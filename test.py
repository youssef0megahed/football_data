import sys
import json
import requests

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def get_summary(league_slug, event_id):

    url = f"{ESPN_BASE_URL}/{league_slug}/summary"

    response = requests.get(
        url, params={"event": str(event_id)}, timeout=30
    )

    response.raise_for_status()

    return response.json()


def describe(value, path="", max_items=2):
    """يطبع شكل الداتا (نوعها + مفاتيحها) من غير ما يطبع كل المحتوى،
    عشان اللوج يفضل قابل للقراءة."""

    if isinstance(value, dict):
        print(f"{path} (dict) keys: {list(value.keys())}")

        for key in list(value.keys())[:max_items]:
            describe(value[key], f"{path}.{key}", max_items)

    elif isinstance(value, list):
        print(f"{path} (list) length: {len(value)}")

        if value:
            describe(value[0], f"{path}[0]", max_items)

    else:
        text = str(value)

        if len(text) > 120:
            text = text[:120] + "..."

        print(f"{path} = {text}")


def main():

    # يقبل event_id + league_slug كـ arguments، أو بيستخدم قيم افتراضية
    league_slug = sys.argv[1] if len(sys.argv) > 1 else "esp.1"
    event_id = sys.argv[2] if len(sys.argv) > 2 else "401882925"

    print(f"Fetching summary for league={league_slug} event={event_id}")

    summary = get_summary(league_slug, event_id)

    print("=" * 60)
    print("TOP-LEVEL KEYS")
    print("=" * 60)
    print(list(summary.keys()))

    print("=" * 60)
    print("BOXSCORE (skipped — already confirmed)")
    print("=" * 60)

    print("=" * 60)
    print("ROSTERS (one starter, full detail, links removed)")
    print("=" * 60)

    rosters = summary.get("rosters")

    if rosters is None:
        print("No 'rosters' key in response.")
    else:

        for team_roster in rosters:

            team_name = (
                team_roster.get("team", {}).get("displayName")
            )

            roster = team_roster.get("roster", [])

            starter = next(
                (p for p in roster if p.get("starter")), None
            )

            print(f"--- {team_name} ---")

            if starter:

                athlete = starter.get("athlete", {})

                print(
                    f"Player: {athlete.get('fullName')} "
                    f"| position: "
                    f"{starter.get('position', {}).get('name')} "
                    f"| jersey: {starter.get('jersey')}"
                )

                stats = starter.get("stats", [])

                print(f"Player stats count: {len(stats)}")

                for stat in stats:
                    print(
                        f"  {stat.get('name')}: "
                        f"{stat.get('displayValue')} "
                        f"({stat.get('displayName')})"
                    )

            else:
                print("No starter found in this roster.")

    print("=" * 60)
    print("LEADERS (full detail)")
    print("=" * 60)

    leaders = summary.get("leaders")

    if leaders is None:
        print("No 'leaders' key in response.")
    else:

        for team_leaders in leaders:

            team_name = (
                team_leaders.get("team", {}).get("displayName")
            )

            print(f"--- {team_name} ---")

            for category in team_leaders.get("leaders", []):

                top = (category.get("leaders") or [{}])[0]

                athlete_name = (
                    top.get("athlete", {}).get("displayName")
                )

                print(
                    f"  {category.get('displayName')}: "
                    f"{top.get('displayValue')} "
                    f"— {athlete_name}"
                )

    print("DONE")


if __name__ == "__main__":
    main()
