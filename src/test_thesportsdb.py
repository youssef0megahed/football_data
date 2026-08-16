import requests

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE = "esp.1"
DATE = "20260816"


def main():
    response = requests.get(
        f"{BASE_URL}/{LEAGUE}/scoreboard",
        params={"dates": DATE},
        timeout=30,
    )
    response.raise_for_status()

    matches = response.json().get("events", [])

    for match in matches:

        if "Racing" not in match.get("name", ""):
            continue

        event_id = match["id"]

        print("=" * 60)
        print("MATCH:", match["name"])
        print("ESPN ID:", event_id)

        response = requests.get(
            f"{BASE_URL}/{LEAGUE}/summary",
            params={"event": event_id},
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        competition = (
            data.get("header", {})
            .get("competitions", [{}])[0]
        )

        details = competition.get("details", [])

        print("TOTAL EVENTS:", len(details))

        for number, event in enumerate(details, 1):

            time = event.get("clock", {}).get(
                "displayValue", ""
            )

            event_type = event.get(
                "type", {}
            ).get("text", "")

            team_id = event.get(
                "team", {}
            ).get("id", "")

            players = []

            for player in event.get(
                "athletesInvolved", []
            ):
                players.append(
                    player.get("displayName", "")
                )

            print(
                f"{number}. "
                f"{time} | "
                f"{event_type} | "
                f"Team: {team_id} | "
                f"Players: {', '.join(players)}"
            )


if __name__ == "__main__":
    main()
