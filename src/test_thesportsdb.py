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
        competition = match["competitions"][0]

        print("=" * 60)
        print("MATCH:", match["name"])
        print("ESPN ID:", event_id)

        # -------------------------
        # BASIC MATCH DATA
        # -------------------------

        print("\nBASIC DATA")

        print("Date:", match.get("date"))
        print("Season:", match.get("season", {}).get("slug"))

        status = competition.get("status", {})

        print(
            "Status:",
            status.get("type", {}).get("name")
        )

        for team in competition.get("competitors", []):

            print(
                "Team:",
                team.get("team", {}).get("displayName"),
                "| Score:",
                team.get("score"),
                "| Home/Away:",
                team.get("homeAway"),
            )

        # -------------------------
        # MATCH EVENTS
        # -------------------------

        print("\nEVENTS")

        details = competition.get("details", [])

        print("Total events:", len(details))

        for event in details:

            print(
                event.get("clock", {}).get("displayValue"),
                "|",
                event.get("type", {}).get("text"),
                "|",
                event.get("team", {}).get("id"),
                "|",
                [
                    p.get("displayName")
                    for p in event.get(
                        "athletesInvolved",
                        []
                    )
                ],
            )

        # -------------------------
        # TEAM STATISTICS
        # -------------------------

        print("\nTEAM STATISTICS")

        for team in competition.get(
            "competitors",
            []
        ):

            print(
                "\n",
                team.get("team", {}).get(
                    "displayName"
                )
            )

            for stat in team.get(
                "statistics",
                []
            ):

                print(
                    stat.get("name"),
                    "=",
                    stat.get("displayValue"),
                )

        # -------------------------
        # SUMMARY
        # -------------------------

        summary_url = (
            f"{BASE_URL}/{LEAGUE}/summary"
        )

        summary_response = requests.get(
            summary_url,
            params={"event": event_id},
            timeout=30,
        )

        summary_response.raise_for_status()

        summary = summary_response.json()

        print("\nSUMMARY SECTIONS")

        for key in summary.keys():

            value = summary[key]

            if isinstance(value, list):

                print(
                    key,
                    ":",
                    len(value)
                )

            elif isinstance(value, dict):

                print(
                    key,
                    ":",
                    list(value.keys())
                )

            else:

                print(
                    key,
                    ":",
                    type(value).__name__
                )


if __name__ == "__main__":
    main()
