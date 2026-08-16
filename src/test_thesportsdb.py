import json
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
