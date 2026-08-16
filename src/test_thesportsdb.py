import json
import requests


BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

EVENTS = {
    "Racing vs Villarreal": "2506178",
    "Espanyol vs Levante": "2506174",
    "Deportivo Alaves vs Getafe": "2506176",
    "Sevilla vs Rayo Vallecano": "2506172",
}


def main():

    for name, event_id in EVENTS.items():

        print("\n" + "=" * 60)
        print(name)
        print("Event ID:", event_id)

        response = requests.get(
            f"{BASE_URL}/lookuptimeline.php",
            params={"id": event_id},
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        timeline = data.get("timeline") or []

        print("عدد الأحداث:", len(timeline))

        for event in timeline:
            print(
                event.get("intTime"),
                "|",
                event.get("strTimeline"),
                "|",
                event.get("strTimelineDetail"),
                "|",
                event.get("strPlayer"),
            )


if __name__ == "__main__":
    main()import json
import requests

BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"
EVENT_ID = "2506178"


def get(endpoint):
    response = requests.get(
        f"{BASE_URL}/{endpoint}",
        params={"id": EVENT_ID},
        timeout=30,
    )

    print(f"\n{'=' * 70}")
    print(endpoint)
    print(f"{'=' * 70}")
    print("STATUS:", response.status_code)

    response.raise_for_status()

    data = response.json()

    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        )
    )

    return data


def main():
    get("lookupevent.php")
    get("lookuptimeline.php")
    get("lookuplineup.php")
    get("lookupeventstats.php")


if __name__ == "__main__":
    main()
