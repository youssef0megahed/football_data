import requests
import json

event_id = "401876489"

url = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/summary"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.espn.com/"
}

response = requests.get(
    url,
    params={"event": event_id},
    headers=headers,
    timeout=30
)

print("STATUS:", response.status_code)
print("URL:", response.url)
print("CONTENT-TYPE:", response.headers.get("content-type"))

if response.status_code != 200:
    print("\n❌ ESPN رفض الطلب")
    print("الرد:")
    print(response.text[:1000])
    raise SystemExit(1)

try:
    data = response.json()
except ValueError:
    print("\n❌ ESPN لم يرجع JSON")
    print(response.text[:1000])
    raise SystemExit(1)

print("\n✅ تم الحصول على البيانات")

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

print(f"تم حفظ: espn_{event_id}.json")
