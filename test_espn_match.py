import requests
import json
import sys


BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def get_match_summary(league, event_id):
    """
    يسحب تفاصيل مباراة واحدة من ESPN.
    مثال league:
    eng.1  = الدوري الإنجليزي
    esp.1  = الدوري الإسباني
    ger.1  = الدوري الألماني
    ita.1  = الدوري الإيطالي
    fra.1  = الدوري الفرنسي
    """

    url = f"{BASE_URL}/{league}/summary"

    response = requests.get(
        url,
        params={"event": event_id},
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    response.raise_for_status()

    return response.json()


def print_section(title, data):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)

    if isinstance(data, (dict, list)):
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def main():

    if len(sys.argv) < 3:
        print(
            "الاستخدام:\n"
            "python test_espn_match.py eng.1 EVENT_ID"
        )
        return

    league = sys.argv[1]
    event_id = sys.argv[2]

    print(f"جاري سحب المباراة من ESPN...")
    print(f"البطولة: {league}")
    print(f"Match ID: {event_id}")

    try:
        data = get_match_summary(league, event_id)

    except requests.RequestException as e:
        print(f"\n❌ فشل الاتصال بـ ESPN:")
        print(e)
        return

    print("\n✅ تم استلام البيانات")

    # -------------------------------------------------
    # المعلومات الأساسية
    # -------------------------------------------------

    header = data.get("header", {})

    print_section(
        "HEADER / MATCH",
        header
    )

    # -------------------------------------------------
    # الأحداث
    # -------------------------------------------------

    events = data.get("plays", [])

    print_section(
        f"MATCH EVENTS ({len(events)})",
        events
    )

    # -------------------------------------------------
    # إحصائيات المباراة
    # -------------------------------------------------

    boxscore = data.get("boxscore", {})

    print_section(
        "BOXSCORE",
        boxscore
    )

    # -------------------------------------------------
    # التشكيلات
    # -------------------------------------------------

    rosters = data.get("rosters", [])

    print_section(
        "ROSTERS",
        rosters
    )

    # -------------------------------------------------
    # الإحصائيات العامة
    # -------------------------------------------------

    leaders = data.get("leaders", [])

    print_section(
        "LEADERS",
        leaders
    )

    # -------------------------------------------------
    # حفظ JSON كامل
    # -------------------------------------------------

    filename = f"espn_match_{event_id}.json"

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 70)
    print(f"✅ تم حفظ JSON الكامل في: {filename}")
    print("=" * 70)


if __name__ == "__main__":
    main()
