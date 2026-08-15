"""
جلب بيانات الفانتازي الرسمية من FPL Official API (مجاني، بدون مفتاح)
"""
import requests


def get_all_players(fpl_base):
    url = f"{fpl_base}/bootstrap-static/"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code != 200:
            print(f"  خطأ في جلب بيانات FPL: {resp.status_code}")
            return []
        data = resp.json()
        teams = {t["id"]: t["name"] for t in data.get("teams", [])}
        players = []
        for p in data.get("elements", []):
            players.append({
                "name": f"{p['first_name']} {p['second_name']}",
                "team": teams.get(p["team"], ""),
                "price": p["now_cost"] / 10,
                "ownership_percent": p["selected_by_percent"],
                "status": p["status"],
                "news": p.get("news", ""),
            })
        return players
    except Exception as e:
        print(f"  خطأ في جلب بيانات FPL: {e}")
        return []


def get_status_changes(fpl_base):
    """يرجع بس اللاعبين اللي عندهم حالة مش طبيعية (إصابة/شك/إيقاف) مع خبر مرفق"""
    players = get_all_players(fpl_base)
    return [p for p in players if p["status"] != "a" and p["news"]]
