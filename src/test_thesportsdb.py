import json
import requests

BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"


def get(endpoint, params):
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=30,
    )

    print(f"\n=== {endpoint} ===")
    print("STATUS:", response.status_code)

    response.raise_for_status()

    data = response.json()

    print(json.dumps(data, indent=2, ensure_ascii=False))

    return data


def main():

    # Get La Liga 2026/27 events
    data = get(
        "eventsseason.php",
        {
            "id": "4335",
        },
    )

    events = data.get("events") or []

    print("\nTOTAL EVENTS:", len(events))

    for event in events:
        home = event.get("strHomeTeam", "")
        away = event.get("strAwayTeam", "")

        if (
            "Racing" in home
            or "Racing" in away
            or "Villarreal" in home
            or "Villarreal" in away
        ):
            print("\nMATCH FOUND:")
            print(
                json.dumps(
                    event,
                    indent=2,
                    ensure_ascii=False,
                )
            )


if __name__ == "__main__":
    main()
