"""
يجيب مباريات اليوم ومباريات الغد لكل الدوريات المتابعة، كل واحدة رسالة منفصلة (نص + صورة).
يشتغل مرة واحدة يومياً.
"""
import datetime
import requests
import config
from utils import telegram, image_gen

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_fixtures_by_date(date_str):
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"date": date_str}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب مباريات {date_str}: {resp.status_code}")
        return []
    return resp.json().get("response", [])


def translate_club(english_name):
    return config.TRACKED_CLUBS.get(english_name, english_name)


def filter_tracked_leagues(fixtures):
    tracked_ids = set(config.LEAGUE_IDS.values())
    return [f for f in fixtures if f["league"]["id"] in tracked_ids]


def send_fixtures_report(fixtures, title):
    if not fixtures:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, f"{title}\n\nمفيش مباريات في الدوريات المتابعة.")
        return

    lines = []
    rows = []
    for f in fixtures[:25]:
        home_en = f["teams"]["home"]["name"]
        away_en = f["teams"]["away"]["name"]
        home_ar = translate_club(home_en)
        away_ar = translate_club(away_en)
        time_str = f["fixture"]["date"][11:16]
        league_name = f["league"]["name"]

        lines.append(f"{home_ar} ضد {away_ar} - {time_str} UTC ({league_name})")
        rows.append([home_ar, away_ar, time_str, league_name])

    text_message = f"{title}\n\n" + "\n".join(lines)
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, text_message)

    img_url = image_gen.generate_table_image(
        config.HCTI_USER_ID, config.HCTI_API_KEY,
        title=title,
        headers=["فريق مضيف", "فريق ضيف", "الموعد", "البطولة"],
        rows=rows,
    )
    if img_url:
        telegram.send_photo(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, img_url)


def main():
    today = datetime.date.today().isoformat()
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    today_fixtures = filter_tracked_leagues(get_fixtures_by_date(today))
    send_fixtures_report(today_fixtures, "📅 مباريات اليوم")

    tomorrow_fixtures = filter_tracked_leagues(get_fixtures_by_date(tomorrow))
    send_fixtures_report(tomorrow_fixtures, "📅 مباريات الغد")

    print("تم إرسال تقرير مباريات اليوم والغد.")


if __name__ == "__main__":
    main()
