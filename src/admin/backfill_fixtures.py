import sys
import time
from datetime import datetime, timedelta

from lib.config import TIMEZONE, COMPETITIONS, validate_environment
from lib.log import log
from lib.espn_client import get_scoreboard
from lib.supabase_client import upsert

from sync.fixtures import (
    ensure_competition, ensure_season, upsert_teams, extract_matches,
)


def date_range(start_date, end_date):

    days = (end_date - start_date).days

    return [
        (start_date + timedelta(days=i)).strftime("%Y%m%d")
        for i in range(days + 1)
    ]


def main():

    validate_environment()

    start_str = sys.argv[1] if len(sys.argv) > 1 else "2026-08-01"

    start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
    end_date = datetime.now(TIMEZONE).date()

    if start_date > end_date:
        raise RuntimeError("start_date is in the future")

    dates = date_range(start_date, end_date)

    log("==================================================")
    log(
        f"BACKFILL START: {start_date.isoformat()} -> "
        f"{end_date.isoformat()} ({len(dates)} days)"
    )
    log("==================================================")

    for name, league_slug in COMPETITIONS.items():

        log(f"--- {name} ({league_slug}) ---")

        competition_id = ensure_competition(name, league_slug)
        season_id = ensure_season(competition_id, league_slug)

        total = 0

        for date_str in dates:

            try:
                scoreboard = get_scoreboard(league_slug, date_str)
            except Exception as error:
                log(f"ERROR {name} {date_str}: {error}")
                continue

            team_db_ids = upsert_teams(scoreboard)

            records = extract_matches(
                scoreboard, competition_id, season_id, team_db_ids
            )

            if records:
                upsert(
                    "matches", records, on_conflict="source,source_id"
                )
                total += len(records)

            # كن لطيف مع ESPN — مفيش داعي نضربه بسرعة قصوى
            time.sleep(0.3)

        log(f"{name}: {total} match rows backfilled")

    log("==================================================")
    log("BACKFILL END")
    log("==================================================")


if __name__ == "__main__":
    main()
  
