import os
import time
import requests

from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIMEZONE = ZoneInfo("Africa/Cairo")

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

EVENT_CHANNEL = "telegram"
MESSAGE_TYPE = "daily_schedule"

HASHTAGS = "#كرة_القدم #Football"

COMPETITION_NAMES_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


# ============================================================
# LOGGING
# ============================================================

def log(message):
    now = datetime.now(TIMEZONE).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{now} Cairo] {message}",
        flush=True
    )


# ============================================================
# ENVIRONMENT
# ============================================================

def validate_environment():

    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }

    missing = [
        key
        for key, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# RETRY
# ============================================================

def retry_call(operation, label):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            return operation()

        except Exception as error:

            last_error = error

            if attempt >= MAX_RETRIES:
                break

            delay = 2 ** (attempt - 1)

            log(
                f"{label} failed "
                f"({attempt}/{MAX_RETRIES}): {error}"
            )

            log(f"Retrying in {delay}s...")

            time.sleep(delay)

    raise RuntimeError(
        f"{label} failed after "
        f"{MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def supabase_request(
    method,
    table,
    params=None,
    json_body=None,
    extra_headers=None,
):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = dict(SUPABASE_HEADERS)

    if extra_headers:
        headers.update(extra_headers)

    def request():

        response = requests.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code in {200, 201, 204}:

            if not response.content:
                return []

            return response.json()

        if response.status_code in {
            408, 409, 429, 500, 502, 503, 504,
        }:

            raise RuntimeError(
                f"Supabase transient HTTP "
                f"{response.status_code}: "
                f"{response.text[:300]}"
            )

        raise RuntimeError(
            f"Supabase HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(
        request,
        f"Supabase {method} {table}",
    )


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, payload):

    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_BOT_TOKEN
        + "/"
        + method
    )

    def request():

        response = requests.post(
            url,
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:

            data = response.json()

            if not data.get("ok", False):
                raise RuntimeError(str(data))

            return data

        if response.status_code in {
            408, 409, 429, 500, 502, 503, 504,
        }:

            raise RuntimeError(
                f"Telegram transient HTTP "
                f"{response.status_code}"
            )

        raise RuntimeError(
            f"Telegram HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(
        request,
        f"Telegram {method}",
    )


# ============================================================
# GET TODAY'S MATCHES
# ============================================================

def get_todays_matches():

    from datetime import timedelta

    today = datetime.now(TIMEZONE).date()

    start = f"{today.isoformat()}T00:00:00"

    end = f"{(today + timedelta(days=1)).isoformat()}T00:00:00"

    rows = supabase_request(
        "GET",
        "matches",
        params={
            "select": (
                "id,"
                "competition_name,"
                "home_team_name,"
                "away_team_name,"
                "home_team_db_id,"
                "away_team_db_id,"
                "kickoff_local,"
                "status"
            ),
            "kickoff_local": [
                f"gte.{start}",
                f"lt.{end}",
            ],
            "order": "kickoff_local.asc",
        },
    )

    return rows


# ============================================================
# فورم الفريق (آخر 3 مباريات) — من قاعدة بياناتنا فقط،
# من غير أي اعتماد على مصدر خارجي.
# ============================================================

def get_recent_form(team_db_id, before_kickoff, limit=3):

    if not team_db_id:
        return []

    rows = supabase_request(
        "GET",
        "matches",
        params={
            "select": (
                "home_team_db_id,away_team_db_id,"
                "home_score,away_score,kickoff_local"
            ),
            "status": "eq.FINISHED",
            "kickoff_local": f"lt.{before_kickoff}",
            "or": (
                f"(home_team_db_id.eq.{team_db_id},"
                f"away_team_db_id.eq.{team_db_id})"
            ),
            "order": "kickoff_local.desc",
            "limit": str(limit),
        },
    )

    results = []

    for row in rows:

        home_score = row.get("home_score")
        away_score = row.get("away_score")

        if home_score is None or away_score is None:
            continue

        is_home = row.get("home_team_db_id") == team_db_id

        team_score = home_score if is_home else away_score
        opponent_score = away_score if is_home else home_score

        if team_score > opponent_score:
            results.append("W")
        elif team_score < opponent_score:
            results.append("L")
        else:
            results.append("D")

    return results


def format_form(results):

    if not results:
        return ""

    icons = {
        "W": "✅",
        "D": "➖",
        "L": "❌",
    }

    # الأقدم أولاً -> الأحدث آخرًا (سهل القراءة من شمال لليمين)
    ordered = list(reversed(results))

    return "".join(icons[r] for r in ordered)


# ============================================================
# ALREADY ANNOUNCED?
# ============================================================

def get_announced_match_ids(match_ids):

    if not match_ids:
        return set()

    ids = ",".join(str(value) for value in match_ids)

    rows = supabase_request(
        "GET",
        "news_events",
        params={
            "select": "match_id",
            "channel": f"eq.{EVENT_CHANNEL}",
            "message_type": f"eq.{MESSAGE_TYPE}",
            "match_id": f"in.({ids})",
        },
    )

    return {
        row["match_id"]
        for row in rows
        if row.get("match_id") is not None
    }


# ============================================================
# RESERVE ANNOUNCEMENT (avoid duplicate sends)
# ============================================================

def reserve_announcement(match_id):

    record = {
        "match_id": match_id,
        "message_type": MESSAGE_TYPE,
        "channel": EVENT_CHANNEL,
        "sent_at": datetime.now(TIMEZONE).isoformat(),
    }

    supabase_request(
        "POST",
        "news_events",
        json_body=[record],
        extra_headers={"Prefer": "return=minimal"},
    )


# ============================================================
# MESSAGE FORMAT
# ============================================================

def format_arabic_time(dt):

    hour = dt.hour
    minute = dt.minute

    period = "صباحًا" if hour < 12 else "مساءً"

    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    return f"{hour_12:02d}:{minute:02d} {period}"


def build_schedule_message(match):

    competition = match.get("competition_name") or ""
    competition_ar = COMPETITION_NAMES_AR.get(
        competition, competition
    )

    home = match.get("home_team_name") or "الفريق الأول"
    away = match.get("away_team_name") or "الفريق الثاني"

    kickoff_local = match.get("kickoff_local")

    date_text = ""
    time_text = ""

    if kickoff_local:

        dt = datetime.fromisoformat(kickoff_local)

        date_text = dt.date().isoformat()
        time_text = format_arabic_time(dt)

    lines = [
        "📅 مباراة اليوم",
        "",
    ]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(f"⚽ {home} 🆚 {away}")
    lines.append("")

    if date_text:
        lines.append(f"📆{date_text}")
        lines.append("")

    if time_text:
        lines.append(f"⏰ {time_text} بتوقيت القاهرة")
        lines.append("")

    home_form = format_form(
        get_recent_form(
            match.get("home_team_db_id"),
            kickoff_local,
        )
    )

    away_form = format_form(
        get_recent_form(
            match.get("away_team_db_id"),
            kickoff_local,
        )
    )

    if home_form:
        lines.append(f"📊 فورم {home}: {home_form}")

    if away_form:
        lines.append(f"📊 فورم {away}: {away_form}")

    if home_form or away_form:
        lines.append("")

    lines.append(HASHTAGS)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("DAILY SCHEDULE PUBLISHER START")
    log("==================================================")

    matches = get_todays_matches()

    if not matches:
        log("No matches today.")
        log("DAILY SCHEDULE PUBLISHER END")
        return

    log(f"Matches today: {len(matches)}")

    match_ids = [match["id"] for match in matches]

    announced = get_announced_match_ids(match_ids)

    sent = 0
    failed = 0
    skipped = 0

    for match in matches:

        match_id = match["id"]

        if match_id in announced:
            skipped += 1
            continue

        try:

            message = build_schedule_message(match)

            telegram_request(
                "sendMessage",
                {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": True,
                },
            )

            reserve_announcement(match_id)

            log(f"Sent schedule for match={match_id}")

            sent += 1

        except Exception as error:

            failed += 1

            log(f"ERROR match={match_id}: {error}")

            continue

    log("==================================================")
    log(f"Sent: {sent}")
    log(f"Failed: {failed}")
    log(f"Skipped (already announced): {skipped}")
    log("DAILY SCHEDULE PUBLISHER END")
    log("==================================================")

    if failed:
        raise RuntimeError(f"{failed} announcement(s) failed")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
