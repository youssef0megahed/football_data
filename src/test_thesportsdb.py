import requests


BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

DATE = "20260816"

LEAGUES = {
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
    "Champions League": "uefa.champions",
}


def test_league(name, league):

    url = f"{BASE_URL}/{league}/scoreboard"

    response = requests.get(
        url,
        params={"dates": DATE},
        timeout=30,
    )

    print("\n" + "=" * 60)
    print(name, "|", league)
    print("STATUS:", response.status_code)

    if response.status_code != 200:
        print("RESULT: FAILED")
        return

    data = response.json()

    events = data.get("events", [])

    print("MATCHES:", len(events))

    if not events:
        print("RESULT: NO MATCHES")
        return

    print("RESULT: OK")

    for event in events[:3]:

        competition = event.get(
            "competitions",
            [{}]
        )[0]

        competitors = competition.get(
            "competitors",
            []
        )

        teams = []

        for team in competitors:

            teams.append(
                team.get(
                    "team",
                    {}
                ).get(
                    "displayName",
                    ""
                )
            )

        print(
            "-",
            event.get("name"),
            "|",
            event.get("date"),
            "|",
            teams
        )


def main():

    print("=" * 60)
    print("ESPN LEAGUE COVERAGE TEST")
    print("=" * 60)

    for name, league in LEAGUES.items():

        try:
            test_league(name, league)

        except Exception as e:

            print(
                "RESULT: ERROR",
                type(e).__name__,
                str(e)
            )


if __name__ == "__main__":
    main()
