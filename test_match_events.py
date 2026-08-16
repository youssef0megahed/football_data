import os
import requests
import json


TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")

MATCH_ID = 564629

URL = f"https://api.football-data.org/v4/matches/{MATCH_ID}"

HEADERS = {
    "X-Auth-Token": TOKEN
}


print("=" * 70)
print("FOOTBALL DATA EVENT TEST")
print("=" * 70)

print(f"Match ID: {MATCH_ID}")
print(f"URL: {URL}")
print("")

if not TOKEN:
    raise Exception(
        "FOOTBALL_DATA_TOKEN is missing."
    )


response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)


print(
    f"HTTP Status: {response.status_code}"
)

print("")


if response.status_code != 200:

    print("❌ API ERROR")
    print(response.text)

    raise SystemExit(1)


data = response.json()


print("Match:")
print(
    data.get("homeTeam", {}).get("name"),
    "vs",
    data.get("awayTeam", {}).get("name")
)

print(
    "Status:",
    data.get("status")
)

print(
    "Score:",
    data.get("score", {})
)

print("")


goals = data.get("goals", [])
bookings = data.get("bookings", [])
substitutions = data.get("substitutions", [])
penalties = data.get("penalties", [])


print("=" * 70)
print("EVENTS")
print("=" * 70)

print(
    f"⚽ Goals         : {len(goals)}"
)

print(
    f"🟨/🟥 Bookings   : {len(bookings)}"
)

print(
    f"🔄 Substitutions : {len(substitutions)}"
)

print(
    f"🥅 Penalties     : {len(penalties)}"
)

print("")


print("=" * 70)
print("GOALS")
print("=" * 70)

print(
    json.dumps(
        goals,
        indent=2,
        ensure_ascii=False
    )
)

print("")


print("=" * 70)
print("BOOKINGS")
print("=" * 70)

print(
    json.dumps(
        bookings,
        indent=2,
        ensure_ascii=False
    )
)

print("")


print("=" * 70)
print("SUBSTITUTIONS")
print("=" * 70)

print(
    json.dumps(
        substitutions,
        indent=2,
        ensure_ascii=False
    )
)

print("")


print("=" * 70)
print("PENALTIES")
print("=" * 70)

print(
    json.dumps(
        penalties,
        indent=2,
        ensure_ascii=False
    )
)
