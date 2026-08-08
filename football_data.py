"""
سحب بيانات كرة القدم من api-football: مباريات الغد، إحصائيات لحظية، ترتيب الدوري، الهدافين.
النتائج بترسل تليجرام كجداول نصية منسقة.
"""
import datetime
import requests
import config
from utils import telegram

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_tomorrow_fixtures():
    tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS, params={"date": tomorrow}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب مباريات الغد: {resp.status_code}")
        return []
    return resp.json().get("response", [])


def get_live_fixtures():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS, params={"live": "all"}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب المباريات المباشرة: {resp.status_code}")
        return []
    return resp.json().get("response", [])


def get_standings():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/standings", headers=HEADERS,
                         params={"league": config.LEAGUE_ID, "season": config.SEASON}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب الترتيب: {resp.status_code}")
        return []
    try:
        return resp.json()["response"][0]["league"]["standings"][0]
    except (KeyError, IndexError):
        return []


def get_top_scorers():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/players/topscorers", headers=HEADERS,
                         params={"league": config.LEAGUE_ID, "season": config.SEASON}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب الهدافين: {resp.status_code}")
        return []
    return resp.json().get("response", [])


def format_fixtures_message(fixtures, title):
    if not fixtures:
        return f"{title}\n\nمفيش مباريات."
    lines = [title, ""]
    for f in fixtures[:15]:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        status = f["fixture"]["status"]["short"]
        if status in ("1H", "2H", "HT", "LIVE"):
            score = f"{f['goals']['home']}-{f['goals']['away']} ({status})"
        else:
            time_str = f["fixture"]["date"][11:16]
            score = time_str
        lines.append(f"{home} vs {away}  |  {score}")
    return "\n".join(lines)


def format_standings_message(standings):
    if not standings:
        return "🏆 ترتيب الدوري\n\nمفيش بيانات متاحة."
    lines = ["🏆 ترتيب الدوري", "", "#  الفريق                 نقط  ف-ت-خ"]
    for team in standings[:20]:
        rank = team["rank"]
        name = team["team"]["name"][:20]
        points = team["points"]
        w, d, l = team["all"]["win"], team["all"]["draw"], team["all"]["lose"]
        lines.append(f"{rank:<2} {name:<22} {points:<4} {w}-{d}-{l}")
    return "```\n" + "\n".join(lines) + "\n```"


def format_scorers_message(scorers):
    if not scorers:
        return "⚽ الهدافين\n\nمفيش بيانات متاحة."
    lines = ["⚽ قائمة الهدافين", "", "#  اللاعب                  أهداف  تمريرات"]
    for i, p in enumerate(scorers[:15], 1):
        name = p["player"]["name"][:20]
        stats = p["statistics"][0]
        goals = stats["goals"]["total"] or 0
        assists = stats["goals"]["assists"] or 0
        lines.append(f"{i:<2} {name:<22} {goals:<6} {assists}")
    return "```\n" + "\n".join(lines) + "\n```"


def main():
    tomorrow_fixtures = get_tomorrow_fixtures()
    msg = format_fixtures_message(tomorrow_fixtures, "📅 مباريات الغد")
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)

    live = get_live_fixtures()
    if live:
        msg_live = format_fixtures_message(live, "🔴 مباريات جارية الآن")
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg_live)

    standings = get_standings()
    msg_standings = format_standings_message(standings)
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg_standings)

    scorers = get_top_scorers()
    msg_scorers = format_scorers_message(scorers)
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg_scorers)

    print("تم إرسال كل بيانات الرياضة.")


if __name__ == "__main__":
    main()
