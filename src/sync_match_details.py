from datetime import datetime, timedelta

from lib.config import TIMEZONE, COMPETITIONS, validate_environment
from lib.log import log
from lib.espn_client import get_summary
from lib.supabase_client import upsert, select


# ============================================================
# STAT FIELD MAPPINGS (confirmed against real ESPN responses)
# ============================================================

TEAM_STAT_MAP = {
    "foulsCommitted": "fouls_committed",
    "yellowCards": "yellow_cards",
    "redCards": "red_cards",
    "offsides": "offsides",
    "wonCorners": "corners",
    "saves": "saves",
    "possessionPct": "possession_pct",
    "totalShots": "total_shots",
    "shotsOnTarget": "shots_on_target",
    "shotPct": "shot_pct",
    "penaltyKickGoals": "penalty_goals",
    "penaltyKickShots": "penalty_shots",
    "accuratePasses": "accurate_passes",
    "totalPasses": "total_passes",
    "passPct": "pass_pct",
    "accurateCrosses": "accurate_crosses",
    "totalCrosses": "total_crosses",
    "crossPct": "cross_pct",
    "totalLongBalls": "total_long_balls",
    "accurateLongBalls": "accurate_long_balls",
    "longballPct": "long_ball_pct",
    "blockedShots": "blocked_shots",
    "effectiveTackles": "effective_tackles",
    "totalTackles": "total_tackles",
    "tacklePct": "tackle_pct",
    "interceptions": "interceptions",
    "effectiveClearance": "effective_clearances",
    "totalClearance": "total_clearances",
}

PLAYER_STAT_MAP = {
    "appearances": "appearances",
    "foulsCommitted": "fouls_committed",
    "foulsSuffered": "fouls_suffered",
    "yellowCards": "yellow_cards",
    "redCards": "red_cards",
    "goalsConceded": "goals_conceded",
    "saves": "saves",
    "shotsFaced": "shots_faced",
    "goalAssists": "goal_assists",
    "shotsOnTarget": "shots_on_target",
    "totalGoals": "total_goals",
    "totalShots": "total_shots",
}


def stat_value(stat):
    """يرجع رقم من عنصر إحصائية ESPN (value لو موجودة، وإلا displayValue)."""

    if stat.get("value") is not None:
        return stat["value"]

    display = stat.get("displayValue")

    try:
        return float(display)
    except (TypeError, ValueError):
        return None


def map_stats(stat_list, field_map):

    mapped = {}

    for stat in stat_list:

        name = stat.get("name")

        if name in field_map:
            mapped[field_map[name]] = stat_value(stat)

    return mapped


# ============================================================
# PLAYER UPSERT HELPER (shared across lineups/stats/events)
# ============================================================

def upsert_players_get_ids(athletes, team_db_id):
    """athletes: list of ESPN athlete dicts (لازم فيها id + fullName).
    بيرجع {source_player_id: internal_players_id}."""

    records = []

    for athlete in athletes:

        source_id = str(athlete.get("id") or "")
        name = athlete.get("fullName") or athlete.get("displayName")

        if not source_id or not name:
            continue

        records.append({
            "source": "espn",
            "source_id": source_id,
            "name": name,
            "current_team_id": team_db_id,
        })

    if not records:
        return {}

    upsert("players", records, on_conflict="source,source_id")

    ids = list({r["source_id"] for r in records})

    rows = select(
        "players",
        {
            "select": "id,source_id",
            "source": "eq.espn",
            "source_id": f"in.({','.join(ids)})",
        },
    )

    return {row["source_id"]: row["id"] for row in rows}


def get_team_db_id(source_team_id):

    if not source_team_id:
        return None

    rows = select(
        "teams",
        {
            "select": "id",
            "source": "eq.espn",
            "source_id": f"eq.{source_team_id}",
        },
    )

    return rows[0]["id"] if rows else None


# ============================================================
# TEAM STATS (boxscore)
# ============================================================

def sync_team_stats(match_db_id, summary):

    boxscore = summary.get("boxscore") or {}

    records = []

    for team_block in boxscore.get("teams", []):

        source_team_id = str(
            (team_block.get("team") or {}).get("id") or ""
        )

        team_db_id = get_team_db_id(source_team_id)

        if not team_db_id:
            continue

        stat_list = team_block.get("statistics", [])

        record = {
            "match_id": match_db_id,
            "team_id": team_db_id,
            "home_away": team_block.get("homeAway"),
            "raw_stats": stat_list,
        }

        record.update(map_stats(stat_list, TEAM_STAT_MAP))

        records.append(record)

    if records:
        upsert("match_stats", records, on_conflict="match_id,team_id")

    return len(records)


# ============================================================
# ROSTERS -> LINEUPS + PLAYER STATS
# ============================================================

def sync_rosters(match_db_id, summary):

    rosters = summary.get("rosters") or []

    if not rosters:
        log(
            f"DEBUG match={match_db_id}: no 'rosters' key/empty. "
            f"Top-level summary keys: {list(summary.keys())}"
        )

    lineup_records = []
    player_stat_records = []

    for team_roster in rosters:

        source_team_id = str(
            (team_roster.get("team") or {}).get("id") or ""
        )

        team_db_id = get_team_db_id(source_team_id)

        roster = team_roster.get("roster", [])

        if not roster:
            log(
                f"DEBUG match={match_db_id} team={source_team_id}: "
                f"team_db_id={team_db_id}, roster empty. "
                f"team_roster keys: {list(team_roster.keys())}"
            )

        athletes = [
            entry.get("athlete", {})
            for entry in roster
            if entry.get("athlete")
        ]

        player_ids = upsert_players_get_ids(athletes, team_db_id)

        formation = team_roster.get("formation")
        home_away = team_roster.get("homeAway")

        for entry in roster:

            athlete = entry.get("athlete") or {}
            source_player_id = str(athlete.get("id") or "")

            player_db_id = player_ids.get(source_player_id)

            if not player_db_id:
                continue

            position = (
                (entry.get("position") or {}).get("name")
            )

            lineup_records.append({
                "match_id": match_db_id,
                "team_id": team_db_id,
                "home_away": home_away,
                "formation": formation,
                "player_id": player_db_id,
                "jersey_number": entry.get("jersey"),
                "position": position,
                "starter": bool(entry.get("starter")),
            })

            stat_list = entry.get("stats", [])

            if not stat_list:

                athlete_name = athlete.get("fullName", "?")

                log(
                    f"DEBUG match={match_db_id}: player "
                    f"'{athlete_name}' has empty 'stats' list. "
                    f"Entry keys: {list(entry.keys())}"
                )

            if stat_list:

                stat_record = {
                    "match_id": match_db_id,
                    "player_id": player_db_id,
                    "team_id": team_db_id,
                    "starter": bool(entry.get("starter")),
                    "active": bool(entry.get("active", True)),
                    "jersey_number": entry.get("jersey"),
                    "position": position,
                    "formation_place": entry.get("formationPlace"),
                    "subbed_in": bool(entry.get("subbedIn")),
                    "subbed_out": bool(entry.get("subbedOut")),
                    "raw_stats": stat_list,
                }

                stat_record.update(
                    map_stats(stat_list, PLAYER_STAT_MAP)
                )

                player_stat_records.append(stat_record)

    if lineup_records:
        upsert(
            "match_lineups",
            lineup_records,
            on_conflict="match_id,player_id",
        )

    if player_stat_records:
        upsert(
            "player_match_stats",
            player_stat_records,
            on_conflict="match_id,player_id",
        )

    return len(lineup_records), len(player_stat_records)


# ============================================================
# LEADERS
# ============================================================

def sync_leaders(match_db_id, summary):

    leaders = summary.get("leaders") or []

    if not leaders:
        log(
            f"DEBUG match={match_db_id}: no 'leaders' key/empty."
        )
        return 0

    records = []

    for team_leaders in leaders:

        source_team_id = str(
            (team_leaders.get("team") or {}).get("id") or ""
        )

        team_db_id = get_team_db_id(source_team_id)

        categories = team_leaders.get("leaders", [])

        if not categories:
            log(
                f"DEBUG match={match_db_id} team={source_team_id}: "
                f"'leaders' list present but empty categories. "
                f"team_leaders keys: {list(team_leaders.keys())}"
            )

        for category in categories:

            top = (category.get("leaders") or [None])[0]

            if not top:
                log(
                    f"DEBUG match={match_db_id} team={source_team_id}: "
                    f"category '{category.get('displayName')}' has "
                    f"no leader entries. category keys: "
                    f"{list(category.keys())}"
                )
                continue

            athlete = top.get("athlete") or {}

            player_ids = upsert_players_get_ids([athlete], team_db_id)

            player_db_id = player_ids.get(str(athlete.get("id") or ""))

            records.append({
                "match_id": match_db_id,
                "team_id": team_db_id,
                "player_id": player_db_id,
                "category": category.get("name") or category.get("displayName"),
                "value": top.get("value"),
                "display_value": top.get("displayValue"),
            })

    if records:
        upsert(
            "match_leaders",
            records,
            on_conflict="match_id,team_id,category",
        )

    return len(records)


# ============================================================
# EVENTS (keyEvents) — منطق مبني على تجربة سابقة ناجحة، لكن
# لسه محتاج تأكيد نهائي على نص "type" الحقيقي من ESPN لو ظهرت
# نتائج غريبة في اللوج (راجع أسلوبنا المعتاد في التشخيص).
# ============================================================

def extract_athletes(detail):

    participants = detail.get("participants") or []

    if participants:
        return [
            p.get("athlete", {})
            for p in participants
            if isinstance(p, dict) and p.get("athlete")
        ]

    return detail.get("athletesInvolved") or []


def classify_event_type(detail):

    type_slug = str(detail.get("type", "")).lower()
    text = str(detail.get("text", "")).lower()

    combined = f"{type_slug} {text}"

    # أنواع بنتجاهلها عمدًا (مش أخطاء، مجرد مش مهمة للتخزين)
    ignored_markers = (
        "delay", "review", "offside", "throw-in",
        "free-kick", "corner-kick", "shot-", "save",
    )

    if any(marker in type_slug for marker in ignored_markers):
        return "ignored"

    if "own goal" in combined:
        return "goal"
    if "goal" in combined and "own" not in combined:
        return "goal"
    if "yellow" in combined:
        return "yellow_card"
    if "red" in combined and "card" in combined:
        return "red_card"
    if "substitution" in combined:
        return "substitution"
    if "penalty" in combined:
        return "penalty"
    if "var" in combined or "video review" in combined:
        return "var"
    if "kickoff" in type_slug:
        return "kickoff"
    if "start-2nd-half" in type_slug or "2nd-half" in type_slug:
        return "start_2nd_half"
    if "halftime" in type_slug:
        return "halftime"
    if "full-time" in type_slug or "fulltime" in type_slug:
        return "fulltime"

    return None


def sync_events(match_db_id, summary, home_team_db_id, away_team_db_id):

    key_events = summary.get("keyEvents") or []

    if not key_events:
        log(
            f"DEBUG match={match_db_id}: no 'keyEvents' key/empty. "
            f"Top-level summary keys: {list(summary.keys())}"
        )

    records = []
    skipped_unclassified = 0

    for index, detail in enumerate(key_events):

        event_type = classify_event_type(detail)

        if event_type == "ignored":
            continue

        if not event_type:
            skipped_unclassified += 1

            if skipped_unclassified <= 3:
                log(
                    f"DEBUG match={match_db_id}: unclassified event "
                    f"raw type={detail.get('type')}, "
                    f"keys={list(detail.keys())}"
                )

            continue

        team_source_id = str(
            (detail.get("team") or {}).get("id") or ""
        )

        team_db_id = get_team_db_id(team_source_id)

        athletes = extract_athletes(detail)

        player_ids = upsert_players_get_ids(athletes, team_db_id)

        def pid(athlete):
            return player_ids.get(str(athlete.get("id") or ""))

        player_id = None
        assist_player_id = None
        player_out_id = None
        player_in_id = None

        if event_type == "substitution" and len(athletes) >= 2:
            player_in_id = pid(athletes[0])
            player_out_id = pid(athletes[1])
        else:
            if len(athletes) >= 1:
                player_id = pid(athletes[0])
            if len(athletes) >= 2:
                assist_player_id = pid(athletes[1])

        clock = (detail.get("clock") or {}).get("displayValue", "")

        minute = None
        extra_time = None

        if clock:

            clean = clock.replace("'", "")

            if "+" in clean:
                base, extra = clean.split("+", 1)
                minute = int(base) if base.isdigit() else None
                extra_time = int(extra) if extra.isdigit() else None
            elif clean.isdigit():
                minute = int(clean)

        records.append({
            "match_id": match_db_id,
            "team_id": team_db_id,
            "player_id": player_id,
            "assist_player_id": assist_player_id,
            "player_out_id": player_out_id,
            "player_in_id": player_in_id,
            "event_type": event_type,
            "minute": minute,
            "extra_time": extra_time,
            "details": detail,
            "source": "espn",
            "source_id": (
                f"{match_db_id}-{detail.get('id', index)}"
            ),
        })

    if records:
        upsert("match_events", records, on_conflict="source,source_id")

    if skipped_unclassified:
        log(
            f"DEBUG match={match_db_id}: "
            f"skipped {skipped_unclassified} unclassified event(s) "
            f"out of {len(key_events)} total keyEvents."
        )

    return len(records)


# ============================================================
# MATCH SELECTION
# ============================================================

def get_league_slug_for_competition(competition_id, competition_id_to_slug):
    return competition_id_to_slug.get(competition_id)


def get_matches_needing_detail_sync():

    today = datetime.now(TIMEZONE).date()

    start = (today - timedelta(days=1)).isoformat() + "T00:00:00"
    end = (today + timedelta(days=2)).isoformat() + "T00:00:00"

    rows = select(
        "matches",
        {
            "select": (
                "id,source_id,status,competition_id,"
                "home_team_id,away_team_id"
            ),
            "kickoff_at": [f"gte.{start}", f"lt.{end}"],
        },
    )

    # نتجاهل الماتشات المنتهية اللي اتعملها تفاصيل خلاص، عشان
    # منضربش ESPN من غير داعي لحاجة خلصت وما هتتغيرش.
    finished_ids = [
        str(r["id"]) for r in rows if r["status"] == "FINISHED"
    ]

    already_has_stats = set()

    if finished_ids:

        existing = select(
            "match_stats",
            {
                "select": "match_id",
                "match_id": f"in.({','.join(finished_ids)})",
            },
        )

        already_has_stats = {row["match_id"] for row in existing}

    return [
        r for r in rows
        if not (r["status"] == "FINISHED" and r["id"] in already_has_stats)
    ]


def main():

    import sys

    validate_environment()

    log("==================================================")
    log("SYNC MATCH DETAILS START")
    log("==================================================")

    competitions = select(
        "competitions", {"select": "id,source_id"}
    )

    competition_slug_map = {
        c["id"]: c["source_id"] for c in competitions
    }

    force_match_id = None

    if len(sys.argv) > 1:
        force_match_id = int(sys.argv[1])

    if force_match_id:

        rows = select(
            "matches",
            {
                "select": (
                    "id,source_id,status,competition_id,"
                    "home_team_id,away_team_id"
                ),
                "id": f"eq.{force_match_id}",
            },
        )

        matches = rows

        log(f"FORCED resync for match={force_match_id}")

    else:
        matches = get_matches_needing_detail_sync()

    log(f"Matches needing detail sync: {len(matches)}")

    for match in matches:

        match_db_id = match["id"]
        league_slug = competition_slug_map.get(match["competition_id"])

        if not league_slug:
            log(
                f"WARNING: no league slug for match={match_db_id}, "
                f"skipping."
            )
            continue

        try:

            summary = get_summary(league_slug, match["source_id"])

            events_count = sync_events(
                match_db_id,
                summary,
                match.get("home_team_id"),
                match.get("away_team_id"),
            )

            stats_count = sync_team_stats(match_db_id, summary)

            lineup_count, player_stat_count = sync_rosters(
                match_db_id, summary
            )

            leaders_count = sync_leaders(match_db_id, summary)

            log(
                f"match={match_db_id}: "
                f"events={events_count}, "
                f"team_stats={stats_count}, "
                f"lineups={lineup_count}, "
                f"player_stats={player_stat_count}, "
                f"leaders={leaders_count}"
            )

        except Exception as error:
            log(f"ERROR match={match_db_id}: {error}")
            continue

    log("==================================================")
    log("SYNC MATCH DETAILS END")
    log("==================================================")


if __name__ == "__main__":
    main()
