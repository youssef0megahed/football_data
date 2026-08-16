mport  os
import requests

from datetime import datetime
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


# ============================================================
# ARABIC COMPETITION NAMES
# ============================================================

COMPETITION_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


# ============================================================
# STATUS TRANSLATIONS
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
# VALIDATION
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
        timeout=30,
    )

    if response.status_code != 200:

        raise Exception(
            f"Supabase GET failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# SUPABASE UPDATE
# ============================================================

def supabase_update(table, params, payload):

    url = f"{SUPABASE_URL}/rest/v1/{table}"

    response = requests.patch(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        json=payload,
        timeout=30,
    )

    if response.status_code not in [200, 204]:

        raise Exception(
            f"Supabase UPDATE failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return True


# ============================================================
# GET ARABIC TEAM NAMES
# ============================================================

def get_teams_map():

    params = {
        "select": "source_team_id,name,name_ar"
    }

    rows = supabase_get(
        TEAMS_TABLE,
        params,
    )

    teams = {}

    for row in rows:

        source_team_id = str(
            row.get("source_team_id")
        )

        teams[source_team_id] = {
            "name": row.get("name"),
            "name_ar": row.get("name_ar"),
        }

    return teams


# ============================================================
# TRANSLATE TEAM
# ============================================================

def get_team_arabic_name(team_id, fallback_name, teams):

    if team_id:

        team = teams.get(
            str(team_id)
        )

        if team:

            if team.get("name_ar"):
                return team["name_ar"]

            if team.get("name"):
                return team["name"]

    return fallback_name or "فريق غير محدد"


# ============================================================
# COMPETITION NAME
# ============================================================

def get_competition_arabic_name(name):

    return COMPETITION_AR.get(
        name,
        name or "بطولة غير محددة"
    )


# ============================================================
# STATUS
# ============================================================

def get_status_arabic(status):

    return STATUS_AR.get(
        status,
        status or "غير معروف"
    )


# ============================================================
# FORMAT TIME - 12 HOUR
# ============================================================

def format_time(kickoff_local):

    if not kickoff_local:
        return "غير محدد"

    try:

        dt = datetime.fromisoformat(
            kickoff_local.replace(
                "Z",
                "+00:00"
            )
        )

        dt = dt.astimezone(TIMEZONE)

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

    except Exception:

        return str(kickoff_local)


# ============================================================
# FORMAT DATE
# ============================================================

def format_date(kickoff_local):

    if not kickoff_local:
        return ""

    try:

        dt = datetime.fromisoformat(
            kickoff_local.replace(
                "Z",
                "+00:00"
            )
        )

        dt = dt.astimezone(TIMEZONE)

        return dt.strftime(
            "%Y-%m-%d"
        )

    except Exception:

        return ""


# ============================================================
# DETERMINE MATCH DAY
# ============================================================

def get_match_day(kickoff_local):

    if not kickoff_local:
        return "unknown"

    try:

        dt = datetime.fromisoformat(
            kickoff_local.replace(
                "Z",
                "+00:00"
            )
        )

        dt = dt.astimezone(TIMEZONE)

        now = datetime.now(
            TIMEZONE
        )

        today = now.date()

        tomorrow = (
            today.replace()
        )

        from datetime import timedelta

        tomorrow = today + timedelta(
            days=1
        )

        if dt.date() == today:
            return "today"

        if dt.date() == tomorrow:
            return "tomorrow"

        return "other"

    except Exception:

        return "unknown"


# ============================================================
# MATCH SCORE
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

    return (
        int(home_score),
        int(away_score)
    )


# ============================================================
# MESSAGE TYPE
# ============================================================

def get_message_title(
    match,
    previous_status=None,
):

    status = match.get(
        "status"
    )

    if status == "FINISHED":

        return "  انتهت المباراة 🔔🕛"

    if status in [
        "IN_PLAY",
        "PAUSED",
    ]:

        return "🔴 مباراة جارية الان"

    if previous_status in [
        "TIMED",
        "SCHEDULED",
    ] and status == "IN_PLAY":

        return "🚨 انطلاق المباراة"

    day = get_match_day(
        match.get("kickoff_local")
    )

    if day == "today":

        return "📅 مباراة اليوم"

    if day == "tomorrow":

        return "📅 مباراة الغد"

    return "⚽ مباراة"


# ============================================================
# BUILD MATCH MESSAGE
# ============================================================
def build_match_message(
    match,
    teams,
    previous_status=None,
):

    competition = get_competition_arabic_name(
        match.get("competition_name")
    )

    home = get_team_arabic_name(
        match.get("home_team_id"),
        match.get("home_team_name"),
        teams,
    )

    away = get_team_arabic_name(
        match.get("away_team_id"),
        match.get("away_team_name"),
        teams,
    )

    status = match.get("status")

    match_time = format_time(
        match.get("kickoff_local")
    )

    match_date = format_date(
        match.get("kickoff_local")
    )

    day = get_match_day(
        match.get("kickoff_local")
    )

    # ========================================================
    # TITLE
    # ========================================================

    if status == "FINISHED":
        title = "� انتهت المباراة "

    elif status in ["IN_PLAY", "PAUSED"]:
        title = "🔴 مباراة جارية الآن"

    elif day == "today":
        title = "📅 مباراة اليوم"

    elif day == "tomorrow":
        title = "📅 مباراة الغد"

    else:
        title = "⚽ مباراة"

    # ========================================================
    # FINISHED MATCH
    # ========================================================

    if status == "FINISHED":

        score = get_score(match)

        if score:

            home_score, away_score = score

            return (
                f"{title}\n"
                f"\n"
                f"🏆 {competition}\n"
                f"\n"
                f" {home} 🆚 {away}\n"
                f"\n"
                f"📆{match_date}\n"
                f"\n"
                f"🏁 النتيجة: "
                f"{home_score} - {away_score}\n"
                f"\n"
                f"#كرة_القدم #Football"
            )

    # ========================================================
    # LIVE MATCH
    # ========================================================

    if status in ["IN_PLAY", "PAUSED"]:

        score = get_score(match)

        if score:

            home_score, away_score = score

            return (
                f"{title}\n"
                f"\n"
                f"🏆 {competition}\n"
                f"\n"
                f" {home} 🆚 {away}\n"
                f"\n"
                f"📆{match_date}\n"
                f"\n"
                f"⏰ {match_time} بتوقيت القاهرة\n"
                f"\n"
                f"📊 النتيجة الحالية: "
                f"{home_score} - {away_score}\n"
                f"\n"
                f"#كرة_القدم #Football"
            )

    # ========================================================
    # UPCOMING MATCH
    # ========================================================

    return (
        f"{title}\n"
        f"\n"
        f"🏆 {competition}\n"
        f"\n"
        f" {home} 🆚 {away}\n"
        f"\n"
        f"📆{match_date}\n"
        f"\n"
        f"⏰ {match_time} بتوقيت القاهرة\n"
        f"\n"
        f"#كرة_القدم #Football"
    )

# ============================================================
# TELEGRAM SEND
# ============================================================

def send_telegram_message(message):

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
        timeout=30,
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
            f"Telegram error: "
            f"{data}"
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

    from datetime import timedelta

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

    day_after = tomorrow + timedelta(
        days=1
    )

    end = datetime(
        day_after.year,
        day_after.month,
        day_after.day,
        tzinfo=TIMEZONE,
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

    # Supabase REST does not accept the
    # combined filter above in a single value.
    # Therefore use two explicit filters.

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

        kickoff = match.get(
            "kickoff_local"
        )

        day = get_match_day(
            kickoff
        )

        if day in [
            "today",
            "tomorrow",
        ]:

            target.append(match)

    return target


# ============================================================
# GET MATCH BY ID
# ============================================================

def get_match_by_id(match_id):

    params = {
        "select": "*",
        "id": f"eq.{match_id}",
        "limit": "1",
    }

    rows = supabase_get(
        MATCHES_TABLE,
        params,
    )

    if not rows:
        return None

    return rows[0]


# ============================================================
# GET PREVIOUS STATE
# ============================================================

def get_previous_state(match):

    """
    We use the existing database state to determine
    whether a match changed.

    The current fixtures.py updates the same row,
    so we keep a small notification state in the
    news_events table.

    If the table does not exist yet, create it using
    the SQL supplied below.
    """

    match_id = match["id"]

    params = {
        "select": "*",
        "match_id": f"eq.{match_id}",
        "order": "created_at.desc",
        "limit": "1",
    }

    rows = supabase_get(
        "news_events",
        params,
    )

    if not rows:
        return None

    return rows[0]


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

    url = (
        f"{SUPABASE_URL}/rest/v1/news_events"
    )

    response = requests.post(
        url,
        headers={
            **SUPABASE_HEADERS,
            "Prefer": "return=minimal",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code not in [
        200,
        201,
    ]:

        raise Exception(
            f"news_events insert failed "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# CHECK IF EVENT WAS ALREADY SENT
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

        params["home_score"] = "is.null"

    else:

        params["home_score"] = (
            f"eq.{home_score}"
        )

    if away_score is None:

        params["away_score"] = "is.null"

    else:

        params["away_score"] = (
            f"eq.{away_score}"
        )

    rows = supabase_get(
        "news_events",
        params,
    )

    return len(rows) > 0


# ============================================================
# DETERMINE MESSAGE TYPE
# ============================================================

def determine_message_type(match):

    status = match.get(
        "status"
    )

    score = get_score(match)

    if status == "FINISHED":

        return "FINISHED"

    if status == "IN_PLAY":

        return "IN_PLAY"

    if status == "PAUSED":

        return "PAUSED"

    return "SCHEDULE"


# ============================================================
# PROCESS MATCH
# ============================================================

def process_match(
    match,
    teams,
):

    match_id = match["id"]

    status = match.get(
        "status"
    )

    score = get_score(match)

    if score:

        home_score, away_score = score

    else:

        home_score = None
        away_score = None

    message_type = determine_message_type(
        match
    )

    # --------------------------------------------------------
    # INITIAL SYNC
    # --------------------------------------------------------

    already_sent = event_already_sent(
        match_id,
        message_type,
        status,
        home_score,
        away_score,
    )

    if already_sent:

        return "SKIPPED"

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    message = build_match_message(
        match,
        teams,
    )

    send_telegram_message(
        message
    )

    # --------------------------------------------------------
    # SAVE EVENT
    # --------------------------------------------------------

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
        f"Today    : "
        f"{now.date()}"
    )

    from datetime import timedelta

    print(
        f"Tomorrow : "
        f"{now.date() + timedelta(days=1)}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    teams = get_teams_map()

    print(
        f"Arabic teams loaded: "
        f"{len(teams)}"
    )

    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

    matches = get_target_matches()

    print(
        f"Matches found: "
        f"{len(matches)}"
    )

    print("")

    sent = 0
    skipped = 0
    errors = 0

    # --------------------------------------------------------
    # PROCESS EACH MATCH
    # --------------------------------------------------------

    for match in matches:

        competition = match.get(
            "competition_name",
            "Unknown"
        )

        home = get_team_arabic_name(
            match.get("home_team_id"),
            match.get("home_team_name"),
            teams,
        )

        away = get_team_arabic_name(
            match.get("away_team_id"),
            match.get("away_team_name"),
            teams,
        )

        print("-" * 70)

        print(
            f"🏆 {competition}"
        )

        print(
            f"{home} vs {away}"
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
                    "📤 News sent successfully"
                )

            else:

                skipped += 1

                print(
                    "⏭️ Already sent - skipped"
                )

        except Exception as error:

            errors += 1

            print(
                f"❌ ERROR: {error}"
            )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"Matches checked : "
        f"{len(matches)}"
    )

    print(
        f"News sent       : "
        f"{sent}"
    )

    print(
        f"Skipped         : "
        f"{skipped}"
    )

    print(
        f"Errors          : "
        f"{errors}"
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
