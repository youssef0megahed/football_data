import os
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

TIMEZONE = ZoneInfo("Africa/Cairo")

MATCHES_TABLE = "matches"
TEAMS_TABLE = "teams"
NEWS_EVENTS_TABLE = "news_events"

REQUEST_TIMEOUT = 30


# ============================================================
# COMPETITIONS
# ============================================================

COMPETITION_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


# ============================================================
# STATUS
# ============================================================

STATUS_AR = {
    "TIMED": "لم تبدأ",
    "SCHEDULED": "مجدولة",
    "IN_PLAY": "جارية الآن",
    "PAUSED": "استراحة",
    "FINISHED": "انتهت",
    "POSTPONED": "تأجلت",
    "SUSPENDED": "توقفت",
    "CANCELLED": "ألغيت",
    "AWARDED": "حُسمت",
}


# ============================================================
# SUPABASE HEADERS
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# VALIDATE ENVIRONMENT
# ============================================================

def validate_environment():

    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise Exception(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# SUPABASE GET
# ============================================================

def supabase_get(table, params=None):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params or {},
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise Exception(
            f"Supabase GET failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# SUPABASE INSERT
# ============================================================

def supabase_insert(
    table,
    payload,
):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    headers = {
        **SUPABASE_HEADERS,
        "Prefer": "return=minimal",
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code not in [200, 201, 204]:

        raise Exception(
            f"Supabase INSERT failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return True


# ============================================================
# GET TEAMS
# ============================================================

def get_teams_map():

    params = {
        "select": "source,source_team_id,name,name_ar"
    }

    rows = supabase_get(
        TEAMS_TABLE,
        params,
    )

    teams = {}

    for row in rows:

        source = row.get("source") or "espn"

        source_team_id = row.get(
            "source_team_id"
        )

        if source_team_id is None:
            continue

        teams[
            (
                source,
                str(source_team_id)
            )
        ] = {
            "name": row.get("name"),
            "name_ar": row.get("name_ar"),
        }

    return teams


# ============================================================
# TEAM ARABIC NAME
# ============================================================

def get_team_arabic_name(
    source,
    team_id,
    fallback_name,
    teams,
):

    if team_id is not None:

        key = (
            source or "espn",
            str(team_id)
        )

        team = teams.get(key)

        if team:

            if team.get("name_ar"):
                return team["name_ar"]

            if team.get("name"):
                return team["name"]

    return fallback_name or "فريق غير محدد"


# ============================================================
# COMPETITION ARABIC
# ============================================================

def get_competition_arabic_name(
    competition_name
):

    return COMPETITION_AR.get(
        competition_name,
        competition_name or "بطولة غير محددة",
    )


# ============================================================
# PARSE DATETIME
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


# ============================================================
# MATCH DATE
# ============================================================

def get_match_date(
    kickoff_local
):

    dt = parse_datetime(
        kickoff_local
    )

    if not dt:
        return None

    return dt.astimezone(
        TIMEZONE
    )


# ============================================================
# MATCH DAY
# ============================================================

def get_match_day(
    kickoff_local
):

    dt = get_match_date(
        kickoff_local
    )

    if not dt:
        return "unknown"

    today = datetime.now(
        TIMEZONE
    ).date()

    tomorrow = today + timedelta(
        days=1
    )

    if dt.date() == today:
        return "today"

    if dt.date() == tomorrow:
        return "tomorrow"

    return "other"


# ============================================================
# FORMAT DATE
# ============================================================

def format_date(
    kickoff_local
):

    dt = get_match_date(
        kickoff_local
    )

    if not dt:
        return "غير محدد"

    return dt.strftime(
        "%Y-%m-%d"
    )


# ============================================================
# FORMAT TIME
# ============================================================

def format_time(
    kickoff_local
):

    dt = get_match_date(
        kickoff_local
    )

    if not dt:
        return "غير محدد"

    hour = dt.hour
    minute = dt.minute

    if hour == 0:

        hour_12 = 12
        period = "صباحًا"

    elif hour < 12:

        hour_12 = hour
        period = "صباحًا"

    elif hour == 12:

        hour_12 = 12
        period = "ظهرًا"

    else:

        hour_12 = hour - 12
        period = "مساءً"

    return (
        f"{hour_12:02d}:"
        f"{minute:02d} "
        f"{period}"
    )


# ============================================================
# SCORE
# ============================================================

def get_score(match):

    home_score = match.get(
        "home_score"
    )

    away_score = match.get(
        "away_score"
    )

    if (
        home_score is None
        or away_score is None
    ):
        return None

    try:

        return (
            int(home_score),
            int(away_score),
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# MESSAGE TITLE
# ============================================================

def get_message_title(
    match
):

    status = (
        match.get("status")
        or ""
    ).upper()

    day = get_match_day(
        match.get(
            "kickoff_local"
        )
    )

    if status == "FINISHED":
        return "🏁 انتهت المباراة"

    if status in [
        "IN_PLAY",
        "PAUSED",
    ]:
        return "🔴 مباراة جارية الآن"

    if status == "POSTPONED":
        return "⚠️ مباراة مؤجلة"

    if status == "SUSPENDED":
        return "⚠️ مباراة متوقفة"

    if status == "CANCELLED":
        return "❌ مباراة ألغيت"

    if day == "today":
        return "📅 مباراة اليوم"

    if day == "tomorrow":
        return "📅 مباراة الغد"

    return "⚽ مباراة"


# ============================================================
# BUILD MESSAGE
# ============================================================

def build_match_message(
    match,
    teams,
):

    source = (
        match.get("source")
        or "espn"
    )

    competition = (
        get_competition_arabic_name(
            match.get(
                "competition_name"
            )
        )
    )

    home = get_team_arabic_name(
        source,
        match.get(
            "home_team_id"
        ),
        match.get(
            "home_team_name"
        ),
        teams,
    )

    away = get_team_arabic_name(
        source,
        match.get(
            "away_team_id"
        ),
        match.get(
            "away_team_name"
        ),
        teams,
    )

    kickoff = match.get(
        "kickoff_local"
    )

    match_date = format_date(
        kickoff
    )

    match_time = format_time(
        kickoff
    )

    title = get_message_title(
        match
    )

    status = (
        match.get("status")
        or ""
    ).upper()

    score = get_score(
        match
    )

    # ========================================================
    # FINISHED
    # ========================================================

    if status == "FINISHED" and score:

        home_score, away_score = score

        return (
            f"{title}\n"
            f"\n"
            f"🏆 {competition}\n"
            f"\n"
            f"⚽ {home} 🆚 {away}\n"
            f"\n"
            f"📆{match_date}\n"
            f"\n"
            f"🏁 النتيجة: "
            f"{home_score} - {away_score}\n"
            f"\n"
            f"#كرة_القدم #Football"
        )

    # ========================================================
    # LIVE
    # ========================================================

    if status in [
        "IN_PLAY",
        "PAUSED",
    ]:

        if score:

            home_score, away_score = score

            return (
                f"{title}\n"
                f"\n"
                f"🏆 {competition}\n"
                f"\n"
                f"⚽ {home} 🆚 {away}\n"
                f"\n"
                f"📆{match_date}\n"
                f"\n"
                f"⏰ {match_time} "
                f"بتوقيت القاهرة\n"
                f"\n"
                f"📊 النتيجة الحالية: "
                f"{home_score} - {away_score}\n"
                f"\n"
                f"#كرة_القدم #Football"
            )

    # ========================================================
    # UPCOMING
    # ========================================================

    return (
        f"{title}\n"
        f"\n"
        f"🏆 {competition}\n"
        f"\n"
        f"⚽ {home} 🆚 {away}\n"
        f"\n"
        f"📆{match_date}\n"
        f"\n"
        f"⏰ {match_time} "
        f"بتوقيت القاهرة\n"
        f"\n"
        f"#كرة_القدم #Football"
    )


# ============================================================
# TELEGRAM SEND
# ============================================================

def send_telegram_message(
    message
):

    url = (
        "https://api.telegram.org/bot"
        f"{TELEGRAM_BOT_TOKEN}"
        "/sendMessage"
    )

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:

        raise Exception(
            f"Telegram send failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not data.get("ok"):

        raise Exception(
            f"Telegram error: {data}"
        )

    return True


# ============================================================
# GET TODAY + TOMORROW MATCHES
# ============================================================

def get_target_matches():

    now = datetime.now(
        TIMEZONE
    )

    today = now.date()

    tomorrow = today + timedelta(
        days=1
    )

    start = datetime(
        today.year,
        today.month,
        today.day,
        tzinfo=TIMEZONE,
    )

    end = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        tzinfo=TIMEZONE,
    )

    end = end + timedelta(
        days=1
    )

    params = {
        "select": "*",
        "kickoff_local": (
            f"gte.{start.isoformat()}"
            f"&kickoff_local=lt."
            f"{end.isoformat()}"
        ),
        "order": "kickoff_local.asc",
    }

    # --------------------------------------------------------
    # Supabase REST handles each filter separately.
    # We fetch from today onward and filter locally.
    # --------------------------------------------------------

    params = {
        "select": "*",
        "kickoff_local": (
            f"gte.{start.isoformat()}"
        ),
        "order": "kickoff_local.asc",
    }

    rows = supabase_get(
        MATCHES_TABLE,
        params,
    )

    target = []

    for match in rows:

        day = get_match_day(
            match.get(
                "kickoff_local"
            )
        )

        if day in [
            "today",
            "tomorrow",
        ]:

            target.append(
                match
            )

    return target


# ============================================================
# EVENT TYPE
# ============================================================

def determine_message_type(
    match
):

    status = (
        match.get("status")
        or ""
    ).upper()

    if status == "FINISHED":
        return "FINISHED"

    if status == "IN_PLAY":
        return "IN_PLAY"

    if status == "PAUSED":
        return "PAUSED"

    return "SCHEDULE"


# ============================================================
# CHECK DUPLICATE
# ============================================================

def event_already_sent(
    match_id,
    message_type,
    status,
    home_score,
    away_score,
):

    params = {
        "select": "id",
        "match_id": f"eq.{match_id}",
        "message_type": (
            f"eq.{message_type}"
        ),
        "status": f"eq.{status}",
        "limit": "1",
    }

    if home_score is None:

        params[
            "home_score"
        ] = "is.null"

    else:

        params[
            "home_score"
        ] = f"eq.{home_score}"

    if away_score is None:

        params[
            "away_score"
        ] = "is.null"

    else:

        params[
            "away_score"
        ] = f"eq.{away_score}"

    rows = supabase_get(
        NEWS_EVENTS_TABLE,
        params,
    )

    return bool(rows)


# ============================================================
# SAVE NEWS EVENT
# ============================================================

def save_news_event(
    match,
    message_type,
    status,
    home_score,
    away_score,
):

    payload = {
        "match_id": match["id"],
        "message_type": message_type,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
    }

    supabase_insert(
        NEWS_EVENTS_TABLE,
        payload,
    )


# ============================================================
# PROCESS MATCH
# ============================================================

def process_match(
    match,
    teams,
):

    match_id = match["id"]

    status = (
        match.get("status")
        or ""
    ).upper()

    score = get_score(
        match
    )

    if score:

        home_score, away_score = score

    else:

        home_score = None
        away_score = None

    message_type = (
        determine_message_type(
            match
        )
    )

    if event_already_sent(
        match_id,
        message_type,
        status,
        home_score,
        away_score,
    ):

        return "SKIPPED"

    message = build_match_message(
        match,
        teams,
    )

    send_telegram_message(
        message
    )

    save_news_event(
        match,
        message_type,
        status,
        home_score,
        away_score,
    )

    return "SENT"


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    now = datetime.now(
        TIMEZONE
    )

    print("=" * 70)
    print("FOOTBALL NEWS ENGINE")
    print("=" * 70)

    print(
        f"Timezone : Africa/Cairo"
    )

    print(
        f"Now      : "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Today    : {now.date()}"
    )

    print(
        f"Tomorrow : "
        f"{now.date() + timedelta(days=1)}"
    )

    print("=" * 70)

    # ========================================================
    # TEAMS
    # ========================================================

    teams = get_teams_map()

    print(
        f"Teams loaded: {len(teams)}"
    )

    # ========================================================
    # MATCHES
    # ========================================================

    matches = get_target_matches()

    print(
        f"Matches found: {len(matches)}"
    )

    print("")

    sent = 0
    skipped = 0
    errors = 0

    # ========================================================
    # EACH MATCH = ONE MESSAGE
    # ========================================================

    for match in matches:

        competition = (
            match.get(
                "competition_name"
            )
            or "Unknown"
        )

        home = get_team_arabic_name(
            match.get(
                "source"
            ),
            match.get(
                "home_team_id"
            ),
            match.get(
                "home_team_name"
            ),
            teams,
        )

        away = get_team_arabic_name(
            match.get(
                "source"
            ),
            match.get(
                "away_team_id"
            ),
            match.get(
                "away_team_name"
            ),
            teams,
        )

        print("-" * 70)

        print(
            f"🏆 {competition}"
        )

        print(
            f"⚽ {home} vs {away}"
        )

        print(
            f"Status: "
            f"{match.get('status')}"
        )

        try:

            result = process_match(
                match,
                teams,
            )

            if result == "SENT":

                sent += 1

                print(
                    "📤 Sent"
                )

            else:

                skipped += 1

                print(
                    "⏭️ Already sent"
                )

        except Exception as error:

            errors += 1

            print(
                f"❌ ERROR: {error}"
            )

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"Matches checked : {len(matches)}"
    )

    print(
        f"News sent       : {sent}"
    )

    print(
        f"Skipped         : {skipped}"
    )

    print(
        f"Errors          : {errors}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
