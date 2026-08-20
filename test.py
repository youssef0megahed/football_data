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
    print("BOXSCORE")
    print("=" * 60)

    boxscore = summary.get("boxscore")

    if boxscore is None:
        print("No 'boxscore' key in response.")
    else:

        for team_block in boxscore.get("teams", []):

            team_name = (
                team_block.get("team", {}).get("displayName")
            )

            home_away = team_block.get("homeAway")

            print(f"--- {team_name} ({home_away}) ---")

            for stat in team_block.get("statistics", []):
                print(
                    f"  {stat.get('name')}: "
                    f"{stat.get('displayValue')} "
                    f"({stat.get('label')})"
                )

    print("=" * 60)
    print("ROSTERS (full first player sample)")
    print("=" * 60)

    rosters = summary.get("rosters")

    if rosters is None:
        print("No 'rosters' key in response.")
    else:

        for team_roster in rosters:

            team_name = (
                team_roster.get("team", {}).get("displayName")
            )

            formation = team_roster.get("formation")

            roster = team_roster.get("roster", [])

            print(
                f"--- {team_name} "
                f"(formation={formation}, "
                f"players={len(roster)}) ---"
            )

            if roster:
                print(json.dumps(roster[0], indent=2)[:2000])

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

                print(f"  category: {category.get('displayName')}")

                for leader in category.get("leaders", [])[:1]:
                    print(
                        f"    {json.dumps(leader, indent=4)[:600]}"
                    )

    print("DONE")


if __name__ == "__main__":
    main()
