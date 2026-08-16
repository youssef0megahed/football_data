import requests


BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE = "esp.1"
DATE = "20260816"


def main():

    scoreboard = requests.get(
        f"{BASE_URL}/{LEAGUE}/scoreboard",
        params={"dates": DATE},
        timeout=30,
    )

    scoreboard.raise_for_status()

    events = scoreboard.json().get("events", [])

    for match in events:

        name = match.get("name", "")

        if "Racing" not in name:
            continue

        event_id = match["id"]

        print("\n" + "=" * 60)
        print("MATCH:", name)
        print("ESPN ID:", event_id)

        summary = requests.get(
            f"{BASE_URL}/{LEAGUE}/summary",
            params={"event": event_id},
            timeout=30,
        )

        summary.raise_for_status()

        data = summary.json()

        details = data.get("plays", [])

        print("TOTAL EVENTS:", len(details))

        for i, event in enumerate(details, 1):

            clock = event.get("clock", {})
            event_type = event.get("type", {})

            athletes = event.get(
                "athletesInvolved",
                []
            )

            players = ", ".join(
                a.get("displayName", "")
                for a in athletes
            )

            print(
                f"{i}. "
                f"{clock.get('displayValue', '')} | "
                f"{event_type.get('text', '')} | "
                f"{players}"
            )


if __name__ == "__main__":
    main()
