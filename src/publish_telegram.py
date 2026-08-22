import os
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import supabase_request, select


# ============================================================
# CONFIG
# ============================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TIMEZONE = ZoneInfo("Africa/Cairo")
REQUEST_TIMEOUT = 30

GEMINI_IMAGE_MODELS = [
    "gemini-3.1-flash-image",
    "gemini-2.5-flash-image",
]

GEMINI_IMAGE_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

COMPETITION_NAMES_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


def validate_telegram_env():

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID"
        )


# ============================================================
# TELEGRAM
# ============================================================

def telegram_send(text):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def request():

        response = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            if not data.get("ok", False):
                raise RuntimeError(str(data))
            return data

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Telegram transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"Telegram HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, "Telegram sendMessage")


def telegram_send_photo_bytes(image_bytes, caption):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    def request():

        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"photo": ("cover.png", image_bytes, "image/png")},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            data = response.json()
            if not data.get("ok", False):
                raise RuntimeError(str(data))
            return data

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Telegram transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"Telegram HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, "Telegram sendPhoto")


# ============================================================
# GEMINI COVER IMAGE (تصميمي/تجريدي — من غير وجوه حقيقية)
# ============================================================

def generate_cover_image(prompt):
    """بيرجع bytes الصورة، أو None لو التوليد فشل (عشان الرسالة
    تتبعت نص عادي بدل ما توقف كل حاجة)."""

    if not GEMINI_API_KEY:
        return None

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
        },
    }

    for model in GEMINI_IMAGE_MODELS:

        url = GEMINI_IMAGE_URL_TEMPLATE.format(model=model)

        try:

            response = requests.post(
                url,
                headers={
                    "x-goog-api-key": GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code != 200:
                log(
                    f"Gemini image ({model}) HTTP "
                    f"{response.status_code}: {response.text[:300]}"
                )
                continue

            data = response.json()

            parts = (
                data["candidates"][0]["content"]["parts"]
            )

            for part in parts:

                inline_data = part.get("inlineData") or part.get(
                    "inline_data"
                )

                if inline_data and inline_data.get("data"):

                    import base64

                    return base64.b64decode(inline_data["data"])

            log(f"Gemini image ({model}): no image data in response")

        except Exception as error:
            log(f"Gemini image ({model}) failed: {error}")
            continue

    return None


def build_cover_prompt(home_name_en, away_name_en, competition_name):
    """برومبت لصورة تصميمية مجردة (مش صورة واقعية للاعبين حقيقيين)،
    بهوية بصرية موحدة لصفحتنا."""

    return (
        "Create a bold, modern sports-news cover graphic for a "
        "football (soccer) match announcement. Abstract, stylized "
        "illustration only — absolutely no real people, no faces, "
        "no recognizable athlete likenesses, no logos or text. "
        f"Theme: {home_name_en} vs {away_name_en}, {competition_name}. "
        "Dynamic abstract player silhouettes, dramatic stadium "
        "lighting, high-contrast professional sports-media "
        "aesthetic, cinematic color grading."
    )

    return retry_call(request, "Telegram sendMessage")


# ============================================================
# HELPERS
# ============================================================

def resolve_name(name, name_ar):
    return name_ar if name_ar else (name or "")


def format_arabic_time(dt_cairo):

    hour = dt_cairo.hour
    minute = dt_cairo.minute

    period = "صباحًا" if hour < 12 else "مساءً"

    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    return f"{hour_12:02d}:{minute:02d} {period}"


def get_teams_by_ids(team_ids):

    if not team_ids:
        return {}

    ids = ",".join(str(t) for t in team_ids)

    rows = select(
        "teams",
        {"select": "id,name,name_ar", "id": f"in.({ids})"},
    )

    return {row["id"]: row for row in rows}


# ============================================================
# SCHEDULE MESSAGES (upcoming matches today, not yet posted)
# ============================================================

def get_matches_to_announce():

    today = datetime.now(TIMEZONE).date()

    start = today.isoformat() + "T00:00:00+03:00"
    end = (today + timedelta(days=1)).isoformat() + "T00:00:00+03:00"

    return select(
        "matches",
        {
            "select": (
                "id,competition_id,home_team_id,away_team_id,"
                "kickoff_at,status"
            ),
            "kickoff_at": [f"gte.{start}", f"lt.{end}"],
            "schedule_posted_at": "is.null",
        },
    )


def build_schedule_message(match, teams, competition_name):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = resolve_name(home.get("name"), home.get("name_ar"))
    away_name = resolve_name(away.get("name"), away.get("name_ar"))

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    kickoff = datetime.fromisoformat(match["kickoff_at"])

    if kickoff.tzinfo is not None:
        kickoff = kickoff.astimezone(TIMEZONE)

    lines = ["📅 مباراة اليوم", ""]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(f"⚽ {home_name} 🆚 {away_name}")
    lines.append("")
    lines.append(f"📆 {kickoff.date().isoformat()}")
    lines.append(f"⏰ {format_arabic_time(kickoff)} بتوقيت القاهرة")

    return "\n".join(lines)


# ============================================================
# RESULT MESSAGES (finished matches, not yet posted)
# ============================================================

def get_matches_to_report():

    return select(
        "matches",
        {
            "select": (
                "id,competition_id,home_team_id,away_team_id,"
                "home_score,away_score,status"
            ),
            "status": "eq.FINISHED",
            "result_posted_at": "is.null",
        },
    )


def get_players_by_ids(player_ids):

    if not player_ids:
        return {}

    ids = ",".join(str(p) for p in player_ids if p)

    if not ids:
        return {}

    rows = select(
        "players",
        {"select": "id,name,name_ar", "id": f"in.({ids})"},
    )

    return {row["id"]: row for row in rows}


def get_goals_for_match(match_id):

    return select(
        "match_events",
        {
            "select": "player_id,team_id,minute,extra_time",
            "match_id": f"eq.{match_id}",
            "event_type": "eq.goal",
            "order": "minute.asc",
        },
    )


def format_minute(minute, extra_time):

    if minute is None:
        return ""

    if extra_time:
        return f"{minute}+{extra_time}'"

    return f"{minute}'"


def build_result_message(match, teams, competition_name, goals, players):

    home = teams.get(match["home_team_id"], {})
    away = teams.get(match["away_team_id"], {})

    home_name = resolve_name(home.get("name"), home.get("name_ar"))
    away_name = resolve_name(away.get("name"), away.get("name_ar"))

    competition_ar = COMPETITION_NAMES_AR.get(
        competition_name, competition_name
    )

    lines = ["🏁 نهاية المباراة", ""]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(
        f"{home_name} {match['home_score']} - "
        f"{match['away_score']} {away_name}"
    )

    if goals:

        home_team_id = match["home_team_id"]
        away_team_id = match["away_team_id"]

        home_goals = [g for g in goals if g.get("team_id") == home_team_id]
        away_goals = [g for g in goals if g.get("team_id") == away_team_id]

        def format_goal_lines(team_goals):

            output = []

            for goal in team_goals:

                player = players.get(goal.get("player_id"), {})

                player_name = resolve_name(
                    player.get("name"), player.get("name_ar")
                )

                minute_text = format_minute(
                    goal.get("minute"), goal.get("extra_time")
                )

                if player_name:
                    output.append(f"  ⚽ {player_name} {minute_text}")

            return output

        if home_goals:
            lines.append("")
            lines.append(f"أهداف {home_name}:")
            lines.extend(format_goal_lines(home_goals))

        if away_goals:
            lines.append("")
            lines.append(f"أهداف {away_name}:")
            lines.extend(format_goal_lines(away_goals))

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()
    validate_telegram_env()

    log("==================================================")
    log("PUBLISH TELEGRAM (schedules + results) START")
    log("==================================================")

    competitions = select("competitions", {"select": "id,name"})
    competition_names = {c["id"]: c["name"] for c in competitions}

    # --- Schedules ---

    to_announce = get_matches_to_announce()

    log(f"Matches to announce (schedule): {len(to_announce)}")

    team_ids = set()

    for m in to_announce:
        team_ids.add(m["home_team_id"])
        team_ids.add(m["away_team_id"])

    teams = get_teams_by_ids(team_ids)

    for match in to_announce:

        try:

            message = build_schedule_message(
                match, teams, competition_names.get(match["competition_id"])
            )

            home = teams.get(match["home_team_id"], {})
            away = teams.get(match["away_team_id"], {})

            prompt = build_cover_prompt(
                home.get("name", ""), away.get("name", ""),
                competition_names.get(match["competition_id"], ""),
            )

            image_bytes = generate_cover_image(prompt)

            if image_bytes:
                telegram_send_photo_bytes(image_bytes, message)
            else:
                telegram_send(message)

            supabase_request(
                "PATCH",
                "matches",
                params={"id": f"eq.{match['id']}"},
                json_body={
                    "schedule_posted_at": datetime.now(TIMEZONE).isoformat()
                },
                extra_headers={"Prefer": "return=minimal"},
            )

            log(f"Sent schedule for match={match['id']}")

        except Exception as error:
            log(f"ERROR schedule match={match['id']}: {error}")
            continue

    # --- Results ---

    to_report = get_matches_to_report()

    log(f"Matches to report (result): {len(to_report)}")

    team_ids = set()

    for m in to_report:
        team_ids.add(m["home_team_id"])
        team_ids.add(m["away_team_id"])

    teams = get_teams_by_ids(team_ids)

    for match in to_report:

        try:

            goals = get_goals_for_match(match["id"])

            player_ids = {g.get("player_id") for g in goals}

            players = get_players_by_ids(player_ids)

            message = build_result_message(
                match,
                teams,
                competition_names.get(match["competition_id"]),
                goals,
                players,
            )

            home = teams.get(match["home_team_id"], {})
            away = teams.get(match["away_team_id"], {})

            prompt = build_cover_prompt(
                home.get("name", ""), away.get("name", ""),
                competition_names.get(match["competition_id"], ""),
            )

            image_bytes = generate_cover_image(prompt)

            if image_bytes:
                telegram_send_photo_bytes(image_bytes, message)
            else:
                telegram_send(message)

            supabase_request(
                "PATCH",
                "matches",
                params={"id": f"eq.{match['id']}"},
                json_body={
                    "result_posted_at": datetime.now(TIMEZONE).isoformat()
                },
                extra_headers={"Prefer": "return=minimal"},
            )

            log(f"Sent result for match={match['id']}")

        except Exception as error:
            log(f"ERROR result match={match['id']}: {error}")
            continue

    log("==================================================")
    log("PUBLISH TELEGRAM END")
    log("==================================================")


if __name__ == "__main__":
    main()
