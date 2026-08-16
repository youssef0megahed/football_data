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

        print("=" * 60)
        print("MATCH:", match["name"])
        print("ESPN ID:", match["id"])

        competition = match["competitions"][0]

        details = competition.get("details", [])

        print("TOTAL EVENTS:", len(details))

        for i, event in enumerate(details, 1):

            print(
                i,
                "|",
                event.get("clock", {}).get("displayValue"),
                "|",
                event.get("type", {}).get("text"),
                "|",
                event.get("team", {}).get("id"),
                "|",
                [
                    p.get("displayName")
                    for p in event.get("athletesInvolved", [])
                ],
            )


if __name__ == "__main__":
    main()
