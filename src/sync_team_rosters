from lib.config import COMPETITIONS, ESPN_BASE_URL, validate_environment
from lib.log import log
from lib.espn_client import espn_get
from lib.supabase_client import upsert, select


# ============================================================
# GET TEAMS PER COMPETITION (من المباريات المسحوبة بالفعل)
# ============================================================

def get_teams_for_competition(competition_id):

    matches = select(
        "matches",
        {
            "select": "home_team_id,away_team_id",
            "competition_id": f"eq.{competition_id}",
        },
    )

    team_ids = set()

    for m in matches:
        if m.get("home_team_id"):
            team_ids.add(m["home_team_id"])
        if m.get("away_team_id"):
            team_ids.add(m["away_team_id"])

    if not team_ids:
        return []

    ids = ",".join(str(t) for t in team_ids)

    return select(
        "teams",
        {"select": "id,name,source_id", "id": f"in.({ids})"},
    )


# ============================================================
# FETCH + PARSE ONE TEAM'S FULL ROSTER
# ============================================================

def get_team_roster(league_slug, source_team_id):

    url = f"{ESPN_BASE_URL}/{league_slug}/teams/{source_team_id}/roster"

    return espn_get(url)


def extract_athletes(roster_response):
    """ESPN بيرجّع الـ roster إما كقائمة مسطحة تحت 'athletes'،
    أو مقسّمة حسب المركز (كل عنصر فيه 'items'). بنتعامل مع
    الاحتمالين، ولو الشكل مختلف تمامًا بنطبعه للتشخيص."""

    athletes_field = roster_response.get("athletes")

    if not athletes_field:
        log(
            f"DEBUG: no 'athletes' key. "
            f"Top-level keys: {list(roster_response.keys())}"
        )
        return []

    # الحالة 1: قائمة مسطحة من اللاعبين مباشرة
    if athletes_field and "fullName" in (athletes_field[0] or {}):
        return athletes_field

    # الحالة 2: مقسّمة حسب المركز، كل عنصر فيه 'items'
    flat = []

    for group in athletes_field:

        items = group.get("items", [])

        if items and "fullName" not in items[0]:
            log(
                f"DEBUG: unexpected athlete item shape: "
                f"{list(items[0].keys()) if items else 'empty'}"
            )

        flat.extend(items)

    return flat


# ============================================================
# UPSERT PLAYERS
# ============================================================

def sync_team_players(team_db_id, team_source_id, league_slug):

    try:
        roster_response = get_team_roster(league_slug, team_source_id)
    except Exception as error:
        log(
            f"ERROR fetching roster team={team_source_id} "
            f"({league_slug}): {error}"
        )
        return 0

    athletes = extract_athletes(roster_response)

    if not athletes:
        return 0

    records = []

    for athlete in athletes:

        source_id = str(athlete.get("id") or "")
        name = athlete.get("fullName") or athlete.get("displayName")

        if not source_id or not name:
            continue

        position = (
            (athlete.get("position") or {}).get("name")
        )

        jersey = athlete.get("jersey")

        nationality = (
            (athlete.get("citizenship"))
            or (athlete.get("birthPlace") or {}).get("country")
        )

        records.append({
            "source": "espn",
            "source_id": source_id,
            "name": name,
            "position": position,
            "jersey_number": str(jersey) if jersey else None,
            "nationality": nationality,
            "current_team_id": team_db_id,
        })

    if records:
        upsert("players", records, on_conflict="source,source_id")

    return len(records)


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("SYNC TEAM ROSTERS START")
    log("==================================================")

    competitions = select(
        "competitions", {"select": "id,name,source_id"}
    )

    total = 0

    for competition in competitions:

        league_slug = competition["source_id"]
        competition_name = competition["name"]

        teams = get_teams_for_competition(competition["id"])

        log(f"--- {competition_name}: {len(teams)} teams ---")

        for team in teams:

            count = sync_team_players(
                team["id"], team["source_id"], league_slug
            )

            log(f"  {team['name']}: {count} players")

            total += count

    log("==================================================")
    log(f"TOTAL players synced: {total}")
    log("SYNC TEAM ROSTERS END")
    log("==================================================")


if __name__ == "__main__":
    main()
