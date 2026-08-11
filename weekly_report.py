"""
تقرير أسبوعي: فقرة موجزة لكل خبر عن كل نادي (معتمدة على نص الخبر نفسه فقط، بدون تأليف)
+ تحليل مستوى الدوريات بناءً على الترتيب.
"""
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


def build_league_report_prompt(league_name, standings):
    top5 = standings[:5]
    lines = [f"{t['rank']}. {t['team']['name']} - {t['points']} نقطة" for t in top5]
    standings_text = "\n".join(lines)

    return f"""انت محلل رياضي محترف. بناءً على ترتيب {league_name} الحالي فقط:

{standings_text}

اكتب فقرة تحليلية قصيرة (3-4 جمل) عن وضع الصدارة والمنافسة بناءً على الأرقام دي فقط. ممنوع ذكر أي أسماء مدربين أو تصريحات أو أحداث مش موجودة في الجدول أعلاه."""


def build_single_article_summary_prompt(article_body):
    return f"""لخّص الخبر ده في فقرة واحدة قصيرة (سطرين بس)، معتمداً فقط على المعلومات المذكورة فيه حرفياً. ممنوع إضافة أي تفصيلة أو اسم أو تصريح مش موجود في النص. رجّع الفقرة فقط بدون أي شرح إضافي.

الخبر: {article_body}"""


def main():
    # تقارير الدوريات (زي الأول، آمنة لأنها مبنية على أرقام فقط)
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

    # تقارير الأندية: فقرة واحدة لكل خبر، مش تلخيص مجمّع
    for club_arabic, club_english in config.TRACKED_CLUBS:
        articles = supabase_client.get_articles_by_club(
            config.SUPABASE_URL, config.SUPABASE_KEY, club_arabic, days=7, limit=10
        )
        if not articles:
            print(f"مفيش أخبار مصنّفة لـ {club_arabic} الأسبوع ده، تخطي.")
            continue

        paragraphs = []
        for article in articles:
            body = article.get("body", "")
            if not body:
                continue
            summary = gemini.call_gemini(
                build_single_article_summary_prompt(body), config.GEMINI_API_KEY, config.GLM_API_KEY
            )
            if summary:
                paragraphs.append(summary.strip())

        if not paragraphs:
            continue

        numbered = "\n\n".join(f"{i}. {p}" for i, p in enumerate(paragraphs, 1))
        message = f"⚽ أهم أخبار {club_arabic} هذا الأسبوع\n\n{numbered}"
        telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
        print(f"تم إرسال تقرير {club_arabic} ({len(paragraphs)} فقرة)")

    print("انتهى التقرير الأسبوعي الكامل.")


if __name__ == "__main__":
    main()
