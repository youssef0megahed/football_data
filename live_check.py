"""
يفحص هل فيه مباريات جارية دلوقتي. لو مفيش، يوقف فوراً (خفيف جداً، مش بيستهلك حصة AI).
لو فيه، يجيب الأحداث الجديدة (أهداف، كروت، بداية/نهاية الشوط)، يترجمها، ويبعتها نص + صورة.
مصمم يشتغل كل دقيقة-دقيقتين عبر cron-job.org.
"""
import config
from utils import gemini, telegram, supabase_client, image_gen
import requests

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_live_fixtures():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"live": "all"}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب المباريات المباشرة: {resp.status_code}")
        return []
    return resp.json().get("response", [])


def translate_club(english_name):
    return config.TRACKED_CLUBS.get(english_name, english_name)


def translate_player_name(english_name):
    prompt = f"""ترجم اسم اللاعب ده للعربي بأشيع تهجئة معروفة له فقط، من غير أي شرح: {english_name}"""
    result = gemini.call_gemini(prompt, config.GEMINI_API_KEY)
    return result.strip() if result else english_name


def process_fixture_events(fixture):
    fixture_id = fixture["fixture"]["id"]
    home_en = fixture["teams"]["home"]["name"]
    away_en = fixture["teams"]["away"]["name"]
    home_ar = translate_club(home_en)
    away_ar = translate_club(away_en)
    status = fixture["fixture"]["status"]["short"]
    elapsed = fixture["fixture"]["status"]["elapsed"]
    score = f"{fixture['goals']['home']}-{fixture['goals']['away']}"

    new_events_text = []
    new_events_rows = []

    # حالة بداية/نهاية الشوط
    status_key = f"status_{status}"
    if status in ("1H", "2H", "HT", "FT") and not supabase_client.is_event_sent(
        config.SUPABASE_URL, config.SUPABASE_KEY, fixture_id, status_key
    ):
        status_labels = {"1H": "بداية الشوط الأول", "HT": "نهاية الشوط الأول", "2H": "بداية الشوط الثاني", "FT": "نهاية المباراة"}
        label = status_labels.get(status, status)
        new_events_text.append(f"⏱️ {label} - {home_ar} {score} {away_ar}")
        new_events_rows.append([label, f"{home_ar} {score} {away_ar}", f"{elapsed}'" if elapsed else ""])
        supabase_client.mark_event_sent(config.SUPABASE_URL, config.SUPABASE_KEY, fixture_id, status_key)

    # أحداث الأهداف والكروت
    for event in fixture.get("events", []):
        event_type = event.get("type")
        if event_type not in ("Goal", "Card"):
            continue

        minute = event.get("time", {}).get("elapsed", 0)
        player_en = event.get("player", {}).get("name", "")
        detail = event.get("detail", "")
        event_key = f"{event_type}_{minute}_{player_en}"

        if supabase_client.is_event_sent(config.SUPABASE_URL, config.SUPABASE_KEY, fixture_id, event_key):
            continue

        player_ar = translate_player_name(player_en) if player_en else ""
        icon = "⚽" if event_type == "Goal" else ("🟨" if "Yellow" in detail else "🟥")
        label_ar = "هدف" if event_type == "Goal" else ("إنذار" if "Yellow" in detail else "طرد")

        new_events_text.append(f"{icon} {minute}' {label_ar} - {player_ar} ({home_ar if event.get('team', {}).get('name') == home_en else away_ar})")
        new_events_rows.append([f"{minute}'", label_ar, player_ar])

        supabase_client.mark_event_sent(config.SUPABASE_URL, config.SUPABASE_KEY, fixture_id, event_key)

    if new_events_text:
        text_message = f"🔴 {home_ar} {score} {away_ar}\n\n" + "\n".join(new_events_text)
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, text_message)

        img_url = image_gen.generate_table_image(
            config.HCTI_USER_ID, config.HCTI_API_KEY,
            title=f"{home_ar} {score} {away_ar}",
            headers=["الدقيقة", "الحدث", "التفاصيل"],
            rows=new_events_rows,
        )
        if img_url:
            telegram.send_photo(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, img_url)

        print(f"  تم إرسال {len(new_events_text)} حدث جديد لمباراة {home_ar} ضد {away_ar}")


def main():
    live_fixtures = get_live_fixtures()

    if not live_fixtures:
        print("مفيش مباريات جارية دلوقتي.")
        return

    print(f"فيه {len(live_fixtures)} مباراة جارية.")
    for fixture in live_fixtures:
        try:
            process_fixture_events(fixture)
        except Exception as e:
            print(f"  خطأ في معالجة مباراة: {e}")


if __name__ == "__main__":
    main()
