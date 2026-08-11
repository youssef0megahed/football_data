"""
تقرير أسبوعي: تحليل مستوى الدوريات الست + الأندية المتابعة، بناءً على:
- بيانات api-football (ترتيب، نتائج)
- أرشيف الأخبار في Supabase (تغطية كل نادي خلال الأسبوع)
"""
import datetime
import requests
import config
from utils import gemini, telegram, supabase_client

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_standings(league_id):
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/standings", headers=HEADERS,
                         params={"league": league_id, "season": config.SEASON}, timeout=20)
    if resp.status_code != 200:
        return []
    try:
        return resp.json()["response"][0]["league"]["standings"][0]
    except (KeyError, IndexError):
        return []


def get_club_articles(club_arabic_name, days=7):
    """يجيب أخبار الأسبوع اللي فيها اسم النادي ده من Supabase"""
    since = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
    url = f"{config.SUPABASE_URL}/rest/v1/articles"
    headers = {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
    }
    params = {
        "select": "title,body,created_at",
        "or": f"(title.ilike.*{club_arabic_name}*,body.ilike.*{club_arabic_name}*)",
        "created_at": f"gte.{since}",
    }
    resp = requests.get(url, headers=headers, params=params, timeout=20)
    return resp.json() if resp.status_code == 200 else []


def build_league_report_prompt(league_name, standings):
    top5 = standings[:5]
    lines = [f"{t['rank']}. {t['team']['name']} - {t['points']} نقطة" for t in top5]
    standings_text = "\n".join(lines)

    return f"""انت محلل رياضي محترف. بناءً على ترتيب {league_name} الحالي:

{standings_text}

اكتب فقرة تحليلية قصيرة (3-4 جمل) عن وضع الصدارة والمنافسة حالياً في الدوري ده. أسلوب صحفي جذاب."""


def build_club_report_prompt(club_name, articles):
    if not articles:
        return None
    titles = [a["title"] for a in articles[:10] if a.get("title")]
    titles_text = "\n".join(f"- {t}" for t in titles)

    return f"""انت محلل رياضي محترف. دي عناوين الأخبار اللي اتغطت عن {club_name} خلال الأسبوع الماضي:

{titles_text}

اكتب فقرة ملخصة (3-4 جمل) عن أبرز أحداث الأسبوع بتاعة النادي ده، بأسلوب صحفي جذاب."""


def main():
    # تقارير الدوريات
    for league_name, league_id in config.LEAGUE_IDS.items():
        standings = get_standings(league_id)
        if not standings:
            print(f"مفيش بيانات ترتيب لـ {league_name}، تخطي.")
            continue

        prompt = build_league_report_prompt(league_name, standings)
        analysis = gemini.call_gemini(prompt, config.GEMINI_API_KEY, config.GLM_API_KEY)
        analysis = analysis or "مفيش تحليل متاح حالياً."

        message = f"📊 تقرير أسبوعي: {league_name}\n\n{analysis}"
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
        print(f"تم إرسال تقرير {league_name}")

    # تقارير الأندية
    for club_arabic, club_api_name in config.TRACKED_CLUBS:
        articles = get_club_articles(club_arabic)
        if not articles:
            print(f"مفيش أخبار عن {club_arabic} الأسبوع ده، تخطي.")
            continue

        prompt = build_club_report_prompt(club_arabic, articles)
        analysis = gemini.call_gemini(prompt, config.GEMINI_API_KEY, config.GLM_API_KEY)
        if not analysis:
            continue

        message = f"⚽ تقرير أسبوعي: {club_arabic}\n\n{analysis}\n\n(عدد الأخبار المغطاة: {len(articles)})"
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
        print(f"تم إرسال تقرير {club_arabic}")

    print("انتهى التقرير الأسبوعي الكامل.")


if __name__ == "__main__":
    main()
