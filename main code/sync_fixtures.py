from datetime import datetime, timedelta

from lib.config import (
    TIMEZONE, COMPETITIONS, COMPETITION_COUNTRY, validate_environment,
)
from lib.log import log
from lib.espn_client import get_scoreboard
from lib.supabase_client import upsert, select


# ============================================================
# COMPETITIONS + SEASONS
# ============================================================

def ensure_competition(name, league_slug):

    rows = upsert(
        "competitions",
        [{
            "name": name,
            "country": COMPETITION_COUNTRY.get(name),
            "source": "espn",
            "source_id": league_slug,
        }],
        on_conflict="source,source_id",
        return_rows=True,
    )

    return rows[0]["id"]


def ensure_season(competition_id, league_slug):

    year = datetime.now(TIMEZONE).year

    rows = upsert(
        "seasons",
        [{
            "competition_id": competition_id,
            "name": str(year),
            "season_year": year,
            "source": "espn",
            "source_id": f"{league_slug}-{year}",
        }],
        on_conflict="source,source_id",
        return_rows=True,
    )

    return rows[0]["id"]


# ============================================================
# TEAMS
# ============================================================

def extract_teams(scoreboard):

    teams = {}

    for event in scoreboard.get("events", []):

        competitions = event.get("competitions", [])

        if not competitions:
            continue

        for competitor in competitions[0].get("competitors", []):

            team = competitor.get("team") or {}
            team_id = team.get("id")

            if not team_id:
                continue

            teams[str(team_id)] = {
                "name": team.get("displayName") or team.get("name"),
                "logo": team.get("logo"),
                "source": "espn",
                "source_id": str(team_id),
            }

    return list(teams.values())


def upsert_teams(scoreboard):

    records = extract_teams(scoreboard)

    if not records:
        return {}

    upsert("teams", records, on_conflict="source,source_id")

    ids = [r["source_id"] for r in records]

    rows = select(
        "teams",
        {
            "select": "id,source_id",
            "source": "eq.espn",
            "source_id": f"in.({','.join(ids)})",
        },
    )

    return {row["source_id"]: row["id"] for row in rows}


# ============================================================
# MATCHES
# ============================================================

def normalize_status(event):

    status = (
        event.get("status", {})
        .get("type", {})
        .get("state")
    )

    mapping = {
        "pre": "SCHEDULED",
        "in": "IN_PROGRESS",
        "post": "FINISHED",
    }

    return mapping.get(status, "SCHEDULED")


def extract_matches(scoreboard, competition_id, season_id, team_db_ids):

    records = []

    for event in scoreboard.get("events", []):

        competitions = event.get("competitions", [])

        if not competitions:
            continue

        comp = competitions[0]

        competitors = comp.get("competitors", [])

        home = next(
            (c for c in competitors if c.get("homeAway") == "home"),
            None,
        )

        away = next(
            (c for c in competitors if c.get("homeAway") == "away"),
            None,
        )

        if not home or not away:
            continue

        home_team_id = team_db_ids.get(
            str((home.get("team") or {}).get("id"))
        )

        away_team_id = team_db_ids.get(
            str((away.get("team") or {}).get("id"))
        )

        home_score = home.get("score")
        away_score = away.get("score")

        winner = None

        status = normalize_status(event)

        if status == "FINISHED" and home_score is not None:

            home_score_i = int(home_score)
            away_score_i = int(away_score)

            if home_score_i > away_score_i:
                winner = "home"
            elif away_score_i > home_score_i:
                winner = "away"
            else:
                winner = "draw"

        records.append({
            "competition_id": competition_id,
            "season_id": season_id,
            "home_team_id": home_team_id,
            "away_team_id": away_team_id,
            "kickoff_at": event.get("date"),
            "status": status,
            "home_score": (
                int(home_score) if home_score is not None else None
            ),
            "away_score": (
                int(away_score) if away_score is not None else None
            ),
            "winner": winner,
            "source": "espn",
            "source_id": str(event.get("id")),
        })

    return records


# ============================================================
# MAIN SYNC
# ============================================================

def get_target_dates():
    """أمس + اليوم + بكرة، بصيغة YYYYMMDD اللي ESPN بيحتاجها."""

    today = datetime.now(TIMEZONE).date()

    return [
        (today + timedelta(days=offset)).strftime("%Y%m%d")
        for offset in (-1, 0, 1)
    ]


def sync_competition(name, league_slug):

    log(f"--- {name} ({league_slug}) ---")

    competition_id = ensure_competition(name, league_slug)
    season_id = ensure_season(competition_id, league_slug)

    total_matches = 0

    for date_str in get_target_dates():

        try:
            scoreboard = get_scoreboard(league_slug, date_str)
        except Exception as error:
            log(f"ERROR scoreboard {league_slug} {date_str}: {error}")
            continue

        team_db_ids = upsert_teams(scoreboard)

        match_records = extract_matches(
            scoreboard, competition_id, season_id, team_db_ids
        )

        if match_records:
            upsert(
                "matches", match_records, on_conflict="source,source_id"
            )
            total_matches += len(match_records)

    log(f"{name}: {total_matches} match rows upserted")

    return total_matches


def main():

    validate_environment()

    log("==================================================")
    log("SYNC FIXTURES START")
    log("==================================================")

    total = 0

    for name, league_slug in COMPETITIONS.items():

        try:
            total += sync_competition(name, league_slug)
        except Exception as error:
            log(f"ERROR syncing {name}: {error}")
            continue

    log("==================================================")
    log(f"TOTAL match rows upserted: {total}")
    log("SYNC FIXTURES END")
    log("==================================================")


if __name__ == "__main__":
    main()
