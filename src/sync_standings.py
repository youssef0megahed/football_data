from lib.config import validate_environment
from lib.log import log
from lib.supabase_client import upsert, select


# ============================================================
# COMPUTE STANDINGS FOR ONE SEASON
# ============================================================

def compute_standings(season_id):

    all_matches = select(
        "matches",
        {
            "select": (
                "home_team_id,away_team_id,home_score,"
                "away_score,status"
            ),
            "season_id": f"eq.{season_id}",
        },
    )

    table = {}

    def ensure_team(team_id):

        if team_id not in table:
            table[team_id] = {
                "team_id": team_id,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
            }

        return table[team_id]

    # الخطوة 1: نضمن ظهور كل فريق ليه ماتش في الموسم ده، حتى لو
    # لسه ما لعبش (هيبان بصفوف صفر لحد ما يلعب).
    for match in all_matches:

        if match.get("home_team_id"):
            ensure_team(match["home_team_id"])

        if match.get("away_team_id"):
            ensure_team(match["away_team_id"])

    # الخطوة 2: نجمع الإحصائيات بس من المباريات المنتهية فعليًا.
    for match in all_matches:

        if match.get("status") != "FINISHED":
            continue

        home_id = match.get("home_team_id")
        away_id = match.get("away_team_id")

        home_score = match.get("home_score")
        away_score = match.get("away_score")

        if (
            not home_id
            or not away_id
            or home_score is None
            or away_score is None
        ):
            continue

        home = ensure_team(home_id)
        away = ensure_team(away_id)

        home["played"] += 1
        away["played"] += 1

        home["goals_for"] += home_score
        home["goals_against"] += away_score

        away["goals_for"] += away_score
        away["goals_against"] += home_score

        if home_score > away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif away_score > home_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1

    rows = []

    for team in table.values():

        goal_diff = team["goals_for"] - team["goals_against"]
        points = team["wins"] * 3 + team["draws"]

        rows.append({
            **team,
            "goal_difference": goal_diff,
            "points": points,
        })

    # الترتيب: نقاط، فارق أهداف، أهداف مسجلة (ترتيب دوري معتاد)
    rows.sort(
        key=lambda r: (
            -r["points"],
            -r["goal_difference"],
            -r["goals_for"],
        )
    )

    for index, row in enumerate(rows, start=1):
        row["rank"] = index
        row["season_id"] = season_id

    return rows


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    log("==================================================")
    log("SYNC STANDINGS START")
    log("==================================================")

    seasons = select("seasons", {"select": "id,name,competition_id"})

    for season in seasons:

        season_id = season["id"]

        rows = compute_standings(season_id)

        if not rows:
            log(
                f"season={season_id} ({season.get('name')}): "
                f"no finished matches yet, skipping."
            )
            continue

        upsert("standings", rows, on_conflict="season_id,team_id")

        log(
            f"season={season_id} ({season.get('name')}): "
            f"{len(rows)} team rows updated"
        )

    log("==================================================")
    log("SYNC STANDINGS END")
    log("==================================================")


if __name__ == "__main__":
    main()
