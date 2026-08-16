import requests


BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

EVENT_ID = "2506178"


def get_events():

    response = requests.get(
        f"{BASE_URL}/lookuptimeline.php",
        params={"id": EVENT_ID},
        timeout=30,
    )

    response.raise_for_status()

    return response.json().get("timeline") or []


def main():

    for request_number in range(1, 4):

        print("\n" + "=" * 60)
        print("الطلب رقم:", request_number)

        events = get_events()

        print("عدد الأحداث:", len(events))

        for event in events:
            print(
                event.get("idTimeline"),
                "|",
                event.get("intTime"),
                "|",
                event.get("strTimeline"),
                "|",
                event.get("strTimelineDetail"),
                "|",
                event.get("strPlayer"),
            )


if __name__ == "__main__":
    main()
