import os
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")

BASE_URL = "https://api.football-data.org/v4/competitions"

TIMEZONE = ZoneInfo("Africa/Cairo")

COMPETITIONS = {
    "Premier League": "PL",
    "La Liga": "PD",
    "Serie A": "SA",
    "Bundesliga": "BL1",
    "Ligue 1": "FL1",
}

HEADERS = {
    "X-Auth-Token": TOKEN
}


# ============================================================
# GET CURRENT SEASON
# ============================================================

def get_current_season():
    """
    Determines the football season based on Cairo date.

    Example:
    August 2026 -> season 2026
    January 2027 -> season 2026
    """

    now = datetime.now(TIMEZONE)

    if now.month >= 7:
        return now.year

    return now.year - 1


# ============================================================
# GET SEASON MATCHES
# ============================================================

def get_competition_matches(competition_code, season):

    url = f"{BASE_URL}/{competition_code}/matches"

    params = {
        "season": season
    }

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(
            f"API request failed: "
            f"{response.status_code} - {response.text}"
        )

    data = response.json()

    return data.get("matches", [])


# ============================================================
# CONVERT UTC TO CAIRO
# ============================================================

def convert_to_cairo(utc_date):

    utc_datetime = datetime.fromisoformat(
        utc_date.replace("Z", "+00:00")
    )

    return utc_datetime.astimezone(TIMEZONE)


# ============================================================
# PRINT MATCH
# ============================================================

def print_match(match):

    match_id = match["id"]

    home_team = match["homeTeam"]["name"]
    away_team = match["awayTeam"]["name"]

    utc_date = match["utcDate"]

    cairo_datetime = convert_to_cairo(utc_date)

    date = cairo_datetime.strftime("%Y-%m-%d")
    time = cairo_datetime.strftime("%H:%M")

    status = match["status"]

    score = match.get("score", {})

    full_time = score.get("fullTime", {})

    home_score = full_time.get("home")
    away_score = full_time.get("away")

    print(f"    Match ID : {match_id}")
    print(f"    Time     : {time}")
    print(f"    Home     : {home_team}")
    print(f"    Away     : {away_team}")
    print(f"    Status   : {status}")

    if home_score is not None and away_score is not None:
        print(f"    Score    : {home_score} - {away_score}")

    print(f"    UTC      : {utc_date}")
    print(f"    Cairo    : {date} {time}")

    print("")


# ============================================================
# MAIN
# ============================================================

def main():

    if not TOKEN:
        raise Exception(
            "FOOTBALL_DATA_TOKEN is missing."
        )

    now = datetime.now(TIMEZONE)

    today = now.date()
    tomorrow = today + timedelta(days=1)

    season = get_current_season()

    print("=" * 70)
    print("FOOTBALL DATA COLLECTOR")
    print("=" * 70)

    print(f"Timezone : Africa/Cairo")
    print(f"Today    : {today}")
    print(f"Tomorrow : {tomorrow}")
    print(f"Season   : {season}")

    print("")
    print("=" * 70)

    total_today = 0
    total_tomorrow = 0

    # --------------------------------------------------------
    # LOOP THROUGH THE FIVE MAJOR LEAGUES
    # --------------------------------------------------------

    for league_name, competition_code in COMPETITIONS.items():

        print("")
        print("=" * 70)
        print(f"🏆 {league_name}")
        print(f"Competition Code: {competition_code}")
        print("=" * 70)

        try:

            matches = get_competition_matches(
                competition_code,
                season
            )

            print(f"Season matches received: {len(matches)}")
            print("")

            today_matches = []
            tomorrow_matches = []

            # ------------------------------------------------
            # FILTER TODAY / TOMORROW
            # ------------------------------------------------

            for match in matches:

                cairo_datetime = convert_to_cairo(
                    match["utcDate"]
                )

                match_date = cairo_datetime.date()

                if match_date == today:
                    today_matches.append(match)

                elif match_date == tomorrow:
                    tomorrow_matches.append(match)

            # ------------------------------------------------
            # TODAY
            # ------------------------------------------------

            print("-" * 70)
            print(f"TODAY - {today}")
            print("-" * 70)

            if today_matches:

                for match in today_matches:
                    print_match(match)

            else:

                print("    No matches")

            # ------------------------------------------------
            # TOMORROW
            # ------------------------------------------------

            print("-" * 70)
            print(f"TOMORROW - {tomorrow}")
            print("-" * 70)

            if tomorrow_matches:

                for match in tomorrow_matches:
                    print_match(match)

            else:

                print("    No matches")

            # ------------------------------------------------
            # COUNTERS
            # ------------------------------------------------

            total_today += len(today_matches)
            total_tomorrow += len(tomorrow_matches)

            print("")
            print(
                f"    Today: {len(today_matches)} | "
                f"Tomorrow: {len(tomorrow_matches)}"
            )

        except Exception as error:

            print("")
            print(f"    ❌ ERROR: {error}")
            print("    Continuing with next league...")

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(f"Today matches    : {total_today}")
    print(f"Tomorrow matches : {total_tomorrow}")
    print(
        f"Total matches    : "
        f"{total_today + total_tomorrow}"
    )

    print("")
    print("API requests used: 5")
    print("Status: SUCCESS")

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
