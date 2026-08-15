import os
import requests

TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")

URL = "https://api.football-data.org/v4/competitions/PD/matches"

HEADERS = {
    "X-Auth-Token": TOKEN
}

PARAMS = {
    "season": 2026
}

response = requests.get(
    URL,
    headers=HEADERS,
    params=PARAMS,
    timeout=30
)

print("=" * 70)
print("LA LIGA - SEASON 2026 TEST")
print("=" * 70)

print("HTTP Status:", response.status_code)

if response.status_code != 200:
    print(response.text)
    raise SystemExit(1)

data = response.json()

print("")

print("Competition:")
print(data.get("competition", {}).get("name"))

print("Season:")
print(data.get("season", {}).get("startDate"),
      "→",
      data.get("season", {}).get("endDate"))

matches = data.get("matches", [])

print("")
print("Total matches returned:", len(matches))

print("")
print("=" * 70)
print("MATCHES AROUND AUGUST 15-17")
print("=" * 70)

for match in matches:

    date = match["utcDate"]

    if date.startswith("2026-08-15") or \
       date.startswith("2026-08-16") or \
       date.startswith("2026-08-17"):

        print("")
        print("Match ID:", match["id"])
        print("Date:", date)
        print(
            match["homeTeam"]["name"],
            "vs",
            match["awayTeam"]["name"]
        )
        print("Status:", match["status"])

print("")
print("=" * 70)
print("TEST COMPLETED")
print("=" * 70)
