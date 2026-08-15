import os
import requests
from datetime import datetime, timedelta, timezone

TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")

BASE_URL = "https://api.football-data.org/v4/matches"

HEADERS = {
    "X-Auth-Token": TOKEN
}


def get_matches(date_from, date_to):

    params = {
        "dateFrom": date_from,
        "dateTo": date_to,
        "competitions": "PL,PD,SA,BL1,FL1"
    }

    response = requests.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    print(f"HTTP Status: {response.status_code}")

    if response.status_code != 200:
        print("API ERROR:")
        print(response.text)
        return None

    return response.json()


def print_matches(data, title):

    print("")
    print("=" * 70)
    print(title)
    print("=" * 70)

    if not data or not data.get("matches"):
        print("No matches found.")
        return

    matches = data["matches"]

    print(f"Matches found: {len(matches)}")
    print("")

    current_competition = None

    for match in matches:

        competition = match["competition"]["name"]

        if competition != current_competition:
            current_competition = competition

            print("")
            print(f"🏆 {competition}")
            print("-" * 50)

        home = match["homeTeam"]["name"]
        away = match["awayTeam"]["name"]

        utc_date = match["utcDate"]
        status = match["status"]

        print(f"  Match ID: {match['id']}")
        print(f"  {home} vs {away}")
        print(f"  UTC: {utc_date}")
        print(f"  Status: {status}")
        print("")


def main():

    if not TOKEN:
        raise Exception(
            "FOOTBALL_DATA_TOKEN is missing."
        )

    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)

    today_string = today.strftime("%Y-%m-%d")
    tomorrow_string = tomorrow.strftime("%Y-%m-%d")

    print("=" * 70)
    print("FOOTBALL-DATA.ORG TEST")
    print("=" * 70)

    print(f"Today:    {today_string}")
    print(f"Tomorrow: {tomorrow_string}")

    # Today
    today_data = get_matches(
        today_string,
        today_string
    )

    print_matches(
        today_data,
        f"TODAY - {today_string}"
    )

    # Tomorrow
    tomorrow_data = get_matches(
        tomorrow_string,
        tomorrow_string
    )

    print_matches(
        tomorrow_data,
        f"TOMORROW - {tomorrow_string}"
    )

    print("")
    print("=" * 70)
    print("TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
