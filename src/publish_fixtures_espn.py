import os
import time
import requests

from datetime import datetime
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)

TIMEZONE = ZoneInfo(
    "Africa/Cairo"
)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

CHANNEL = "telegram"


# ============================================================
# EVENTS ALLOWED FOR PUBLISHING
# ============================================================

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


# ============================================================
# EVENTS THAT MUST NEVER BE PUBLISHED
# ============================================================

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
# LOGGING
# ============================================================

def log(message):

    now = datetime.now(
        TIMEZONE
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{now} Cairo] {message}",
        flush=True
    )


# ============================================================
# ENVIRONMENT VALIDATION
# ============================================================

def validate_environment():

    required = {

        "SUPABASE_URL":
            SUPABASE_URL,

        "SUPABASE_KEY":
            SUPABASE_KEY,

        "TELEGRAM_BOT_TOKEN":
            TELEGRAM_BOT_TOKEN,

        "TELEGRAM_CHAT_ID":
            TELEGRAM_CHAT_ID,

    }

    missing = [

        name

        for name, value
        in required.items()

        if not value

    ]

    if missing:

        raise RuntimeError(

            "Missing environment variables: "
            + ", ".join(missing)

        )


# ============================================================
# RETRY / EXPONENTIAL BACKOFF
# ============================================================

def retry_call(
    operation,
    label,
):

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            return operation()

        except Exception as error:

            last_error = error

            if attempt >= MAX_RETRIES:

                break

            delay = (
                2 ** (attempt - 1)
            )

            log(
                f"{label} failed "
                f"({attempt}/{MAX_RETRIES}): "
                f"{error}"
            )

            log(
                f"Retrying in {delay}s..."
            )

            time.sleep(
                delay
            )

    raise RuntimeError(

        f"{label} failed after "
        f"{MAX_RETRIES} attempts: "
        f"{last_error}"

    )


# ============================================================
# SUPABASE
# ============================================================

SUPABASE_HEADERS = {

    "apikey":
        SUPABASE_KEY,

    "Authorization":
        f"Bearer {SUPABASE_KEY}",

    "Content-Type":
        "application/json",

}


def supabase_request(

    method,

    table,

    params=None,

    json_body=None,

):

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/{table}"
    )

    def request():

        response = requests.request(

            method,

            url,

            headers=SUPABASE_HEADERS,

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
                f"{response.status_code}"

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

def telegram_request(
    method,
    payload,
):

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

            if not data.get(
                "ok",
                False
            ):

                raise RuntimeError(
                    str(data)
                )

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

def format_minute(
    minute,
    extra_time,
):

    if minute is None:

        return ""

    if extra_time:

        return (
            f"{minute}+"
            f"{extra_time}'"
        )

    return f"{minute}'"


def get_raw_event(
    event,
):

    raw = event.get(
        "raw_event"
    )

    if isinstance(
        raw,
        dict
    ):

        return raw

    return {}


# ============================================================
# MATCH SCORE
# ============================================================

def get_score(
    event,
    match,
):

    home_score = (
        event.get(
            "home_score"
        )
    )

    away_score = (
        event.get(
            "away_score"
        )
    )

    if home_score is None:

        home_score = match.get(
            "home_score"
        )

    if away_score is None:

        away_score = match.get(
            "away_score"
        )

    if (
        home_score is None
        or
        away_score is None
    ):

        return None

    return (
        home_score,
        away_score
    )


def score_line(
    event,
    match,
):

    score = get_score(
        event,
        match
    )

    if not score:

        return ""

    home = (
        match.get(
            "home_team_name"
        )
        or
        "الفريق الأول"
    )

    away = (
        match.get(
            "away_team_name"
        )
        or
        "الفريق الثاني"
    )

    home_score, away_score = score

    return (
        f"📊 {home} "
        f"{home_score} - "
        f"{away_score} {away}"
    )


# ============================================================
# SUBSTITUTION PLAYERS
# ============================================================

def get_substitution_players(
    event,
):

    player_out = (
        event.get(
            "player_out_name"
        )
        or ""
    )

    player_in = (
        event.get(
            "player_in_name"
        )
        or ""
    )

    if player_out or player_in:

        return (
            player_out,
            player_in
        )

    raw = get_raw_event(
        event
    )

    # --------------------------------------------------------
    # Explicit ESPN fields
    # --------------------------------------------------------

    out_value = (

        raw.get(
            "playerOut"
        )

        or

        raw.get(
            "athleteOut"
        )

        or

        raw.get(
            "substitutionOut"
        )

    )

    in_value = (

        raw.get(
            "playerIn"
        )

        or

        raw.get(
            "athleteIn"
        )

        or

        raw.get(
            "substitutionIn"
        )

    )

    def name(value):

        if not isinstance(
            value,
            dict
        ):

            return str(
                value or ""
            )

        return (

            value.get(
                "displayName"
            )

            or

            value.get(
                "fullName"
            )

            or

            value.get(
                "shortName"
            )

            or

            value.get(
                "name"
            )

            or ""

        )

    player_out = name(
        out_value
    )

    player_in = name(
        in_value
    )

    if player_out or player_in:

        return (
            player_out,
            player_in
        )

    # --------------------------------------------------------
    # athletesInvolved fallback
    # --------------------------------------------------------

    athletes = (

        raw.get(
            "athletesInvolved"
        )
        or []

    )

    if len(athletes) >= 2:

        return (

            name(
                athletes[0]
            ),

            name(
                athletes[1]
            ),

        )

    return (
        "",
        ""
    )


# ============================================================
# MESSAGE GENERATOR
# ============================================================

def build_event_message(
    event,
    match,
):

    event_type = event.get(
        "event_type"
    )

    team = (
        event.get(
            "team_name"
        )
        or ""
    )

    player = (
        event.get(
            "player_name"
        )
        or ""
    )

    assist = (
        event.get(
            "assist_player_name"
        )
        or ""
    )

    minute = format_minute(

        event.get(
            "minute"
        ),

        event.get(
            "extra_time"
        ),

    )

    home = (
        match.get(
            "home_team_name"
        )
        or
        "الفريق الأول"
    )

    away = (
        match.get(
            "away_team_name"
        )
        or
        "الفريق الثاني"
    )

    # ========================================================
    # GOAL
    # ========================================================

    if event_type == "goal":

        lines = [
            "⚽ هدف!",
        ]

        if team:

            lines.append(
                f"🏟️ {team}"
            )

        if player:

            lines.append(
                f"👤 {player}"
            )

        if assist:

            lines.append(
                f"🎯 أسيست: {assist}"
            )

        score = score_line(
            event,
            match
        )

        if score:

            lines.append(
                score
            )

        if minute:

            lines.append(
                f"⏱️ {minute}"
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # YELLOW CARD
    # ========================================================

    if event_type == "yellow_card":

        lines = [
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

        if minute:

            lines.append(
                f"⏱️ {minute}"
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # RED CARD
    # ========================================================

    if event_type == "red_card":

        lines = [
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

        if minute:

            lines.append(
                f"⏱️ {minute}"
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # SUBSTITUTION
    # ========================================================

    if event_type == "substitution":

        player_out, player_in = (
            get_substitution_players(
                event
            )
        )

        lines = [
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

        return "\n".join(
            lines
        )

    # ========================================================
    # VAR
    # ========================================================

    if event_type == "var":

        lines = [
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

        if minute:

            lines.append(
                f"⏱️ {minute}"
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # PENALTY
    # ========================================================

    if event_type == "penalty":

        lines = [
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

        if minute:

            lines.append(
                f"⏱️ {minute}"
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # KICKOFF
    # ========================================================

    if event_type == "kickoff":

        return (
            "🟢 بداية المباراة\n"
            f"{home} × {away}"
        )

    # ========================================================
    # SECOND HALF
    # ========================================================

    if event_type == "start_2nd_half":

        return (
            "▶️ بداية الشوط الثاني\n"
            f"{home} × {away}"
        )

    # ========================================================
    # HALF TIME
    # ========================================================

    if event_type == "halftime":

        score = score_line(
            event,
            match
        )

        lines = [
            "⏸️ نهاية الشوط الأول"
        ]

        if score:

            lines.append(
                score
            )

        return "\n".join(
            lines
        )

    # ========================================================
    # FULL TIME
    # ========================================================

    if event_type == "fulltime":

        score = score_line(
            event,
            match
        )

        lines = [
            "🏁 نهاية المباراة"
        ]

        if score:

            lines.append(
                score
            )

        return "\n".join(
            lines
        )

    return ""


# ============================================================
# GET UNPUBLISHED EVENTS
# ============================================================

def get_unpublished_events():

    params = {

        "select":
            (
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
                "away_score,"
                "raw_event"
            ),

        "source":
            "eq.espn",

        "order":
            "id.asc",

        "limit":
            "100",

    }

    events = supabase_request(

        "GET",

        "match_events",

        params

    )

    if not events:

        return []

    # --------------------------------------------------------
    # ONLY REAL PUBLISHABLE EVENTS
    # --------------------------------------------------------

    events = [

        event

        for event in events

        if (

            event.get(
                "event_type"
            )

            in

            PUBLISHABLE_EVENTS

        )

        and (

            event.get(
                "event_type"
            )

            not in

            IGNORED_EVENTS

        )

    ]

    if not events:

        return []

    # --------------------------------------------------------
    # CHECK news_events
    # --------------------------------------------------------

    event_ids = [

        str(
            event["id"]
        )

        for event in events

        if event.get(
            "id"
        ) is not None

    ]

    if not event_ids:

        return []

    sent_rows = supabase_request(

        "GET",

        "news_events",

        {

            "select":
                "match_event_id,channel",

            "channel":
                f"eq.{CHANNEL}",

            "match_event_id":
                "in.("
                + ",".join(
                    event_ids
                )
                + ")",

        },

    )

    sent_ids = {

        str(
            row[
                "match_event_id"
            ]
        )

        for row in sent_rows

        if row.get(
            "match_event_id"
        ) is not None

    }

    unpublished = [

        event

        for event in events

        if str(
            event["id"]
        )
        not in sent_ids

    ]

    return unpublished


# ============================================================
# GET MATCHES
# ============================================================

def get_matches(
    match_ids,
):

    if not match_ids:

        return {}

    ids = ",".join(

        str(
            value
        )

        for value in match_ids

    )

    rows = supabase_request(

        "GET",

        "matches",

        {

            "select":
                (
                    "id,"
                    "source_match_id,"
                    "home_team_name,"
                    "away_team_name,"
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

        str(
            row["id"]
        ):
            row

        for row in rows

    }


# ============================================================
# LOG SENT EVENT
# ============================================================

def log_sent_event(
    event,
):

    event_id = event.get(
        "id"
    )

    if event_id is None:

        raise RuntimeError(
            "Event has no database ID"
        )

    record = {

        "match_event_id":
            event_id,

        "channel":
            CHANNEL,

        "sent_at":
            datetime.now(
                TIMEZONE
            ).isoformat(),

    }

    # --------------------------------------------------------
    # The database UNIQUE constraint is the final protection
    # against duplicate publishing records.
    # --------------------------------------------------------

    try:

        supabase_request(

            "POST",

            "news_events",

            {
                "on_conflict":
                    "match_event_id,channel"
            },

            [record],

        )

    except Exception as error:

        # Message was already sent successfully.
        # Do not resend it because logging failed.

        log(
            f"WARNING: Telegram sent "
            f"but news_events logging "
            f"failed for event={event_id}: "
            f"{error}"
        )

        raise


# ============================================================
# PROCESS ONE EVENT
# ============================================================

def process_event(
    event,
    match,
):

    event_id = event.get(
        "id"
    )

    event_type = event.get(
        "event_type"
    )

    # --------------------------------------------------------
    # SAFETY FILTER
    # --------------------------------------------------------

    if event_type not in (
        PUBLISHABLE_EVENTS
    ):

        log(

            f"SKIP unsupported event "
            f"id={event_id} "
            f"type={event_type}"

        )

        return False

    if event_type in (
        IGNORED_EVENTS
    ):

        log(

            f"SKIP ignored event "
            f"id={event_id} "
            f"type={event_type}"

        )

        return False

    # --------------------------------------------------------
    # BUILD MESSAGE
    # --------------------------------------------------------

    message = build_event_message(

        event,

        match,

    )

    if not message.strip():

        log(

            f"SKIP empty message "
            f"id={event_id} "
            f"type={event_type}"

        )

        return False

    # --------------------------------------------------------
    # SEND TELEGRAM
    # --------------------------------------------------------

    log(

        f"Publishing event "
        f"id={event_id} "
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
        f"Telegram sent "
        f"event={event_id}"
    )

    # --------------------------------------------------------
    # LOG AFTER SUCCESSFUL SEND
    # --------------------------------------------------------

    log_sent_event(
        event
    )

    log(
        f"news_events logged "
        f"event={event_id}"
    )

    return True


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
        "Architecture: "
        "Supabase -> Python -> Telegram"
    )

    log(
        "=================================================="
    )

    # --------------------------------------------------------
    # GET NEW EVENTS
    # --------------------------------------------------------

    events = get_unpublished_events()

    if not events:

        log(
            "No unpublished "
            "publishable events."
        )

        log(
            "TELEGRAM EVENT PUBLISHER END"
        )

        return

    log(
        f"Unpublished events: "
        f"{len(events)}"
    )

    # --------------------------------------------------------
    # GET MATCH DATA
    # --------------------------------------------------------

    match_ids = list({

        event["match_id"]

        for event in events

        if event.get(
            "match_id"
        ) is not None

    })

    matches = get_matches(
        match_ids
    )

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    sent = 0
    failed = 0
    skipped = 0

    for event in events:

        event_id = event.get(
            "id"
        )

        match = matches.get(
            str(
                event.get(
                    "match_id"
                )
            )
        )

        if not match:

            log(

                f"SKIP event={event_id}: "
                "match not found"

            )

            skipped += 1

            continue

        try:

            result = process_event(

                event,

                match,

            )

            if result:

                sent += 1

            else:

                skipped += 1

        except Exception as error:

            failed += 1

            log(

                f"ERROR publishing "
                f"event={event_id}: "
                f"{error}"

            )

            # ------------------------------------------------
            # Continue with other events.
            # One Telegram/Supabase failure must not stop
            # the complete publishing cycle.
            # ------------------------------------------------

            continue

    # ========================================================
    # FINAL LOG
    # ========================================================

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

    # --------------------------------------------------------
    # Workflow should report failure if events failed,
    # so GitHub Actions / cron monitoring can detect it.
    # --------------------------------------------------------

    if failed:

        raise RuntimeError(

            f"{failed} event(s) "
            "failed to publish"

        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
