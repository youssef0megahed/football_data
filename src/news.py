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


# ============================================================
# SUPABASE HEADERS
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# ENVIRONMENT CHECK
# ============================================================

def check_environment():

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
# CURRENT DATE / TIME
# ============================================================

def get_dates():

    now = datetime.now(TIMEZONE)

    today = now.date()

    tomorrow = today + timedelta(days=1)

    return now, today, tomorrow


# ============================================================
# GET TODAY + TOMORROW MATCHES
# ============================================================

def get_target_matches():

    _, today, tomorrow = get_dates()

    today_start = datetime(
        today.year,
        today.month,
        today.day,
        0,
        0,
        0,
        tzinfo=TIMEZONE
    )

    tomorrow_end = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        23,
        59,
        59,
        tzinfo=TIMEZONE
    )

    url = f"{SUPABASE_URL}/rest/v1/matches"

    params = {

        "kickoff_local":
            f"gte.{today_start.isoformat()}",

        "and":
            f"(kickoff_local.lte.{tomorrow_end.isoformat()})",

        "select":
            "id,competition_name,"
            "home_team_name,away_team_name,"
            "home_score,away_score,"
            "status,kickoff_local,venue",

        "order":
            "kickoff_local.asc"
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            "Failed to get matches: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# GET NEWS STATE
# ============================================================

def get_news_state(match_id):

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"match_news_state"
    )

    params = {

        "match_id":
            f"eq.{match_id}",

        "select":
            "id,match_id,last_status,"
            "last_home_score,last_away_score,"
            "initialized",

        "limit":
            "1"
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            "Failed to get news state: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not data:
        return None

    return data[0]


# ============================================================
# CREATE INITIAL STATE
# ============================================================

def create_initial_state(match):

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"match_news_state"
    )

    payload = {

        "match_id":
            match["id"],

        "last_status":
            match["status"],

        "last_home_score":
            match["home_score"],

        "last_away_score":
            match["away_score"],

        "initialized":
            True
    }

    headers = {
        **SUPABASE_HEADERS,
        "Prefer":
            "return=representation"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code not in [200, 201]:

        raise Exception(
            "Failed to create initial state: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()[0]


# ============================================================
# UPDATE STATE
# ============================================================

def update_news_state(
    match,
    state_id=None
):

    url = (
        f"{SUPABASE_URL}/rest/v1/"
        f"match_news_state"
    )

    payload = {

        "last_status":
            match["status"],

        "last_home_score":
            match["home_score"],

        "last_away_score":
            match["away_score"],

        "initialized":
            True,

        "updated_at":
            datetime.now(TIMEZONE).isoformat()
    }

    if state_id:

        params = {
            "id":
                f"eq.{state_id}"
        }

        response = requests.patch(
            url,
            headers=SUPABASE_HEADERS,
            params=params,
            json=payload,
            timeout=30
        )

    else:

        payload["match_id"] = match["id"]

        headers = {
            **SUPABASE_HEADERS,
            "Prefer":
                "return=representation"
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

    if response.status_code not in [200, 201, 204]:

        raise Exception(
            "Failed to update news state: "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# CHECK EXISTING NEWS
# ============================================================

def news_exists(
    match_id,
    news_type
):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    params = {

        "match_id":
            f"eq.{match_id}",

        "news_type":
            f"eq.{news_type}",

        "select":
            "id",

        "limit":
            "1"
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            "Failed to check news: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return len(response.json()) > 0


# ============================================================
# CREATE NEWS RECORD
# ============================================================

def create_news_record(
    match,
    news_type,
    title,
    content
):

    if news_exists(
        match["id"],
        news_type
    ):

        print(
            f"News already exists: "
            f"{news_type}"
        )

        return None

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    payload = {

        "match_id":
            match["id"],

        "news_type":
            news_type,

        "title":
            title,

        "content":
            content,

        "telegram_sent":
            False
    }

    headers = {
        **SUPABASE_HEADERS,
        "Prefer":
            "return=representation"
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    if response.status_code not in [200, 201]:

        raise Exception(
            "Failed to create news record: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()[0]


# ============================================================
# SEND TELEGRAM
# ============================================================

def send_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/"
        f"sendMessage"
    )

    payload = {

        "chat_id":
            TELEGRAM_CHAT_ID,

        "text":
            text
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            "Telegram HTTP error: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not data.get("ok"):

        raise Exception(
            f"Telegram API error: {data}"
        )

    return data["result"]["message_id"]


# ============================================================
# MARK NEWS AS SENT
# ============================================================

def mark_news_as_sent(
    news_id,
    telegram_message_id
):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    params = {

        "id":
            f"eq.{news_id}"
    }

    payload = {

        "telegram_sent":
            True,

        "telegram_message_id":
            telegram_message_id,

        "published_at":
            datetime.now(TIMEZONE).isoformat()
    }

    response = requests.patch(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        json=payload,
        timeout=30
    )

    if response.status_code not in [200, 204]:

        raise Exception(
            "Failed to mark news as sent: "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# FORMAT KICKOFF TIME
# ============================================================

def format_kickoff(kickoff):

    dt = datetime.fromisoformat(
        kickoff.replace("Z", "+00:00")
    )

    dt = dt.astimezone(TIMEZONE)

    return dt.strftime("%H:%M")


# ============================================================
# GET MATCH DAY
# ============================================================

def get_match_day(kickoff):

    _, today, tomorrow = get_dates()

    dt = datetime.fromisoformat(
        kickoff.replace("Z", "+00:00")
    )

    dt = dt.astimezone(TIMEZONE)

    if dt.date() == today:
        return "اليوم"

    if dt.date() == tomorrow:
        return "غدًا"

    return "لاحقًا"


# ============================================================
# BUILD SCHEDULED NEWS
# ============================================================

def build_scheduled_news(match):

    home = match["home_team_name"]

    away = match["away_team_name"]

    competition = match["competition_name"]

    kickoff = format_kickoff(
        match["kickoff_local"]
    )

    day = get_match_day(
        match["kickoff_local"]
    )

    title = (
        f"📅 مباراة {day} | "
        f"{home} × {away}"
    )

    content = (
        f"📅 مباراة {day}\n\n"
        f"🏆 {competition}\n\n"
        f"⚽ {home}\n"
        f"🆚\n"
        f"⚽ {away}\n\n"
        f"⏰ الموعد: {kickoff} "
        f"بتوقيت القاهرة\n\n"
        f"📢 تابعوا المباراة "
        f"والتحديثات أولًا بأول."
    )

    return title, content


# ============================================================
# BUILD STARTED NEWS
# ============================================================

def build_started_news(match):

    home = match["home_team_name"]

    away = match["away_team_name"]

    competition = match["competition_name"]

    title = (
        f"🟢 انطلاق المباراة | "
        f"{home} × {away}"
    )

    content = (
        f"🟢 انطلاق المباراة الآن\n\n"
        f"🏆 {competition}\n\n"
        f"⚽ {home} 0 - 0 {away}\n\n"
        f"بدأت المباراة "
        f"والنتيجة حتى الآن 0-0."
    )

    return title, content


# ============================================================
# BUILD FINISHED NEWS
# ============================================================

def build_finished_news(match):

    home = match["home_team_name"]

    away = match["away_team_name"]

    competition = match["competition_name"]

    home_score = match["home_score"]

    away_score = match["away_score"]

    title = (
        f"🏁 نهاية المباراة | "
        f"{home} {home_score} - "
        f"{away_score} {away}"
    )

    content = (
        f"🏁 نهاية المباراة\n\n"
        f"🏆 {competition}\n\n"
        f"⚽ {home} "
        f"{home_score} - "
        f"{away_score} {away}\n\n"
        f"📊 النتيجة النهائية: "
        f"{home_score} - {away_score}"
    )

    return title, content


# ============================================================
# PROCESS INITIAL SYNC
# ============================================================

def initialize_match(match):

    print(
        f"INITIAL SYNC: "
        f"{match['home_team_name']} "
        f"vs "
        f"{match['away_team_name']}"
    )

    create_initial_state(match)

    print(
        f"Saved initial status: "
        f"{match['status']}"
    )


# ============================================================
# PROCESS MATCH CHANGES
# ============================================================

def process_match(match, state):

    current_status = match["status"]

    previous_status = state["last_status"]

    match_id = match["id"]

    print(
        f"Previous: {previous_status} "
        f"→ Current: {current_status}"
    )

    # --------------------------------------------------------
    # No status change
    # --------------------------------------------------------

    if previous_status == current_status:

        return False


    # --------------------------------------------------------
    # TIMED → IN_PLAY
    # --------------------------------------------------------

    if current_status in [
        "IN_PLAY",
        "PAUSED"
    ]:

        news_type = "MATCH_STARTED"

        title, content = build_started_news(
            match
        )

    # --------------------------------------------------------
    # ANY → FINISHED
    # --------------------------------------------------------

    elif current_status == "FINISHED":

        news_type = "MATCH_FINISHED"

        title, content = build_finished_news(
            match
        )

    # --------------------------------------------------------
    # OTHER STATUS
    # --------------------------------------------------------

    else:

        print(
            f"Status changed but no news rule: "
            f"{previous_status} → {current_status}"
        )

        update_news_state(
            match,
            state["id"]
        )

        return False


    # --------------------------------------------------------
    # CREATE NEWS
    # --------------------------------------------------------

    news = create_news_record(
        match,
        news_type,
        title,
        content
    )

    if not news:

        update_news_state(
            match,
            state["id"]
        )

        return False


    print(
        f"News created: {news['id']}"
    )


    # --------------------------------------------------------
    # SEND TELEGRAM
    # --------------------------------------------------------

    try:

        telegram_message_id = send_telegram(
            content
        )

        mark_news_as_sent(
            news["id"],
            telegram_message_id
        )

        print(
            "Telegram: SENT ✅"
        )

    except Exception as error:

        print(
            "Telegram: FAILED ❌"
        )

        print(error)

        # مهم:
        # لا نحدّث الحالة هنا.
        # حتى يستطيع التشغيل القادم إعادة المحاولة.

        return False


    # --------------------------------------------------------
    # UPDATE STATE ONLY AFTER SUCCESS
    # --------------------------------------------------------

    update_news_state(
        match,
        state["id"]
    )

    print(
        f"State updated for match {match_id}"
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)

    print(
        "FOOTBALL NEWS ENGINE"
    )

    print("=" * 70)

    check_environment()

    now, today, tomorrow = get_dates()

    print(
        f"Timezone : Africa/Cairo"
    )

    print(
        f"Now      : "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Today    : {today}"
    )

    print(
        f"Tomorrow : {tomorrow}"
    )

    print("=" * 70)


    matches = get_target_matches()

    print(
        f"Matches found: {len(matches)}"
    )


    initialized = 0

    changed = 0

    skipped = 0


    # ========================================================
    # PROCESS MATCHES
    # ========================================================

    for match in matches:

        print("")

        print("-" * 70)

        print(
            f"🏆 {match['competition_name']}"
        )

        print(
            f"{match['home_team_name']} "
            f"vs "
            f"{match['away_team_name']}"
        )

        print(
            f"Status: {match['status']}"
        )


        # ----------------------------------------------------
        # Get previous state
        # ----------------------------------------------------

        state = get_news_state(
            match["id"]
        )


        # ----------------------------------------------------
        # INITIAL SYNC
        # ----------------------------------------------------

        if state is None:

            initialize_match(
                match
            )

            initialized += 1

            continue


        # ----------------------------------------------------
        # Process changes
        # ----------------------------------------------------

        if process_match(
            match,
            state
        ):

            changed += 1

        else:

            skipped += 1


    # ========================================================
    # SUMMARY
    # ========================================================

    print("")

    print("=" * 70)

    print(
        "FINAL SUMMARY"
    )

    print("=" * 70)

    print(
        f"Matches checked : {len(matches)}"
    )

    print(
        f"Initialized     : {initialized}"
    )

    print(
        f"News sent       : {changed}"
    )

    print(
        f"Skipped         : {skipped}"
    )

    print("=" * 70)


if __name__ == "__main__":

    main()
