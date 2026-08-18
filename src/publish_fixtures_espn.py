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

# الأحداث التي ننشرها
PUBLISHABLE_EVENTS = {
    "goal",
    "yellow_card",
    "red_card",
    "substitution",
    "var",
    "penalty",
    "kickoff",
    "start_2nd_half",
    "halftime",
    "fulltime",
}

# أحداث لا يتم نشرها إطلاقًا
IGNORED_EVENTS = {
    "other",
    "delay",
    "start_delay",
    "end_delay",
    "game_delay",
    "weather_delay",
    "review",
    "official_review",
}

# ============================================================
# أسماء البطولات بالعربي
# ============================================================

COMPETITION_NAMES_AR = {
    "Premier League": "الدوري الإنجليزي الممتاز",
    "La Liga": "الدوري الإسباني",
    "Serie A": "الدوري الإيطالي",
    "Bundesliga": "الدوري الألماني",
    "Ligue 1": "الدوري الفرنسي",
}


def resolve_name(name, name_ar):
    """يرجع الاسم العربي لو موجود، وإلا يرجع الاسم الإنجليزي."""

    if name_ar:
        return name_ar

    return name or ""


def make_hashtag(text):

    if not text:
        return ""

    return "#" + text.replace(" ", "_")


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

            log(
                f"Retrying in {delay}s..."
            )

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

    url = (
        f"{SUPABASE_URL}/rest/v1/{table}"
    )

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

        if response.status_code in {
            200,
            201,
            204,
        }:

            if not response.content:
                return []

            return response.json()

        if response.status_code in {
            408,
            409,
            429,
            500,
            502,
            503,
            504,
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
            408,
            409,
            429,
            500,
            502,
            503,
            504,
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
# HELPERS
# ============================================================

def format_minute(minute, extra_time):

    if minute is None:
        return ""

    if extra_time:
        return f"{minute}+{extra_time}'"

    return f"{minute}'"


def score_line(event, match):

    home_score = event.get("home_score")
    away_score = event.get("away_score")

    if home_score is None:
        home_score = match.get("home_score")

    if away_score is None:
        away_score = match.get("away_score")

    if home_score is None or away_score is None:
        return ""

    home = (
        match.get("home_team_display")
        or match.get("home_team_name")
        or "الفريق الأول"
    )

    away = (
        match.get("away_team_display")
        or match.get("away_team_name")
        or "الفريق الثاني"
    )

    return (
        f"📊 {home} "
        f"{home_score} - "
        f"{away_score} {away}"
    )


# ============================================================
# SUBSTITUTION PLAYERS
# ============================================================

def get_substitution_players(event):

    player_out = (
        event.get("player_out_name")
        or ""
    )

    player_in = (
        event.get("player_in_name")
        or ""
    )

    return player_out, player_in


# ============================================================
# EVENT MESSAGE
# ============================================================

def build_event_message(event, match):

    event_type = event.get("event_type")

    team = (
        event.get("team_display")
        or event.get("team_name")
        or ""
    )

    player = (
        event.get("player_name")
        or ""
    )

    minute = format_minute(
        event.get("minute"),
        event.get("extra_time"),
    )

    home = (
        match.get("home_team_display")
        or match.get("home_team_name")
        or "الفريق الأول"
    )

    away = (
        match.get("away_team_display")
        or match.get("away_team_name")
        or "الفريق الثاني"
    )

    competition = (
        match.get("competition_name_display")
        or match.get("competition_name")
        or ""
    )

    hashtag = make_hashtag(competition)

    header_lines = []

    if competition:
        header_lines.append(
            f"🏆 {competition}"
        )


    # --------------------------------------------------------
    # GOAL
    # --------------------------------------------------------

    if event_type == "goal":

        lines = header_lines + [
            "⚽ هدف!"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player:
            lines.append(
                f"👤 {player}"
            )

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # YELLOW CARD
    # --------------------------------------------------------

    if event_type == "yellow_card":

        lines = header_lines + [
            "🟨 بطاقة صفراء"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player:
            lines.append(
                f"👤 {player}"
            )

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # RED CARD
    # --------------------------------------------------------

    if event_type == "red_card":

        lines = header_lines + [
            "🟥 بطاقة حمراء"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player:
            lines.append(
                f"👤 {player}"
            )

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # SUBSTITUTION
    # --------------------------------------------------------

    if event_type == "substitution":

        player_out, player_in = (
            get_substitution_players(event)
        )

        lines = header_lines + [
            "🔄 تبديل"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player_out:
            lines.append(
                f"⬅️ خروج: {player_out}"
            )

        if player_in:
            lines.append(
                f"➡️ دخول: {player_in}"
            )

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # VAR
    # --------------------------------------------------------

    if event_type == "var":

        lines = header_lines + [
            "📺 مراجعة تقنية الفيديو"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player:
            lines.append(
                f"👤 {player}"
            )

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # PENALTY
    # --------------------------------------------------------

    if event_type == "penalty":

        lines = header_lines + [
            "⚽ ركلة جزاء"
        ]

        if team:
            lines.append(
                f"🏟️ {team}"
            )

        if player:
            lines.append(
                f"👤 {player}"
            )

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if minute:
            lines.append(
                f"⏱️ {minute}"
            )

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # KICKOFF
    # --------------------------------------------------------

    if event_type == "kickoff":

        lines = header_lines + [
            "🟢 بداية المباراة",
            "",
            f"{home} 🆚 {away}",
        ]

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # SECOND HALF
    # --------------------------------------------------------

    if event_type == "start_2nd_half":

        lines = header_lines + [
            "▶️ بداية الشوط الثاني",
            "",
            f"{home} 🆚 {away}",
        ]

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # HALF TIME
    # --------------------------------------------------------

    if event_type == "halftime":

        lines = header_lines + [
            "⏸️ نهاية الشوط الأول"
        ]

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    # --------------------------------------------------------
    # FULL TIME
    # --------------------------------------------------------

    if event_type == "fulltime":

        lines = header_lines + [
            "🏁 نهاية المباراة"
        ]

        score = score_line(
            event,
            match
        )

        if score:
            lines.append(score)

        if hashtag:
            lines.append(hashtag)

        return "\n".join(lines)


    return ""


# ============================================================
# GET EVENTS
# ============================================================

def get_events():

    params = {

        "select": (
            "id,"
            "match_id,"
            "source,"
            "source_event_key,"
            "event_type,"
            "minute,"
            "extra_time,"
            "team_id,"
            "team_name,"
            "player_id,"
            "player_name,"
            "assist_player_id,"
            "assist_player_name,"
            "player_out_id,"
            "player_out_name,"
            "player_in_id,"
            "player_in_name,"
            "card,"
            "home_score,"
            "away_score"
        ),

        "source": "eq.espn",

        "order": "id.asc",

        "limit": "200",
    }

    events = supabase_request(
        "GET",
        "match_events",
        params=params,
    )

    return [
        event
        for event in events
        if event.get("event_type")
        in PUBLISHABLE_EVENTS
    ]


# ============================================================
# GET SENT EVENTS
# ============================================================

def get_sent_event_ids(event_ids):

    if not event_ids:
        return set()

    ids = ",".join(
        str(event_id)
        for event_id in event_ids
    )

    rows = supabase_request(

        "GET",

        "news_events",

        params={
            "select": "match_event_id,channel",

            "channel":
                f"eq.{EVENT_CHANNEL}",

            "match_event_id":
                f"in.({ids})",
        },
    )

    return {
        str(row["match_event_id"])
        for row in rows
        if row.get("match_event_id") is not None
    }


# ============================================================
# GET MATCHES
# ============================================================

def get_matches(match_ids):

    if not match_ids:
        return {}

    ids = ",".join(
        str(value)
        for value in match_ids
    )

    rows = supabase_request(

        "GET",

        "matches",

        params={

            "select": (
                "id,"
                "source_match_id,"
                "home_team_name,"
                "away_team_name,"
                "home_team_db_id,"
                "away_team_db_id,"
                "home_score,"
                "away_score,"
                "status,"
                "kickoff_local,"
                "competition_name"
            ),

            "id":
                f"in.({ids})",
        },
    )

    return {
        str(row["id"]): row
        for row in rows
    }


# ============================================================
# أسماء الفرق بالعربي (عن طريق id الداخلي في teams)
# ============================================================

def get_teams_ar_by_id(team_db_ids):

    if not team_db_ids:
        return {}

    ids = ",".join(
        str(value)
        for value in team_db_ids
    )

    rows = supabase_request(
        "GET",
        "teams",
        params={
            "select": "id,name,name_ar",
            "id": f"in.({ids})",
        },
    )

    return {
        str(row["id"]): row
        for row in rows
    }


# ============================================================
# أسماء الفرق بالعربي (عن طريق source_team_id من ESPN)
# ============================================================

def get_teams_ar_by_source(source_team_ids):

    if not source_team_ids:
        return {}

    ids = ",".join(
        str(value)
        for value in source_team_ids
    )

    rows = supabase_request(
        "GET",
        "teams",
        params={
            "select": "source_team_id,name,name_ar",
            "source": "eq.espn",
            "source_team_id": f"in.({ids})",
        },
    )

    return {
        str(row["source_team_id"]): row
        for row in rows
    }


# ============================================================
# إضافة الأسماء العربية للمباريات (فريق مضيف / ضيف / البطولة)
# ============================================================

def attach_match_display_names(matches):

    team_db_ids = set()

    for match in matches.values():

        if match.get("home_team_db_id") is not None:
            team_db_ids.add(match["home_team_db_id"])

        if match.get("away_team_db_id") is not None:
            team_db_ids.add(match["away_team_db_id"])

    teams_ar = get_teams_ar_by_id(team_db_ids)

    for match in matches.values():

        home_team = teams_ar.get(
            str(match.get("home_team_db_id"))
        )

        away_team = teams_ar.get(
            str(match.get("away_team_db_id"))
        )

        match["home_team_display"] = resolve_name(
            match.get("home_team_name"),
            home_team.get("name_ar") if home_team else None,
        )

        match["away_team_display"] = resolve_name(
            match.get("away_team_name"),
            away_team.get("name_ar") if away_team else None,
        )

        match["competition_name_display"] = (
            COMPETITION_NAMES_AR.get(
                match.get("competition_name"),
                match.get("competition_name"),
            )
        )


# ============================================================
# إضافة الاسم العربي لفريق الحدث (team_id في match_events)
# ============================================================

def attach_event_team_display(events):

    source_ids = {
        event["team_id"]
        for event in events
        if event.get("team_id")
    }

    teams_ar = get_teams_ar_by_source(source_ids)

    for event in events:

        team = teams_ar.get(
            str(event.get("team_id"))
        )

        event["team_display"] = resolve_name(
            event.get("team_name"),
            team.get("name_ar") if team else None,
        )


# ============================================================
# DUPLICATE PROTECTION
#
# IMPORTANT:
# We reserve the event BEFORE sending it.
#
# This prevents:
# Run A -> send
# Run B -> send
#
# when two GitHub/cron executions overlap.
# ============================================================

def reserve_event(event_id):

    record = {
        "match_event_id": event_id,
        "channel": EVENT_CHANNEL,
        "sent_at": datetime.now(
            TIMEZONE
        ).isoformat(),
    }

    try:

        supabase_request(

            "POST",

            "news_events",

            json_body=[record],

            extra_headers={
                "Prefer":
                    "return=minimal"
            },
        )

        log(
            f"Event reserved: {event_id}"
        )

        return True


    except Exception as error:

        error_text = str(error)

        # Unique constraint means another run
        # already reserved/sent this event.

        if (
            "409" in error_text
            or
            "duplicate" in error_text.lower()
            or
            "unique" in error_text.lower()
        ):

            log(
                f"SKIP duplicate event: {event_id}"
            )

            return False

        raise


# ============================================================
# REMOVE RESERVATION AFTER FAILED TELEGRAM SEND
# ============================================================

def remove_event_reservation(event_id):

    try:

        supabase_request(

            "DELETE",

            "news_events",

            params={
                "match_event_id":
                    f"eq.{event_id}",

                "channel":
                    f"eq.{EVENT_CHANNEL}",
            },

        )

        log(
            f"Reservation removed: {event_id}"
        )

    except Exception as error:

        log(
            f"WARNING: could not remove "
            f"reservation event={event_id}: "
            f"{error}"
        )


# ============================================================
# SEND EVENT
# ============================================================

def send_event(event, match):

    event_id = event.get("id")

    if not event_id:
        return False

    event_type = event.get(
        "event_type"
    )

    if event_type not in PUBLISHABLE_EVENTS:
        return False

    if event_type in IGNORED_EVENTS:
        return False


    # --------------------------------------------------------
    # RESERVE FIRST
    # --------------------------------------------------------

    reserved = reserve_event(
        event_id
    )

    if not reserved:
        return False


    # --------------------------------------------------------
    # BUILD MESSAGE
    # --------------------------------------------------------

    message = build_event_message(
        event,
        match
    )

    if not message:
        remove_event_reservation(
            event_id
        )

        log(
            f"Empty message event={event_id}"
        )

        return False


    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    try:

        log(
            f"Sending event={event_id} "
            f"type={event_type}"
        )

        telegram_request(

            "sendMessage",

            {
                "chat_id":
                    TELEGRAM_CHAT_ID,

                "text":
                    message,

                "disable_web_page_preview":
                    True,
            },
        )

        log(
            f"Telegram sent event={event_id}"
        )

        return True


    except Exception:

        # Telegram failed.
        # Remove reservation so next run
        # can retry safely.

        remove_event_reservation(
            event_id
        )

        raise


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log(
        "=================================================="
    )

    log(
        "TELEGRAM EVENT PUBLISHER START"
    )

    log(
        "Supabase -> Python -> Telegram"
    )

    log(
        "=================================================="
    )


    # --------------------------------------------------------
    # GET EVENTS
    # --------------------------------------------------------

    events = get_events()

    if not events:

        log(
            "No events found."
        )

        log(
            "TELEGRAM EVENT PUBLISHER END"
        )

        return


    log(
        f"Events found: {len(events)}"
    )


    # --------------------------------------------------------
    # REMOVE ALREADY SENT EVENTS
    # --------------------------------------------------------

    event_ids = [
        event["id"]
        for event in events
        if event.get("id") is not None
    ]

    sent_ids = get_sent_event_ids(
        event_ids
    )

    events = [
        event
        for event in events
        if str(event["id"])
        not in sent_ids
    ]


    if not events:

        log(
            "No unpublished events."
        )

        log(
            "TELEGRAM EVENT PUBLISHER END"
        )

        return


    log(
        f"Unpublished events: {len(events)}"
    )


    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

    match_ids = list({

        event["match_id"]

        for event in events

        if event.get("match_id") is not None

    })

    matches = get_matches(
        match_ids
    )

    attach_match_display_names(
        matches
    )

    attach_event_team_display(
        events
    )


    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    sent = 0
    failed = 0
    skipped = 0


    for event in events:

        event_id = event.get("id")

        match_id = event.get(
            "match_id"
        )

        match = matches.get(
            str(match_id)
        )


        if not match:

            log(
                f"SKIP event={event_id}: "
                f"match not found"
            )

            skipped += 1

            continue


        try:

            result = send_event(
                event,
                match
            )

            if result:

                sent += 1

            else:

                skipped += 1


        except Exception as error:

            failed += 1

            log(
                f"ERROR event={event_id}: "
                f"{error}"
            )

            # لا نوقف باقي الأحداث
            continue


    # --------------------------------------------------------
    # FINAL LOG
    # --------------------------------------------------------

    log(
        "=================================================="
    )

    log(
        f"Sent: {sent}"
    )

    log(
        f"Failed: {failed}"
    )

    log(
        f"Skipped: {skipped}"
    )

    log(
        "TELEGRAM EVENT PUBLISHER END"
    )

    log(
        "=================================================="
    )


    if failed:

        raise RuntimeError(
            f"{failed} event(s) failed"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
