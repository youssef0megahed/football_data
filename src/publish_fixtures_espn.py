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
# STATUS
# ============================================================

LIVE_STATUSES = {
    "IN_PLAY",
    "PAUSED",
}

FINISHED_STATUSES = {
    "FINISHED",
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
# RUNTIME DUPLICATE PROTECTION
# ============================================================

SENT_THIS_RUN = set()


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

def supabase_insert(table, payload):

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
# GET TEAMS MAP
# ============================================================

def get_teams_map():

    params = {
        "select": "source,source_team_id,name,name_ar",
        "source": "eq.espn",
    }

    rows = supabase_get(
        TEAMS_TABLE,
        params,
    )

    teams = {}

    for row in rows:

        source_team_id = row.get(
            "source_team_id"
        )

        if source_team_id is None:
            continue

        source_team_id = str(
            source_team_id
        )

        teams[source_team_id] = {
            "name": row.get("name"),
            "name_ar": row.get("name_ar"),
        }

    return teams


# ============================================================
# GET ARABIC TEAM NAME
# ============================================================

def get_team_name(
    team_id,
    fallback_name,
    teams,
):

    if team_id is not None:

        team = teams.get(
            str(team_id)
        )

        if team:

            arabic_name = team.get(
                "name_ar"
            )

            if arabic_name:
                return arabic_name.strip()

            original_name = team.get(
                "name"
            )

            if original_name:
                return original_name.strip()

    return fallback_name or "فريق غير محدد"


# ============================================================
# COMPETITION NAME
# ============================================================

def get_competition_name(
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

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        ).astimezone(
            TIMEZONE
        )

    except Exception:

        return None


# ============================================================
# FORMAT DATE
# ============================================================

def format_date(kickoff_local):

    dt = parse_datetime(
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

def format_time(kickoff_local):

    dt = parse_datetime(
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
# MATCH DAY
# ============================================================

def get_match_day(kickoff_local):

    dt = parse_datetime(
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
# MATCH TITLE
# ============================================================

def get_match_title(match):

    status = match.get(
        "status"
    )

    if status in LIVE_STATUSES:
        return "🔴 مباراة جارية الآن"

    if status in FINISHED_STATUSES:
        return "🏁 انتهت المباراة"

    day = get_match_day(
        match.get("kickoff_local")
    )

    if day == "today":
        return "📅 مباراة اليوم"

    if day == "tomorrow":
        return "📅 مباراة الغد"

    return "⚽ مباراة"


# ============================================================
# GET SCORE
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
# BUILD MATCH MESSAGE
# ============================================================

def build_match_message(
    match,
    teams,
):

    title = get_match_title(
        match
    )

    competition = get_competition_name(
        match.get("competition_name")
    )

    home = get_team_name(
        match.get("home_team_id"),
        match.get("home_team_name"),
        teams,
    )

    away = get_team_name(
        match.get("away_team_id"),
        match.get("away_team_name"),
        teams,
    )

    match_date = format_date(
        match.get("kickoff_local")
    )

    match_time = format_time(
        match.get("kickoff_local")
    )

    status = match.get(
        "status"
    )

    score = get_score(
        match
    )

    # ========================================================
    # FINISHED
    # ========================================================

    if status in FINISHED_STATUSES:

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
                f"🏁 النتيجة: "
                f"{home_score} - {away_score}\n"
                f"\n"
                f"#كرة_القدم #Football"
            )

    # ========================================================
    # LIVE
    # ========================================================

    if status in LIVE_STATUSES:

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
# TELEGRAM
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
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:

        raise Exception(
            f"Telegram HTTP error "
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
# GET TARGET MATCHES
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

        dt = parse_datetime(
            kickoff
        )

        if not dt:
            continue

        if (
            dt.date() == today
            or
            dt.date() == tomorrow
        ):

            target.append(match)

    return target


# ============================================================
# NOTIFICATION TYPE
# ============================================================

def get_notification_type(match):

    status = match.get(
        "status"
    )

    # --------------------------------------------------------
    # UPCOMING
    # --------------------------------------------------------

    if status not in LIVE_STATUSES and \
       status not in FINISHED_STATUSES:

        return "SCHEDULE"

    # --------------------------------------------------------
    # LIVE
    #
    # Every different score is a new update.
    # --------------------------------------------------------

    if status in LIVE_STATUSES:

        home_score = match.get(
            "home_score"
        )

        away_score = match.get(
            "away_score"
        )

        return (
            f"LIVE:"
            f"{home_score}:"
            f"{away_score}"
        )

    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    if status in FINISHED_STATUSES:

        home_score = match.get(
            "home_score"
        )

        away_score = match.get(
            "away_score"
        )

        return (
            f"FINISHED:"
            f"{home_score}:"
            f"{away_score}"
        )

    return "OTHER"


# ============================================================
# STABLE NOTIFICATION KEY
# ============================================================

def make_notification_key(match):

    match_id = match.get(
        "id"
    )

    notification_type = get_notification_type(
        match
    )

    return (
        f"{match_id}:"
        f"{notification_type}"
    )


# ============================================================
# CHECK NOTIFICATION
# ============================================================

def notification_already_sent(match):

    match_id = match.get(
        "id"
    )

    notification_type = get_notification_type(
        match
    )

    key = make_notification_key(
        match
    )

    # --------------------------------------------------------
    # RUNTIME PROTECTION
    # --------------------------------------------------------

    if key in SENT_THIS_RUN:
        return True

    # --------------------------------------------------------
    # DATABASE PROTECTION
    # --------------------------------------------------------

    params = {
        "select": "id",
        "match_id": f"eq.{match_id}",
        "message_type": (
            f"eq.{notification_type}"
        ),
        "limit": "1",
    }

    # For live / finished notifications,
    # distinguish different scores.
    # For schedule, there is only one notification.

    if notification_type.startswith(
        "LIVE:"
    ):

        score_parts = notification_type.split(
            ":"
        )

        home_score = score_parts[1]
        away_score = score_parts[2]

        params["status"] = "in.(IN_PLAY,PAUSED)"
        params["home_score"] = f"eq.{home_score}"
        params["away_score"] = f"eq.{away_score}"

    elif notification_type.startswith(
        "FINISHED:"
    ):

        score_parts = notification_type.split(
            ":"
        )

        home_score = score_parts[1]
        away_score = score_parts[2]

        params["status"] = "eq.FINISHED"
        params["home_score"] = f"eq.{home_score}"
        params["away_score"] = f"eq.{away_score}"

    else:

        # SCHEDULE
        params["status"] = (
            "not.in.(IN_PLAY,PAUSED,FINISHED)"
        )

    rows = supabase_get(
        NEWS_EVENTS_TABLE,
        params,
    )

    if rows:

        SENT_THIS_RUN.add(
            key
        )

        return True

    return False


# ============================================================
# SAVE NOTIFICATION
# ============================================================

def save_notification(match):

    match_id = match.get(
        "id"
    )

    notification_type = get_notification_type(
        match
    )

    payload = {
        "match_id": match_id,
        "message_type": notification_type,
        "status": match.get(
            "status"
        ),
        "home_score": match.get(
            "home_score"
        ),
        "away_score": match.get(
            "away_score"
        ),
    }

    supabase_insert(
        NEWS_EVENTS_TABLE,
        payload,
    )

    SENT_THIS_RUN.add(
        make_notification_key(
            match
        )
    )


# ============================================================
# PROCESS MATCH
# ============================================================

def process_match(
    match,
    teams,
):

    notification_type = get_notification_type(
        match
    )

    print(
        f"Notification type: "
        f"{notification_type}"
    )

    if notification_already_sent(
        match
    ):

        return "SKIPPED"

    message = build_match_message(
        match,
        teams,
    )

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    send_telegram_message(
        message
    )

    # --------------------------------------------------------
    # SAVE ONLY AFTER TELEGRAM SUCCESS
    # --------------------------------------------------------

    save_notification(
        match
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
        "Timezone : Africa/Cairo"
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

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    teams = get_teams_map()

    print(
        f"ESPN teams loaded: "
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
    # PROCESS
    # --------------------------------------------------------

    for match in matches:

        competition = match.get(
            "competition_name",
            "Unknown",
        )

        home = get_team_name(
            match.get("home_team_id"),
            match.get("home_team_name"),
            teams,
        )

        away = get_team_name(
            match.get("away_team_id"),
            match.get("away_team_name"),
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
                    "📤 Sent successfully"
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
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
