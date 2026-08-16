import os
import requests


API_KEY = os.getenv("THE_NEWS_API_KEY")

URL = "https://api.thenewsapi.com/v1/news/all"


def main():

    print("=" * 70)
    print("THE NEWS API TEST")
    print("=" * 70)

    if not API_KEY:
        print("❌ THE_NEWS_API_KEY is missing")
        return

    params = {
        "api_token": API_KEY,
        "search": "football",
        "language": "en",
        "limit": 3,
    }

    print("URL:", URL)
    print("Search:", params["search"])
    print("Limit:", params["limit"])

    response = requests.get(
        URL,
        params=params,
        timeout=30,
    )

    print("")
    print("HTTP STATUS:", response.status_code)

    print("")
    print("FINAL URL:")
    print(response.url)

    print("")
    print("RESPONSE:")

    try:
        print(response.json())

    except Exception:
        print(response.text[:3000])


if __name__ == "__main__":
    main()
