import os
import time
import requests

from datetime import datetime, timedelta
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

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer"
)

# نفحص المباريات اللي هتبدأ خلال الفترة دي (بالدقايق)،
# لأن ESPN بينشر التشكيلة الرسمية عادة قبل الماتش بساعة تقريبًا.
LOOKAHEAD_MINUTES = 120

EVENT_CHANNEL = "telegram"
MESSAGE_TYPE = "lineup"

HASHTAGS = "#كرة_القدم #Football"

COMPETITION_SLUGS = {
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
}

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
    now = datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now} Cairo] {message}", flush=True)


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

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing)
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

            log(f"{label} failed ({attempt}/{MAX_RETRIES}): {error}")
            log(f"Retrying in {delay}s...")

            time.sleep(delay)

    raise RuntimeError(
        f"{label} failed after {MAX_RETRIES} attempts: {last_error}"
    )


# ============================================================
# ESPN
# ============================================================

def espn_get(url, params=None):

    def request():

        response = requests.get(
            url, params=params, timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"ESPN transient HTTP {response.status_code}"
            )

        raise RuntimeError(
            f"ESPN HTTP {response.status_code}: {response.text[:300]}"
        )

    return retry_call(request, f"ESPN GET {url}")


def get_match_summary(source_match_id, league_slug):

    url = f"{ESPN_BASE_URL}/{league_slug}/summary"

    return espn_get(url, {"event": str(source_match_id)})


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


def supabase_request(
    method, table, params=None, json_body=None, extra_headers=None
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

        if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Supabase transient HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )

        raise RuntimeError(
            f"Supabase HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, f"Supabase {method} {table}")


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, payload):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

    def request():

        response = requests.post(
            url, json=payload, timeout=REQUEST_TIMEOUT
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

    return retry_call(request, f"Telegram {method}")


# ============================================================
# GET UPCOMING MATCHES (within lookahead window)
# ============================================================

def get_upcoming_matches():

    now = datetime.now(TIMEZONE)

    end = now + timedelta(minutes=LOOKAHEAD_MINUTES)

    rows = supabase_request(
        "GET",
        "matches",
        params={
            "select": (
                "id,source_match_id,competition_name,"
                "home_team_name,away_team_name,"
                "home_team_db_id,away_team_db_id,"
                "kickoff_local,status"
            ),
            "status": "eq.SCHEDULED",
            "kickoff_local": [
                f"gte.{now.isoformat()}",
                f"lte.{end.isoformat()}",
            ],
        },
    )

    return rows


# ============================================================
# ALREADY ANNOUNCED?
# ============================================================

def already_announced(match_id):

    rows = supabase_request(
        "GET",
        "news_events",
        params={
            "select": "id",
            "match_id": f"eq.{match_id}",
            "message_type": f"eq.{MESSAGE_TYPE}",
            "channel": f"eq.{EVENT_CHANNEL}",
        },
    )

    return len(rows) > 0


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
# TEAM LOOKUP (internal id by ESPN source id)
# ============================================================

def get_team_by_source_id(source_team_id):

    if not source_team_id:
        return None

    rows = supabase_request(
        "GET",
        "teams",
        params={
            "select": "id,name,name_ar,source_team_id",
            "source": "eq.espn",
            "source_team_id": f"eq.{source_team_id}",
        },
    )

    return rows[0] if rows else None


# ============================================================
# PARSE LINEUPS (DEFENSIVE — ESPN's exact schema unverified)
# ============================================================
#
# ESPN's summary endpoint is known (from public docs / community
# reverse-engineering) to include a top-level "lineups" list, one
# entry per team, each with roster entries under a few possible
# key names depending on sport/competition. We try several known
# candidates and log the raw shape so any mismatch can be fixed
# quickly from the GitHub Actions log output (same approach that
# found the "participants" vs "athletesInvolved" bug earlier).
# ============================================================

def parse_lineups(summary, match):

    lineups = summary.get("lineups") or []

    if not lineups:
        log(
            f"No 'lineups' key yet for match "
            f"{match['source_match_id']} "
            f"(not published by ESPN yet, or wrong field name)."
        )
        return []

    log(
        f"Raw lineups top-level keys for match "
        f"{match['source_match_id']}: "
        f"{[list(team.keys()) for team in lineups]}"
    )

    parsed_teams = []

    for index, team_lineup in enumerate(lineups):

        team_info = team_lineup.get("team") or {}

        source_team_id = str(
            team_info.get("id") or ""
        )

        formation = (
            team_lineup.get("formation")
            or team_lineup.get("formationName")
            or ""
        )

        # Try known candidate keys for the list of players.
        entries = (
            team_lineup.get("entries")
            or team_lineup.get("roster")
            or team_lineup.get("statistics")
            or []
        )

        if entries and not isinstance(entries, list):
            entries = []

        if entries:
            log(
                f"Sample raw lineup entry "
                f"(team_index={index}): {entries[0]}"
            )

        players = []

        for entry in entries:

            athlete = entry.get("athlete") or {}

            source_player_id = str(
                entry.get("playerId")
                or athlete.get("id")
                or ""
            )

            name = (
                athlete.get("displayName")
                or athlete.get("shortName")
                or athlete.get("fullName")
                or ""
            )

            if not source_player_id or not name:
                continue

            position_obj = entry.get("position") or {}

            position = (
                position_obj.get("abbreviation")
                or position_obj.get("name")
                or ""
            )

            jersey = str(
                entry.get("jersey")
                or athlete.get("jersey")
                or ""
            )

            # Starter detection: try a few known conventions.
            is_starter = entry.get("starter")

            if is_starter is None:
                is_starter = not entry.get("substitute", False)

            if is_starter is None:
                is_starter = position.upper() != "SUB"

            players.append(
                {
                    "source_player_id": source_player_id,
                    "name": name,
                    "position": position,
                    "jersey": jersey,
                    "is_starter": bool(is_starter),
                }
            )

        parsed_teams.append(
            {
                "source_team_id": source_team_id,
                "formation": formation,
                "players": players,
            }
        )

    return parsed_teams


# ============================================================
# SAVE LINEUPS + UPSERT PLAYERS
# ============================================================

def save_lineup(match, team_side, team_db_id, team_data):

    records = []

    for player in team_data["players"]:

        records.append(
            {
                "match_id": match["id"],
                "team_side": team_side,
                "team_id": team_db_id,
                "source_player_id": player["source_player_id"],
                "player_name": player["name"],
                "position": player["position"],
                "jersey_number": player["jersey"],
                "is_starter": player["is_starter"],
                "formation": team_data["formation"],
                "source": "espn",
            }
        )

    if not records:
        return

    supabase_request(
        "POST",
        "match_lineups",
        params={"on_conflict": "match_id,source_player_id"},
        json_body=records,
        extra_headers={
            "Prefer": "resolution=merge-duplicates,return=minimal"
        },
    )

    # نضيف اللاعبين لجدول players (بالإنجليزي)، بنفس منطق
    # fixtures_espn.py — لو الاسم العربي متسجل قبل كده، مش بنلمسه.

    player_records = [
        {
            "source": "espn",
            "source_player_id": player["source_player_id"],
            "name": player["name"],
            "team_id": team_db_id,
        }
        for player in team_data["players"]
    ]

    supabase_request(
        "POST",
        "players",
        params={"on_conflict": "source,source_player_id"},
        json_body=player_records,
        extra_headers={
            "Prefer": "resolution=merge-duplicates,return=minimal"
        },
    )


# ============================================================
# MESSAGE
# ============================================================

def format_team_block(label_emoji, team_name, team_data):

    starters = [
        p for p in team_data["players"] if p["is_starter"]
    ]

    lines = [
        f"{label_emoji} {team_name}"
        + (f" ({team_data['formation']})" if team_data["formation"] else "")
    ]

    for i, player in enumerate(starters, start=1):
        lines.append(f"{i}. {player['name']}")

    return "\n".join(lines)


def build_lineup_message(match, home_team_data, away_team_data):

    competition = match.get("competition_name") or ""
    competition_ar = COMPETITION_NAMES_AR.get(competition, competition)

    home = match.get("home_team_name") or "الفريق الأول"
    away = match.get("away_team_name") or "الفريق الثاني"

    lines = ["📋 التشكيلة الرسمية", ""]

    if competition_ar:
        lines.append(f"🏆 {competition_ar}")
        lines.append("")

    lines.append(format_team_block("🔵", home, home_team_data))
    lines.append("")
    lines.append(format_team_block("🔴", away, away_team_data))
    lines.append("")
    lines.append(HASHTAGS)

    return "\n".join(lines)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("LINEUPS PUBLISHER START")
    log("==================================================")

    matches = get_upcoming_matches()

    if not matches:
        log("No upcoming matches in the lookahead window.")
        log("LINEUPS PUBLISHER END")
        return

    log(f"Upcoming matches: {len(matches)}")

    for match in matches:

        match_id = match["id"]
        source_match_id = match["source_match_id"]

        if already_announced(match_id):
            log(f"Already announced match={match_id}, skipping.")
            continue

        league_slug = COMPETITION_SLUGS.get(
            match.get("competition_name")
        )

        if not league_slug:
            log(
                f"WARNING: unknown competition "
                f"'{match.get('competition_name')}' for "
                f"match={match_id}, skipping."
            )
            continue

        try:

            summary = get_match_summary(source_match_id, league_slug)

            teams_data = parse_lineups(summary, match)

            if len(teams_data) < 2:
                log(
                    f"Lineups not ready yet for match={match_id}. "
                    f"Will retry next run."
                )
                continue

            home_team = get_team_by_source_id(
                teams_data[0]["source_team_id"]
            )

            away_team = get_team_by_source_id(
                teams_data[1]["source_team_id"]
            )

            # لو الترتيب مقلوب (تيم[0] مش هو المضيف فعليًا)،
            # نتأكد بمطابقة home_team_db_id المسجل في matches.
            if (
                home_team
                and home_team["id"] != match.get("home_team_db_id")
            ):
                teams_data = list(reversed(teams_data))
                home_team, away_team = away_team, home_team

            home_starters = sum(
                1 for p in teams_data[0]["players"] if p["is_starter"]
            )

            away_starters = sum(
                1 for p in teams_data[1]["players"] if p["is_starter"]
            )

            if home_starters < 11 or away_starters < 11:
                log(
                    f"Incomplete lineup for match={match_id} "
                    f"(home_starters={home_starters}, "
                    f"away_starters={away_starters}). "
                    f"Will retry next run."
                )
                continue

            save_lineup(
                match,
                "home",
                home_team["id"] if home_team else None,
                teams_data[0],
            )

            save_lineup(
                match,
                "away",
                away_team["id"] if away_team else None,
                teams_data[1],
            )

            message = build_lineup_message(
                match, teams_data[0], teams_data[1]
            )

            telegram_request(
                "sendMessage",
                {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message,
                    "disable_web_page_preview": True,
                },
            )

            reserve_announcement(match_id)

            log(f"Sent lineups for match={match_id}")

        except Exception as error:

            log(f"ERROR match={match_id}: {error}")
            continue

    log("LINEUPS PUBLISHER END")
    log("==================================================")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
