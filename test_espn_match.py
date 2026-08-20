import requests
import json

event_id = "401876489"

url = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/summary"

response = requests.get(
    url,
    params={"event": event_id},
    timeout=30,
    headers={"User-Agent": "Mozilla/5.0"}
)

print("STATUS:", response.status_code)

data = response.json()

print(json.dumps(data, ensure_ascii=False, indent=2))

with open(
    f"espn_{event_id}.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(
        data,
        f,
        ensure_ascii=False,
        indent=2
    )
