"""
تحليل أسبوعي يجمع بيانات api-football (فورمة/إحصائيات) مع FPL API (سعر/ملكية/إصابة)
لترشيح أفضل 5 لاعبين للجولة الجاية.
"""
import requests
import config
from utils import gemini, telegram, fpl

HEADERS = {
    "x-rapidapi-key": config.RAPIDAPI_KEY,
    "x-rapidapi-host": config.API_FOOTBALL_HOST,
}


def get_fixtures():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/fixtures", headers=HEADERS,
                         params={"league": config.LEAGUE_ID, "season": config.SEASON, "next": 10}, timeout=20)
    if resp.status_code != 200:
        return []
    return resp.json().get("response", [])


def get_players_stats():
    resp = requests.get(f"{config.API_FOOTBALL_BASE}/players", headers=HEADERS,
                         params={"league": config.LEAGUE_ID, "season": config.SEASON, "page": 1}, timeout=20)
    if resp.status_code != 200:
        return []
    return resp.json().get("response", [])


def merge_stats_with_fpl(api_football_players, fpl_players):
    """يدمج إحصائيات api-football مع بيانات FPL (سعر/ملكية/إصابة) حسب اسم اللاعب"""
    fpl_by_name = {p["name"].lower(): p for p in fpl_players}
    merged = []
    for p in api_football_players[:40]:
        name = p["player"]["name"]
        fpl_match = fpl_by_name.get(name.lower())
        stats = p["statistics"][0] if p.get("statistics") else {}
        entry = {
            "name": name,
            "team": stats.get("team", {}).get("name", ""),
            "goals": stats.get("goals", {}).get("total", 0) or 0,
            "rating": stats.get("games", {}).get("rating", "غير متاح"),
        }
        if fpl_match:
            entry["price"] = fpl_match["price"]
            entry["ownership_percent"] = fpl_match["ownership_percent"]
            entry["status"] = fpl_match["status"]
            entry["injury_news"] = fpl_match["news"]
        merged.append(entry)
    return merged


def build_analysis_prompt(fixtures, merged_players):
    fixtures_summary = "\n".join(
        f"{f['teams']['home']['name']} ضد {f['teams']['away']['name']}" for f in fixtures[:10]
    )

    players_lines = []
    for p in merged_players:
        line = f"{p['name']} ({p['team']}) - أهداف: {p['goals']}, تقييم: {p['rating']}"
        if "price" in p:
            line += f", سعر: £{p['price']}م, نسبة ملكية: {p['ownership_percent']}%"
            if p["status"] != "a":
                line += f", ⚠️ حالة: {p['injury_news'] or 'غير متاح للعب'}"
        players_lines.append(line)
    players_summary = "\n".join(players_lines)

    return f"""انت محلل فانتازي كورة قدم محترف. بناءً على البيانات دي:

المباريات القادمة:
{fixtures_summary}

إحصائيات وبيانات اللاعبين:
{players_summary}

رشح أفضل 5 لاعبين للشراء في الجولة القادمة. استبعد أي لاعب مصاب أو موقوف تماماً. خد بالك من نسبة الملكية (لاعب بملكية منخفضة وأداء قوي = فرصة مميزة). لكل ترشيح اكتب سبب مختصر. رجّع الرد بصيغة JSON فقط: {{"recommendations": [{{"name": "...", "reason": "..."}}]}}"""


def build_review_prompt(analysis_text):
    return f"""راجع الترشيحات دي. تأكد إن مفيش لاعب مصاب أو موقوف ضمنهم، وإن الأسباب منطقية. لو فيه مشكلة صححها. رجّع بنفس صيغة JSON: {{"recommendations": [{{"name": "...", "reason": "..."}}]}}

الترشيحات: {analysis_text}"""


def format_message(recommendations_text):
    import json
    import re
    try:
        cleaned = re.sub(r"```json|```", "", recommendations_text).strip()
        parsed = json.loads(cleaned)
        lines = ["⚽ توقعات فانتازي الجولة القادمة", ""]
        for i, r in enumerate(parsed.get("recommendations", []), 1):
            lines.append(f"{i}. {r['name']}")
            lines.append(f"   {r['reason']}")
            lines.append("")
        return "\n".join(lines)
    except Exception:
        return "⚽ توقعات فانتازي الجولة القادمة\n\n" + recommendations_text


def main():
    fixtures = get_fixtures()
    api_players = get_players_stats()
    fpl_players = fpl.get_all_players(config.FPL_BASE)

    if not fixtures or not api_players:
        print("مفيش بيانات كافية من api-football، توقف.")
        return

    merged = merge_stats_with_fpl(api_players, fpl_players)

    analysis = gemini.call_gemini(build_analysis_prompt(fixtures, merged), config.GEMINI_API_KEY, config.GEMINI_MODELS)
    if not analysis:
        print("فشل التحليل الأول.")
        return

    reviewed = gemini.call_gemini(build_review_prompt(analysis), config.GEMINI_API_KEY, config.GEMINI_MODELS)
    final_text = reviewed or analysis

    message = format_message(final_text)
    telegram.send_message(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID, message)
    print("تم إرسال توقعات الفانتازي.")


if __name__ == "__main__":
    main()
