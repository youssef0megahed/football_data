import os
import requests

API_KEY = os.getenv("API_FOOTBALL_KEY")

BASE_URL = "https://v3.football.api-sports.io/fixtures"

LEAGUES = {
    "Premier League": 39,
    "La Liga": 140,
    "Serie A": 135,
    "Bundesliga": 78,
    "Ligue 1": 61,
}

SEASONS = [2022, 2023, 2024, 2025, 2026, ]

HEADERS = {
    "x-apisports-key": API_KEY
}


def check_season(league_name, league_id, season):

    params = {
        "league": league_id,
        "season": season
    }

    response = requests.get(
        BASE_URL,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    data = response.json()

    if data.get("errors"):
        return False, data["errors"]

    return True, len(data.get("response", []))


def main():

    if not API_KEY:
        print("ERROR: API_FOOTBALL_KEY is missing.")
        return

    print("=" * 70)
    print("API-FOOTBALL SEASON ACCESS CHECK")
    print("=" * 70)

    for league_name, league_id in LEAGUES.items():

        print("")
        print(f"🏆 {league_name}")
        print("-" * 50)

        for season in SEASONS:

            try:
                available, result = check_season(
                    league_name,
                    league_id,
                    season
                )

                if available:
                    print(
                        f"Season {season}: ✓ AVAILABLE "
                        f"(sample response: {result})"
                    )
                else:
                    print(
                        f"Season {season}: ✗ NOT AVAILABLE"
                    )
                    print(f"   API message: {result}")

            except Exception as e:
                print(f"Season {season}: ✗ ERROR")
                print(f"   {e}")

    print("")
    print("=" * 70)
    print("CHECK COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()
