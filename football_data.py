"""
سحب بيانات كرة القدم من api-football وإرسال ترتيب الدوري كصورة احترافية.
"""
import datetime
import requests
import config
from utils import telegram

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_upcoming_fixtures():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"league": config.LEAGUE_ID, "season": config.SEASON, "next": 10}, timeout=20)
    if resp.status_code != 200:
        print(f"خطأ في جلب المباريات القادمة: {resp.status_code} - {resp.text[:300]}")
        return []
    data = resp.json()
    if data.get("errors"):
        print(f"تحذير من API: {data['errors']}")
    return data.get("response", [])


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
        return f"{title}\n\nمفيش مباريات قادمة متاحة حالياً."
    lines = [title, ""]
    for f in fixtures[:15]:
        home = f["teams"]["home"]["name"]
        away = f["teams"]["away"]["name"]
        time_str = f["fixture"]["date"][11:16]
        date_str = f["fixture"]["date"][:10]
        lines.append(f"{home} vs {away}  |  {date_str} - {time_str}")
    return "\n".join(lines)


def build_standings_html(standings):
    rows_html = ""
    for team in standings[:20]:
        rows_html += f"""
        <tr>
          <td>{team['rank']}</td>
          <td class="team-name">{team['team']['name']}</td>
          <td>{team['points']}</td>
          <td>{team['all']['played']}</td>
          <td>{team['all']['win']}</td>
          <td>{team['all']['draw']}</td>
          <td>{team['all']['lose']}</td>
        </tr>"""

    return f"""
    <div class="wrapper">
      <h1>🏆 ترتيب الدوري</h1>
      <table>
        <thead>
          <tr><th>#</th><th>الفريق</th><th>نقط</th><th>لعب</th><th>فوز</th><th>تعادل</th><th>خسارة</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


def build_standings_css():
    return """
    body { margin: 0; font-family: 'Tahoma', sans-serif; direction: rtl; }
    .wrapper { background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 30px; width: 700px; }
    h1 { color: #fff; text-align: center; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; }
    th { background: #0d1b2a; color: #fff; padding: 12px 8px; font-size: 15px; }
    td { padding: 10px 8px; text-align: center; border-bottom: 1px solid #eee; font-size: 14px; }
    .team-name { text-align: right; font-weight: bold; }
    tr:nth-child(even) { background: #f5f7fa; }
    """


def generate_standings_image(standings):
    html = build_standings_html(standings)
    css = build_standings_css()
    resp = requests.post(
        "https://hcti.io/v1/image",
        data={"html": html, "css": css},
        auth=(config.HCTI_USER_ID, config.HCTI_API_KEY),
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("url")
    print(f"خطأ في توليد صورة الترتيب: {resp.status_code} - {resp.text[:300]}")
    return None


def build_scorers_html(scorers):
    rows_html = ""
    for i, p in enumerate(scorers[:15], 1):
        stats = p["statistics"][0]
        goals = stats["goals"]["total"] or 0
        assists = stats["goals"]["assists"] or 0
        rows_html += f"""
        <tr>
          <td>{i}</td>
          <td class="team-name">{p['player']['name']}</td>
          <td>{stats.get('team', {}).get('name', '')}</td>
          <td>{goals}</td>
          <td>{assists}</td>
        </tr>"""

    return f"""
    <div class="wrapper">
      <h1>⚽ قائمة الهدافين</h1>
      <table>
        <thead>
          <tr><th>#</th><th>اللاعب</th><th>الفريق</th><th>أهداف</th><th>تمريرات</th></tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""


def generate_scorers_image(scorers):
    html = build_scorers_html(scorers)
    css = build_standings_css()
    resp = requests.post(
        "https://hcti.io/v1/image",
        data={"html": html, "css": css},
        auth=(config.HCTI_USER_ID, config.HCTI_API_KEY),
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("url")
    print(f"خطأ في توليد صورة الهدافين: {resp.status_code} - {resp.text[:300]}")
    return None


def main():
    upcoming = get_upcoming_fixtures()
    msg = format_fixtures_message(upcoming, "📅 المباريات القادمة")
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, msg)

    standings = get_standings()
    if standings:
        img_url = generate_standings_image(standings)
        if img_url:
            telegram.send_photo(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, img_url, "🏆 ترتيب الدوري")
        else:
            telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, "فشل توليد صورة الترتيب")
    else:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, "🏆 مفيش بيانات ترتيب متاحة حالياً")

    scorers = get_top_scorers()
    if scorers:
        img_url = generate_scorers_image(scorers)
        if img_url:
            telegram.send_photo(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, img_url, "⚽ قائمة الهدافين")
        else:
            telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, "فشل توليد صورة الهدافين")
    else:
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, "⚽ مفيش بيانات هدافين متاحة حالياً")

    print("تم إرسال كل بيانات الرياضة.")


if __name__ == "__main__":
    main()
