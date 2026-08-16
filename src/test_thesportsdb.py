import json
import requests


BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

EVENTS = {
    "Racing vs Villarreal": "2506178",
    "Espanyol vs Levante": "2506174",
    "Deportivo Alaves vs Getafe": "2506176",
    "Sevilla vs Rayo Vallecano": "2506172",
}


def get_timeline(event_id):
    response = requests.get(
        f"{BASE_URL}/lookuptimeline.php",
        params={"id": event_id},
        timeout=30,
    )

    response.raise_for_status()

    return response.json()


def main():

    print("=" * 70)
    print("TheSportsDB MATCH EVENTS COVERAGE TEST")
    print("=" * 70)

    results = []

    for name, event_id in EVENTS.items():

        print(f"\n{'-' * 70}")
        print(name)
        print("Event ID:", event_id)

        try:
            data = get_timeline(event_id)

            timeline = data.get("timeline") or []

            print("Timeline events:", len(timeline))

            event_types = {}

            for event in timeline:
                event_type = event.get("strTimeline", "UNKNOWN")
                detail = event.get("strTimelineDetail", "")

                key = f"{event_type} / {detail}"

                event_types[key] = (
                    event_types.get(key, 0) + 1
                )

            print(
                json.dumps(
                    event_types,
                    indent=2,
                    ensure_ascii=False,
                )
            )

            results.append(
                {
                    "match": name,
                    "event_id": event_id,
                    "status": "OK",
                    "events": len(timeline),
                    "types": event_types,
                }
            )

        except Exception as exc:

            print("ERROR:", exc)

            results.append(
                {
                    "match": name,
                    "event_id": event_id,
                    "status": "ERROR",
                    "error": str(exc),
                }
            )

    print("\n")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
