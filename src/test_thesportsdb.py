import json
import requests


BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# La Liga
LEAGUE = "esp.1"

# Racing de Santander vs Villarreal
DATE = "20260816"


def main():

    url = f"{BASE_URL}/{LEAGUE}/scoreboard"

    response = requests.get(
        url,
        params={"dates": DATE},
        timeout=30,
    )

    print("STATUS:", response.status_code)

    response.raise_for_status()

    data = response.json()

    events = data.get("events", [])

    print("TOTAL MATCHES:", len(events))

    for event in events:

        competition = event.get("competitions", [{}])[0]

        competitors = competition.get(
            "competitors",
            []
        )

        teams = [
            c.get("team", {}).get("displayName", "")
            for c in competitors
        ]

        if not any("Racing" in team for team in teams):
            continue

        print("\n" + "=" * 70)
        print("MATCH")
        print("=" * 70)

        print(
            json.dumps(
                event,
                indent=2,
                ensure_ascii=False,
            )
        )

        event_id = event.get("id")

        print("\nESPN EVENT ID:", event_id)

        # Get detailed event data
        summary_url = (
            "https://site.api.espn.com/apis/site/v2/"
            f"sports/soccer/{LEAGUE}/summary"
        )

        summary_response = requests.get(
            summary_url,
            params={"event": event_id},
            timeout=30,
        )

        print(
            "\nSUMMARY STATUS:",
            summary_response.status_code
        )

        summary_response.raise_for_status()

        summary = summary_response.json()

        print("\n" + "=" * 70)
        print("SUMMARY / EVENTS")
        print("=" * 70)

        print(
            json.dumps(
                summary,
                indent=2,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
