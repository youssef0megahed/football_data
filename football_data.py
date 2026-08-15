import os
import requests
from datetime import datetime, timedelta, timezone

API_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io/fixtures"

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}

HEADERS = {
    "x-apisports-key": API_KEY
}


def get_fixtures(date, league_name, league_id):
    params = {
        "date": date,
        "league": league_id,
        "season": datetime.strptime(date, "%Y-%m-%d").year
    }

    response = requests.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if data.get("errors"):
        raise Exception(data["errors"])

    return data.get("response", [])


def print_match(match):
    fixture = match["fixture"]
    teams = match["teams"]
    league = match["league"]

    match_time = fixture["date"]

    print(f"    Match ID: {fixture['id']}")
    print(f"    {teams['home']['name']} vs {teams['away']['name']}")
    print(f"    Time: {match_time}")
    print(f"    Venue: {fixture['venue']['name']}")
    print(f"    Status: {fixture['status']['long']}")
    print(f"    League: {league['name']}")
    print("")


def main():

    if not API_KEY:
        raise Exception(
            "API_FOOTBALL_KEY is missing. "
            "Make sure it is added to GitHub Secrets."
        )

    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)

    dates = {
        "TODAY": today,
        "TOMORROW": tomorrow
    }

    total_today = 0
    total_tomorrow = 0

    print("=" * 60)
    print("FOOTBALL DATA PIPELINE")
    print("=" * 60)

    for day_name, date in dates.items():

        date_string = date.strftime("%Y-%m-%d")

        print("")
        print("=" * 60)
        print(f"{day_name}: {date_string}")
        print("=" * 60)

        for league_name, league_id in LEAGUES.items():

            print("")
            print(f"🏆 {league_name}")
            print("-" * 40)

            matches = get_fixtures(
                date_string,
                league_name,
                league_id
            )

            if not matches:
                print("    No matches")
                continue

            print(f"    Matches found: {len(matches)}")
            print("")

            for match in matches:
                print_match(match)

            if day_name == "TODAY":
                total_today += len(matches)
            else:
                total_tomorrow += len(matches)

    print("")
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Today:     {total_today}")
    print(f"Tomorrow:  {total_tomorrow}")
    print(f"Total:     {total_today + total_tomorrow}")
    print("")
    print("STATUS: SUCCESS")
    print("=" * 60)


if __name__ == "__main__":
    main()
