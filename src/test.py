# src/import_players_espn.py

import os
import sys
import time
import requests
from typing import Any, Dict, List, Optional

from supabase import create_client, Client


# ============================================================
# الإعدادات
# ============================================================

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)

SOURCE = "espn"

# الدوريات الخمس الكبرى
LEAGUES = {
    "eng.1": "الدوري الإنجليزي",
    "esp.1": "الدوري الإسباني",
    "ita.1": "الدوري الإيطالي",
    "ger.1": "الدوري الألماني",
    "fra.1": "الدوري الفرنسي",
}

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"


# ============================================================
# أدوات مساعدة
# ============================================================

def log(message: str):
    print(f"[PLAYERS] {message}", flush=True)


def get_json(url: str, params: Optional[Dict[str, Any]] = None):
    response = requests.get(
        url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "football_news/1.0"
        },
    )

    response.raise_for_status()
    return response.json()


def normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""

    return " ".join(str(value).strip().split())


def get_player_id(athlete: Dict[str, Any]) -> Optional[str]:
    athlete_id = athlete.get("id")

    if athlete_id is None:
        return None

    return str(athlete_id)


# ============================================================
# جلب فرق الدوري من ESPN
# ============================================================

def get_league_teams(league_code: str) -> List[Dict[str, Any]]:
    url = f"{ESPN_BASE}/{league_code}/teams"

    data = get_json(url)

    sports = data.get("sports", [])

    if not sports:
        return []

    leagues = sports[0].get("leagues", [])

    if not leagues:
        return []

    teams = leagues[0].get("teams", [])

    result = []

    for item in teams:
        team = item.get("team", item)

        if team.get("id"):
            result.append(team)

    return result


# ============================================================
# البحث عن الفريق الموجود في قاعدة البيانات
# ============================================================

def find_db_team(espn_team_id: str):
    result = (
        supabase
        .table("teams")
        .select("id,source,source_team_id,name,name_ar,league")
        .eq("source", SOURCE)
        .eq("source_team_id", espn_team_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    # احتياطًا لو المصدر مختلف
    result = (
        supabase
        .table("teams")
        .select("id,source,source_team_id,name,name_ar,league")
        .eq("source_team_id", espn_team_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


# ============================================================
# جلب قائمة لاعبي الفريق
# ============================================================

def get_team_roster(
    league_code: str,
    team_id: str
) -> List[Dict[str, Any]]:

    url = f"{ESPN_BASE}/{league_code}/teams/{team_id}/roster"

    data = get_json(url)

    athletes = data.get("athletes", [])

    # بعض استجابات ESPN تكون مقسمة إلى مجموعات
    if not athletes:
        groups = data.get("groups", [])

        for group in groups:
            athletes.extend(group.get("athletes", []))

    return athletes


# ============================================================
# تجهيز بيانات اللاعب
# ============================================================

def build_player(
    athlete: Dict[str, Any],
    db_team: Dict[str, Any]
) -> Optional[Dict[str, Any]]:

    player_id = get_player_id(athlete)

    if not player_id:
        return None

    name = normalize_name(
        athlete.get("displayName")
        or athlete.get("fullName")
        or athlete.get("shortName")
    )

    if not name:
        return None

    position = None

    position_data = athlete.get("position")

    if isinstance(position_data, dict):
        position = (
            position_data.get("displayName")
            or position_data.get("name")
            or position_data.get("abbreviation")
        )
    elif isinstance(position_data, str):
        position = position_data

    photo_url = athlete.get("headshot")

    return {
        "source": SOURCE,
        "source_player_id": player_id,
        "name": name,
        "name_ar": None,
        "team_id": db_team["id"],
        "position": position,
        "photo_url": photo_url,
    }


# ============================================================
# فحص اللاعب قبل الإضافة
# ============================================================

def player_exists(source_player_id: str) -> bool:

    result = (
        supabase
        .table("players")
        .select("id")
        .eq("source", SOURCE)
        .eq("source_player_id", source_player_id)
        .limit(1)
        .execute()
    )

    return bool(result.data)


# ============================================================
# إضافة اللاعب بدون تكرار
# ============================================================

def insert_player(player: Dict[str, Any]) -> bool:

    if player_exists(player["source_player_id"]):
        return False

    supabase \
        .table("players") \
        .insert(player) \
        .execute()

    return True


# ============================================================
# تشغيل الاستيراد
# ============================================================

def main():

    log("=" * 60)
    log("IMPORT PLAYERS - ESPN")
    log("الدوريات الخمس الكبرى")
    log("=" * 60)

    total_found = 0
    total_added = 0
    total_existing = 0
    total_skipped = 0

    # منع تكرار نفس اللاعب داخل نفس التشغيل
    seen_players = set()

    for league_code, league_name in LEAGUES.items():

        log("")
        log(f"🏆 {league_name} ({league_code})")

        try:
            teams = get_league_teams(league_code)

        except Exception as exc:
            log(f"❌ فشل جلب فرق الدوري: {exc}")
            continue

        log(f"الفرق الموجودة في ESPN: {len(teams)}")

        for team in teams:

            espn_team_id = str(team.get("id"))

            db_team = find_db_team(espn_team_id)

            if not db_team:
                log(
                    f"⚠️ الفريق غير موجود في قاعدة البيانات: "
                    f"{team.get('displayName')} "
                    f"(ESPN ID: {espn_team_id})"
                )
                continue

            team_name = (
                db_team.get("name_ar")
                or db_team.get("name")
                or team.get("displayName")
            )

            log(f"  👥 {team_name}")

            try:
                roster = get_team_roster(
                    league_code,
                    espn_team_id
                )

            except Exception as exc:
                log(
                    f"    ❌ فشل جلب اللاعبين: {exc}"
                )
                continue

            log(f"    اللاعبين: {len(roster)}")

            for athlete in roster:

                player_id = get_player_id(athlete)

                if not player_id:
                    total_skipped += 1
                    continue

                # منع تكرار اللاعب داخل التشغيل
                if player_id in seen_players:
                    continue

                seen_players.add(player_id)

                total_found += 1

                player = build_player(
                    athlete,
                    db_team
                )

                if not player:
                    total_skipped += 1
                    continue

                try:

                    added = insert_player(player)

                    if added:
                        total_added += 1

                        log(
                            f"    ✅ {player['name']}"
                        )

                    else:
                        total_existing += 1

                        log(
                            f"    ↩️ موجود: {player['name']}"
                        )

                except Exception as exc:

                    log(
                        f"    ❌ خطأ في إضافة "
                        f"{player['name']}: {exc}"
                    )

            # عدم الضغط على ESPN بسرعة
            time.sleep(0.3)

    log("")
    log("=" * 60)
    log("اكتمل الاستيراد")
    log("=" * 60)
    log(f"إجمالي اللاعبين المكتشفين: {total_found}")
    log(f"تمت إضافة: {total_added}")
    log(f"كانوا موجودين: {total_existing}")
    log(f"تم تخطي: {total_skipped}")
    log("=" * 60)


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log("تم إيقاف البرنامج.")

    except Exception as exc:
        log(f"❌ خطأ قاتل: {exc}")
        sys.exit(1)
