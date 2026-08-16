import os
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


# ============================================================
# SUPABASE HEADERS
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# TELEGRAM URL
# ============================================================

TELEGRAM_URL = (
    f"https://api.telegram.org/bot"
    f"{TELEGRAM_BOT_TOKEN}/sendMessage"
)


# ============================================================
# CURRENT TIME
# ============================================================

def now_cairo():

    return datetime.now(TIMEZONE)


# ============================================================
# GET MATCHES
# ============================================================

def get_matches():

    url = f"{SUPABASE_URL}/rest/v1/matches"

    params = {
        "select": "*",
        "order": "kickoff_local.asc",
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            f"Supabase matches query failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# GET NEWS LOG
# ============================================================

def news_was_sent(match_id, news_type):

    url = f"{SUPABASE_URL}/rest/v1/news_log"

    params = {
        "match_id": f"eq.{match_id}",
        "news_type": f"eq.{news_type}",
        "select": "id",
        "limit": "1",
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:

        raise Exception(
            f"Supabase news_log query failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    return len(data) > 0


# ============================================================
# SAVE NEWS LOG
# ============================================================

def save_news_log(match_id, news_type, message):

    url = f"{SUPABASE_URL}/rest/v1/news_log"

    payload = {
        "match_id": match_id,
        "news_type": news_type,
        "message": message,
    }

    response = requests.post(
        url,
        headers=SUPABASE_HEADERS,
        json=payload,
        timeout=30
    )

    if response.status_code not in [200, 201]:

        raise Exception(
            f"Supabase news_log insert failed "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# SEND TELEGRAM
# ============================================================

def send_telegram(message):

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    response = requests.post(
        TELEGRAM_URL,
        json=payload,
        timeout=30
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
            f"Telegram API error: {data}"
        )


# ============================================================
# FORMAT TIME
# ============================================================

def format_match_time(kickoff_local):

    if not kickoff_local:
        return "غير محدد"

    try:

        dt = datetime.fromisoformat(
            kickoff_local.replace("Z", "+00:00")
        )

        dt = dt.astimezone(TIMEZONE)

        return dt.strftime("%H:%M")

    except Exception:

        return str(kickoff_local)


# ============================================================
# FORMAT DATE
# ============================================================

def format_match_date(kickoff_local):

    if not kickoff_local:
        return ""

    try:

        dt = datetime.fromisoformat(
            kickoff_local.replace("Z", "+00:00")
        )

        dt = dt.astimezone(TIMEZONE)

        return dt.strftime("%Y-%m-%d")

    except Exception:

        return str(kickoff_local)[:10]


# ============================================================
# MATCH SCHEDULE MESSAGE
# ============================================================

def build_schedule_message(match, schedule_type):

    competition = match.get(
        "competition_name",
        "بطولة غير محددة"
    )

    home = match.get(
        "home_team_name",
        "الفريق صاحب الأرض"
    )

    away = match.get(
        "away_team_name",
        "الفريق الضيف"
    )

    kickoff = match.get("kickoff_local")

    match_time = format_match_time(kickoff)

    match_date = format_match_date(kickoff)

    if schedule_type == "MATCH_TODAY":

        title = "📅 مباريات اليوم"

    else:

        title = "📅 مباريات الغد"

    message = f"""
{title}

🏆 {competition}

⚽ {home}
🆚 {away}

⏰ {match_time} بتوقيت القاهرة
📆 {match_date}

#كرة_القدم #Football
""".strip()

    return message


# ============================================================
# MATCH STARTED MESSAGE
# ============================================================

def build_started_message(match):

    competition = match.get(
        "competition_name",
        "بطولة غير محددة"
    )

    home = match.get(
        "home_team_name",
        "الفريق صاحب الأرض"
    )

    away = match.get(
        "away_team_name",
        "الفريق الضيف"
    )

    home_score = match.get("home_score")

    away_score = match.get("away_score")

    if home_score is None:
        home_score = 0

    if away_score is None:
        away_score = 0

    message = f"""
🟢 انطلاق المباراة

🏆 {competition}

⚽ {home}
🆚 {away}

🔢 النتيجة الآن:
{home} {home_score} - {away_score} {away}

📡 نتابع المباراة معكم

#كرة_القدم #مباشر
""".strip()

    return message


# ============================================================
# MATCH FINISHED MESSAGE
# ============================================================

def build_finished_message(match):

    competition = match.get(
        "competition_name",
        "بطولة غير محددة"
    )

    home = match.get(
        "home_team_name",
        "الفريق صاحب الأرض"
    )

    away = match.get(
        "away_team_name",
        "الفريق الضيف"
    )

    home_score = match.get("home_score")

    away_score = match.get("away_score")

    if home_score is None:
        home_score = "-"

    if away_score is None:
        away_score = "-"

    message = f"""
🏁 نهاية المباراة

🏆 {competition}

⚽ {home}
🆚 {away}

🔢 النتيجة النهائية:
{home} {home_score} - {away_score} {away}

#كرة_القدم #نتائج
""".strip()

    return message


# ============================================================
# SEND NEWS IF NOT SENT
# ============================================================

def send_news(match, news_type, message):

    match_id = match["id"]

    if news_was_sent(match_id, news_type):

        return False

    send_telegram(message)

    save_news_log(
        match_id,
        news_type,
        message
    )

    print(
        f"Telegram: SENT | "
        f"Match {match_id} | "
        f"{news_type}"
    )

    return True


# ============================================================
# MAIN NEWS ENGINE
# ============================================================

def main():

    # --------------------------------------------------------
    # Validate environment
    # --------------------------------------------------------

    if not SUPABASE_URL:

        raise Exception(
            "SUPABASE_URL is missing."
        )

    if not SUPABASE_KEY:

        raise Exception(
            "SUPABASE_KEY is missing."
        )

    if not TELEGRAM_BOT_TOKEN:

        raise Exception(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    if not TELEGRAM_CHAT_ID:

        raise Exception(
            "TELEGRAM_CHAT_ID is missing."
        )

    # --------------------------------------------------------
    # Current date
    # --------------------------------------------------------

    now = now_cairo()

    today = now.date()

    tomorrow = today.fromordinal(
        today.toordinal() + 1
    )

    print("=" * 70)
    print("FOOTBALL NEWS ENGINE")
    print("=" * 70)

    print(
        f"Timezone : Africa/Cairo"
    )

    print(
        f"Now      : {now.strftime('%Y-%m-%d %H:%M:%S')}"
    )

    print(
        f"Today    : {today}"
    )

    print(
        f"Tomorrow : {tomorrow}"
    )

    print("=" * 70)

    # --------------------------------------------------------
    # Get matches
    # --------------------------------------------------------

    matches = get_matches()

    print(
        f"Matches found: {len(matches)}"
    )

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    checked = 0

    initialized = 0

    news_sent = 0

    skipped = 0

    # --------------------------------------------------------
    # Process matches
    # --------------------------------------------------------

    for match in matches:

        match_id = match.get("id")

        kickoff_local = match.get(
            "kickoff_local"
        )

        status = match.get(
            "status"
        )

        competition = match.get(
            "competition_name",
            "Unknown"
        )

        home = match.get(
            "home_team_name",
            "Unknown"
        )

        away = match.get(
            "away_team_name",
            "Unknown"
        )

        # ----------------------------------------------------
        # Skip invalid matches
        # ----------------------------------------------------

        if not kickoff_local:

            continue

        try:

            kickoff = datetime.fromisoformat(
                kickoff_local.replace(
                    "Z",
                    "+00:00"
                )
            )

            kickoff = kickoff.astimezone(
                TIMEZONE
            )

        except Exception:

            continue

        match_date = kickoff.date()

        # ----------------------------------------------------
        # Only today / tomorrow / recently finished matches
        # ----------------------------------------------------

        if match_date not in [today, tomorrow]:

            continue

        checked += 1

        print("")
        print("-" * 70)

        print(
            f"🏆 {competition}"
        )

        print(
            f"{home} vs {away}"
        )

        print(
            f"Status: {status}"
        )

        # ====================================================
        # TODAY
        # ====================================================

        if match_date == today:

            message = build_schedule_message(
                match,
                "MATCH_TODAY"
            )

            sent = send_news(
                match,
                "MATCH_TODAY",
                message
            )

            if sent:

                news_sent += 1

            else:

                skipped += 1

        # ====================================================
        # TOMORROW
        # ====================================================

        elif match_date == tomorrow:

            message = build_schedule_message(
                match,
                "MATCH_TOMORROW"
            )

            sent = send_news(
                match,
                "MATCH_TOMORROW",
                message
            )

            if sent:

                news_sent += 1

            else:

                skipped += 1

        # ====================================================
        # STARTED
        # ====================================================

        if status in [
            "IN_PLAY",
            "PAUSED"
        ]:

            message = build_started_message(
                match
            )

            sent = send_news(
                match,
                "MATCH_STARTED",
                message
            )

            if sent:

                news_sent += 1

        # ====================================================
        # FINISHED
        # ====================================================

        if status in [
            "FINISHED",
            "AWARDED"
        ]:

            message = build_finished_message(
                match
            )

            sent = send_news(
                match,
                "MATCH_FINISHED",
                message
            )

            if sent:

                news_sent += 1

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"Matches checked : {checked}"
    )

    print(
        f"Initialized     : {initialized}"
    )

    print(
        f"News sent       : {news_sent}"
    )

    print(
        f"Skipped         : {skipped}"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
