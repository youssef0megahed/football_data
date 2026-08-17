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
# ENVIRONMENT
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
# RETRY
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
                f"Retrying in {delay}s"
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

                f"Supabase transient "
                f"HTTP {response.status_code}"

            )

        raise RuntimeError(

            f"Supabase HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"

        )

    return retry_call(

        request,

        f"Supabase {method} {table}"

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
        f"{TELEGRAM_BOT_TOKEN}/"
        f"{method}"

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

                f"Telegram transient "
                f"HTTP {response.status_code}"

            )

        raise RuntimeError(

            f"Telegram HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"

        )

    return retry_call(

        request,

        f"Telegram {method}"

    )


# ============================================================
# FETCH UNPUBLISHED EVENTS
# ============================================================

def get_unpublished_events():

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

        params,

    )

    if not events:

        return []

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

    # --------------------------------------------------------
    # Get events already published to this channel.
    # --------------------------------------------------------

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
        ) not in sent_ids

    ]

    return unpublished


# ============================================================
# MATCH DATA
# ============================================================

def get_matches(
    match_ids,
):

    if not match_ids:

        return {}

    ids = ",".join(

        str(value)

        for value in match_ids

    )

    rows = supabase_request(

        "GET",

        "matches",

        {

            "select": (
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
# FORMAT MINUTE
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

    return (
        f"{minute}'"
    )


# ============================================================
# EVENT EMOJI
# ============================================================

def event_prefix(
    event_type,
):

    prefixes = {

        "goal":
            "⚽",

        "yellow_card":
            "🟨",

        "red_card":
            "🟥",

        "substitution":
            "🔄",

        "var":
            "📺",

        "penalty":
            "⚽",

        "kickoff":
            "🟢",

        "start_2nd_half":
            "▶️",

        "halftime":
            "⏸️",

        "fulltime":
            "🔴",

    }

    return prefixes.get(
        event_type,
        "📢"
    )


# ============================================================
# MESSAGE GENERATION
# ============================================================

def build_event_message(
    event,
    match,
):

    event_type = event.get(
        "event_type"
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

    competition = (
        match.get(
            "competition_name"
        )
        or
        ""
    )

    minute = format_minute(

        event.get(
            "minute"
        ),

        event.get(
            "extra_time"
        ),

    )

    player = (
        event.get(
            "player_name"
        )
        or
        ""
    )

    assist = (
        event.get(
            "assist_player_name"
        )
        or
        ""
    )

    team = (
        event.get(
            "team_name"
        )
        or
        ""
    )

    home_score = event.get(
        "home_score"
    )

    away_score = event.get(
        "away_score"
    )

    # --------------------------------------------------------
    # GOAL
    # --------------------------------------------------------

    if event_type == "goal":

        text = (
            f"⚽ هدف!"
            f"\n{team}"
        )

        if player:

            text += (
                f"\n👤 {player}"
            )

        if assist:

            text += (
                f"\n🎯 أسيست: {assist}"
            )

        if (
            home_score is not None
            and
            away_score is not None
        ):

            text += (

                f"\n📊 "
                f"{home} "
                f"{home_score} - "
                f"{away_score} "
                f"{away}"

            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # YELLOW CARD
    # --------------------------------------------------------

    if event_type == "yellow_card":

        text = (
            f"🟨 بطاقة صفراء"
            f"\n{team}"
        )

        if player:

            text += (
                f"\n👤 {player}"
            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # RED CARD
    # --------------------------------------------------------

    if event_type == "red_card":

        text = (
            f"🟥 بطاقة حمراء"
            f"\n{team}"
        )

        if player:

            text += (
                f"\n👤 {player}"
            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # SUBSTITUTION
    # --------------------------------------------------------

    if event_type == "substitution":

        player_out = (
            event.get(
                "player_out_name"
            )
            or
            ""
        )

        player_in = (
            event.get(
                "player_in_name"
            )
            or
            ""
        )

        text = (
            f"🔄 تبديل"
            f"\n{team}"
        )

        if player_out:

            text += (
                f"\n⬅️ خروج: "
                f"{player_out}"
            )

        if player_in:

            text += (
                f"\n➡️ دخول: "
                f"{player_in}"
            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # VAR
    # --------------------------------------------------------

    if event_type == "var":

        text = (
            "📺 مراجعة VAR"
        )

        if team:

            text += (
                f"\n{team}"
            )

        if player:

            text += (
                f"\n👤 {player}"
            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # PENALTY
    # --------------------------------------------------------

    if event_type == "penalty":

        text = (
            f"⚽ ركلة جزاء"
            f"\n{team}"
        )

        if player:

            text += (
                f"\n👤 {player}"
            )

        if minute:

            text += (
                f"\n⏱️ {minute}"
            )

        return text

    # --------------------------------------------------------
    # KICKOFF
    # --------------------------------------------------------

    if event_type == "kickoff":

        return (

            f"🟢 بداية المباراة"

            f"\n{home} × {away}"

            + (
                f"\n🏆 {competition}"
                if competition
                else ""
            )

        )

    # --------------------------------------------------------
    # SECOND HALF
    # --------------------------------------------------------

    if event_type == "start_2nd_half":

        return (
            "▶️ بداية الشوط الثاني"
            f"\n{home} × {away}"
        )

    # --------------------------------------------------------
    # HALF TIME
    # --------------------------------------------------------

    if event_type == "halftime":

        score_text = ""

        if (
            home_score is not None
            and
            away_score is not None
        ):

            score_text = (

                f"\n📊 "
                f"{home} "
                f"{home_score} - "
                f"{away_score} "
                f"{away}"

            )

        return (
            "⏸️ نهاية الشوط الأول"
            f"{score_text}"
        )

    # --------------------------------------------------------
    # FULL TIME
    # --------------------------------------------------------

    if event_type == "fulltime":

        score_text = ""

        if (
            home_score is not None
            and
            away_score is not None
        ):

            score_text = (

                f"\n🏁 "
                f"{home} "
                f"{home_score} - "
                f"{away_score} "
                f"{away}"

            )

        return (
            "🔴 نهاية المباراة"
            f"{score_text}"
        )

    # --------------------------------------------------------
    # UNKNOWN EVENT
    # --------------------------------------------------------

    text = (
        f"{event_prefix(event_type)} "
        f"{event_type or 'حدث جديد'}"
    )

    if team:

        text += (
            f"\n{team}"
        )

    if player:

        text += (
            f"\n👤 {player}"
        )

    if minute:

        text += (
            f"\n⏱️ {minute}"
        )

    return text


# ============================================================
# SEND TELEGRAM
# ============================================================

def send_telegram_message(
    text,
):

    payload = {

        "chat_id":
            TELEGRAM_CHAT_ID,

        "text":
            text,

        "disable_web_page_preview":
            True,

    }

    return telegram_request(

        "sendMessage",

        payload,

    )


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

        # IMPORTANT:
        #
        # Telegram was already sent.
        #
        # We must not blindly resend the message,
        # otherwise a Supabase error could create
        # duplicate Telegram posts.
        #
        # Therefore we raise an explicit error and
        # let the workflow report it.

        raise RuntimeError(

            "Telegram message was sent "
            "but logging in news_events failed: "
            f"{error}"

        )


# ============================================================
# PROCESS EVENT
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

    log(

        f"Publishing event "
        f"id={event_id} "
        f"type={event_type}"

    )

    message = build_event_message(

        event,

        match,

    )

    if not message.strip():

        log(
            f"Skipping empty message "
            f"for event {event_id}"
        )

        return False

    # --------------------------------------------------------
    # SEND
    # --------------------------------------------------------

    send_telegram_message(
        message
    )

    log(
        f"Telegram sent "
        f"event={event_id}"
    )

    # --------------------------------------------------------
    # LOG
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
        f"Channel: {CHANNEL}"
    )

    # --------------------------------------------------------
    # GET EVENTS
    # --------------------------------------------------------

    try:

        events = (
            get_unpublished_events()
        )

    except Exception as error:

        log(
            f"ERROR loading events: "
            f"{error}"
        )

        raise

    if not events:

        log(
            "No unpublished events."
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
    # MATCHES
    # --------------------------------------------------------

    match_ids = [

        event[
            "match_id"
        ]

        for event in events

        if event.get(
            "match_id"
        ) is not None

    ]

    matches = get_matches(
        list(
            set(
                match_ids
            )
        )
    )

    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    sent = 0
    failed = 0
    skipped = 0

    for event in events:

        match_id = event.get(
            "match_id"
        )

        match = matches.get(
            str(
                match_id
            )
        )

        if not match:

            log(

                f"Skipping event "
                f"{event.get('id')}: "
                f"match {match_id} "
                f"not found"

            )

            skipped += 1

            continue

        try:

            success = process_event(

                event,

                match,

            )

            if success:

                sent += 1

            else:

                skipped += 1

        except Exception as error:

            failed += 1

            log(

                f"ERROR publishing "
                f"event "
                f"{event.get('id')}: "
                f"{error}"

            )

            # Continue with next event.

            continue

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    log(
        "=================================================="
    )

    log(
        "TELEGRAM EVENT PUBLISHER END"
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
        "=================================================="
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # If anything failed, GitHub Actions should show
    # the run as failed.
    # --------------------------------------------------------

    if failed:

        raise RuntimeError(

            f"{failed} event(s) "
            f"failed to publish"

        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
