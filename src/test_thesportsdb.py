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

    print(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False
        )
    )

    return data


def main():

    # ========================================================
    # SEARCH MATCH
    # ========================================================

    search = get(
        "searchevents.php",
        {
            "e": "Racing Santander vs Villarreal",
            "d": "2026-08-16",
        },
    )

    events = search.get("event") or []

    if not events:
        raise RuntimeError(
            "TheSportsDB returned no matching event."
        )

    event_id = events[0].get(
        "idEvent"
    )

    if not event_id:
        raise RuntimeError(
            "TheSportsDB event has no idEvent."
        )

    print(
        "\nSELECTED EVENT ID:",
        event_id
    )


    # ========================================================
    # EVENT DETAILS
    # ========================================================

    get(
        "lookupevent.php",
        {
            "id": event_id
        }
    )


    # ========================================================
    # TIMELINE / MATCH EVENTS
    # ========================================================

    get(
        "lookuptimeline.php",
        {
            "id": event_id
        }
    )


    # ========================================================
    # LINEUP
    # ========================================================

    get(
        "lookuplineup.php",
        {
            "id": event_id
        }
    )


    # ========================================================
    # STATISTICS
    # ========================================================

    get(
        "lookupeventstats.php",
        {
            "id": event_id
        }
    )


    # ========================================================
    # EVENT RESULTS
    # ========================================================

    get(
        "eventresults.php",
        {
            "id": event_id
        }
    )


if __name__ == "__main__":
    main()
