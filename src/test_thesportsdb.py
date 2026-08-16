import requests
import json

BASE_URL = "https://www.thesportsdb.com/api/v1/json/123"

params = {
    "e": "Racing Santander vs Villarreal",
    "d": "2026-08-16",
}

response = requests.get(
    f"{BASE_URL}/searchevents.php",
    params=params,
    timeout=30,
)

print("STATUS:", response.status_code)
print(json.dumps(response.json(), indent=2, ensure_ascii=False))
