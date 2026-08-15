"""
يجيب مواعيد وأحداث المباريات من api-football، وأحداث الفانتازي (تغيّر أسعار/إصابات) من FPL،
يترجمهم للعربي، ويبعتهم تليجرام. بس كده، من غير تحليل أو توصيات.
"""
import datetime
import requests
import config
from utils import gemini, telegram, fpl

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_todays_fixtures():
    today = datetime.date.today().isoformat()
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"date": today}, timeout=20)
    if resp.status_code != 200:
        return []
    return resp.json().get("response", [])


def get_live_events():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"live": "all"}, timeout=20)
    if resp.status_code != 200:
        return []
    return resp.json().get("response", [])


def format_fixtures_english(fixtures):
    if not fixtures:
        return None
    lines = []
    for f in fixtures[:20]:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        time_str = f["fixture"]["date"][11:16]
        lines.append(f"{home} vs {away} at {time_str} UTC")
    return "\n".join(lines)


def format_live_events_english(live_fixtures):
    if not live_fixtures:
        return None
    lines = []
    for f in live_fixtures[:10]:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        score = f"{f['goals']['home']}-{f['goals']['away']}"
        status = f["fixture"]["status"]["elapsed"]
        lines.append(f"{home} {score} {away} (minute {status})")
        events = f.get("events", [])
        for e in events[-5:]:
            if e.get("type") in ("Goal", "Card"):
                player = e.get("player", {}).get("name", "")
                detail = e.get("detail", "")
                minute = e.get("time", {}).get("elapsed", "")
                lines.append(f"  - {minute}': {detail} - {player}")
    return "\n".join(lines)


def get_fantasy_changes():
    players = fpl.get_all_players(config.FPL_BASE)
    if not players:
        return None
    injured = [p for p in players if p["status"] != "a" and p["news"]]
    lines = []
    for p in injured[:15]:
        lines.append(f"{p['name']} ({p['team']}) - status: {p['status']} - {p['news']}")
    return "\n".join(lines) if lines else None


def translate_to_arabic(english_text, context_label):
    if not english_text:
        return None
    prompt = f"""انت مترجم رياضي محترف. ترجم المعلومات دي للعربية الفصحى الصحفية بشكل منظم وواضح، من غير أي تحليل أو رأي شخصي، بس نقل المعلومة بدقة:

{english_text}

رجّع النص المترجم فقط، منسّق في نقط أو أسطر واضحة."""
    return gemini.call_gemini(prompt, config.GEMINI_API_KEY, config.GLM_API_KEY)


def main():
    # مواعيد وأحداث المباريات
    fixtures = get_todays_fixtures()
    fixtures_en = format_fixtures_english(fixtures)
    if fixtures_en:
        translated = translate_to_arabic(fixtures_en, "مباريات اليوم")
        if translated:
            telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, f"📅 مباريات اليوم\n\n{translated}")

    live = get_live_events()
    live_en = format_live_events_english(live)
    if live_en:
        translated = translate_to_arabic(live_en, "أحداث مباشرة")
        if translated:
            telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, f"🔴 أحداث مباشرة\n\n{translated}")

    # أحداث الفانتازي
    fantasy_en = get_fantasy_changes()
    if fantasy_en:
        translated = translate_to_arabic(fantasy_en, "تحديثات فانتازي")
        if translated:
            telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, f"⚽ تحديثات فانتازي\n\n{translated}")

    print("انتهى التشغيل.")


if __name__ == "__main__":
    main()
