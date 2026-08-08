"""
جلب بيانات الفانتازي الرسمية من FPL Official API (مجاني، بدون مفتاح)
أسعار اللاعبين، نسب الملكية، حالة الإصابة
"""
import requests


def get_all_players(fpl_base):
    """يرجع قائمة كل اللاعبين ببياناتهم (سعر، ملكية، حالة) دفعة واحدة"""
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
                "price": p["now_cost"] / 10,  # FPL بيخزن السعر × 10
                "ownership_percent": p["selected_by_percent"],
                "status": p["status"],  # 'a' = متاح، 'i' = مصاب، 'd' = شكوك، 's' = موقوف
                "news": p.get("news", ""),  # تفاصيل الإصابة لو موجودة
                "total_points": p["total_points"],
                "form": p["form"],
            })
        return players
    except Exception as e:
        print(f"  خطأ في جلب بيانات FPL: {e}")
        return []


def get_available_players(fpl_base):
    """نفس get_all_players بس بيستبعد المصابين والموقوفين تلقائياً"""
    all_players = get_all_players(fpl_base)
    return [p for p in all_players if p["status"] == "a"]
