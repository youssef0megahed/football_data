import os
import requests


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# ============================================================
# HEADERS
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# CHECK ENVIRONMENT
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
# GET FINISHED MATCHES WITHOUT NEWS
# ============================================================

def get_finished_matches():

    url = (
        f"{SUPABASE_URL}/rest/v1/matches"
    )

    params = {

        "status":
            "eq.FINISHED",

        "select":
            "id,competition_name,home_team_name,"
            "away_team_name,home_score,away_score,"
            "kickoff_local",

        "order":
            "kickoff_local.desc"

    }

    response = requests.get(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        timeout=30

    )

    if response.status_code != 200:

        raise Exception(
            "Failed to get finished matches: "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# CHECK IF NEWS ALREADY EXISTS
# ============================================================

def news_exists(match_id, news_type):

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
# CREATE NEWS
# ============================================================

def create_news(match):

    match_id = match["id"]

    news_type = "MATCH_FINISHED"


    # --------------------------------------------------------
    # Prevent duplicates
    # --------------------------------------------------------

    if news_exists(
        match_id,
        news_type
    ):

        print(
            f"News already exists "
            f"for match {match_id}"
        )

        return None


    home = match["home_team_name"]

    away = match["away_team_name"]

    home_score = match["home_score"]

    away_score = match["away_score"]

    competition = match["competition_name"]


    # --------------------------------------------------------
    # Generate title
    # --------------------------------------------------------

    title = (
        f"🏁 انتهت المباراة | "
        f"{home} {home_score} - "
        f"{away_score} {away}"
    )


    # --------------------------------------------------------
    # Generate content
    # --------------------------------------------------------

    content = (
        f"🏁 انتهت المباراة\n\n"

        f"🏆 {competition}\n\n"

        f"⚽ {home} "
        f"{home_score} - "
        f"{away_score} "
        f"{away}\n\n"

        f"📊 النتيجة النهائية: "
        f"{home_score} - {away_score}"
    )


    # --------------------------------------------------------
    # Save news
    # --------------------------------------------------------

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )


    payload = {

        "match_id":
            match_id,

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


    if response.status_code not in [
        200,
        201
    ]:

        raise Exception(
            "Failed to create news: "
            f"{response.status_code}: "
            f"{response.text}"
        )


    data = response.json()

    return data[0]


# ============================================================
# SEND TELEGRAM
# ============================================================

def send_telegram(
    text
):

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
            "Telegram error: "
            f"{response.status_code}: "
            f"{response.text}"
        )


    data = response.json()


    if not data.get("ok"):

        raise Exception(
            "Telegram returned failure: "
            f"{data}"
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
            "now()"

    }


    response = requests.patch(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        json=payload,

        timeout=30

    )


    if response.status_code not in [
        200,
        204
    ]:

        raise Exception(
            "Failed to mark news as sent: "
            f"{response.status_code}: "
            f"{response.text}"
        )


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


    # --------------------------------------------------------
    # Get finished matches
    # --------------------------------------------------------

    matches = get_finished_matches()


    print(
        f"Finished matches found: "
        f"{len(matches)}"
    )


    created = 0

    sent = 0


    # --------------------------------------------------------
    # Process matches
    # --------------------------------------------------------

    for match in matches:

        print("")

        print(
            f"Match {match['id']}: "
            f"{match['home_team_name']} "
            f"{match['home_score']} - "
            f"{match['away_score']} "
            f"{match['away_team_name']}"
        )


        # ----------------------------------------------------
        # Create news
        # ----------------------------------------------------

        news = create_news(
            match
        )


        if not news:

            continue


        created += 1


        print(
            f"News created: "
            f"{news['id']}"
        )


        # ----------------------------------------------------
        # Send Telegram
        # ----------------------------------------------------

        try:

            telegram_message_id = (
                send_telegram(
                    news["content"]
                )
            )


            mark_news_as_sent(

                news["id"],

                telegram_message_id

            )


            sent += 1


            print(
                "Telegram: SENT ✅"
            )


        except Exception as error:

            print(
                "Telegram: FAILED ❌"
            )

            print(error)


    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("")

    print("=" * 70)

    print("FINAL SUMMARY")

    print("=" * 70)

    print(
        f"Finished matches: "
        f"{len(matches)}"
    )

    print(
        f"News created   : "
        f"{created}"
    )

    print(
        f"Telegram sent  : "
        f"{sent}"
    )

    print("=" * 70)


if __name__ == "__main__":

    main()
