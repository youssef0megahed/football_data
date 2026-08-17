import os
import time
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
BATCH_SIZE = 500

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}


def request(method, table, params=None, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{table}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.request(
                method,
                url,
                headers=HEADERS,
                params=params,
                json=body,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code in {200, 201, 204}:
                return response.json() if response.content else []

            if response.status_code in {408, 409, 429, 500, 502, 503, 504}:
                raise RuntimeError(
                    f"HTTP {response.status_code}: {response.text[:300]}"
                )

            raise RuntimeError(
                f"HTTP {response.status_code}: {response.text[:500]}"
            )

        except Exception:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(2 ** (attempt - 1))

    return []


def chunks(items, size=BATCH_SIZE):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def get_all(table, select):
    rows = []
    offset = 0

    while True:
        batch = request(
            "GET",
            table,
            params={
                "select": select,
                "order": "id.asc",
                "limit": str(BATCH_SIZE),
                "offset": str(offset),
            },
        )

        rows.extend(batch)

        if len(batch) < BATCH_SIZE:
            break

        offset += BATCH_SIZE

    return rows


def athlete_from_participant(participant):
    if not isinstance(participant, dict):
        return {}

    athlete = participant.get("athlete")

    if isinstance(athlete, dict):
        return athlete

    return participant if participant.get("id") else {}


def athlete_name(athlete):
    if not isinstance(athlete, dict):
        return ""

    return (
        athlete.get("displayName")
        or athlete.get("fullName")
        or athlete.get("shortName")
        or athlete.get("name")
        or ""
    )


def sync_players(events, team_map):
    records = {}

    for event in events:
        raw = event.get("raw_event") or {}
        participants = raw.get("participants") or []

        team_source_id = (
            str(event["team_id"])
            if event.get("team_id")
            else None
        )

        team_db_id = team_map.get(team_source_id)

        for participant in participants:
            athlete = athlete_from_participant(participant)
            player_id = athlete.get("id")
            name = athlete_name(athlete)

            if player_id is None or not name:
                continue

            source_player_id = str(player_id)

            records[source_player_id] = {
                "source": "espn",
                "source_player_id": source_player_id,
                "name": name,
                "team_id": team_db_id,
            }

    saved = list(records.values())

    for batch in chunks(saved):
        request(
            "POST",
            "players",
            params={
                "on_conflict": "source,source_player_id",
            },
            body=batch,
        )

    return len(saved)


def load_players():
    rows = get_all(
        "players",
        "id,source,source_player_id,name,name_ar,team_id",
    )

    return {
        str(row["source_player_id"]): row
        for row in rows
        if row.get("source") == "espn"
    }


def resolve_player(athlete, player_map):
    if not athlete.get("id"):
        return None, ""

    player_id = str(athlete["id"])
    row = player_map.get(player_id)

    if row:
        return (
            player_id,
            row.get("name_ar")
            or row.get("name")
            or athlete_name(athlete),
        )

    return player_id, athlete_name(athlete)


def update_events(events, player_map, team_ar_map):
    updates = []

    for event in events:
        raw = event.get("raw_event") or {}
        participants = raw.get("participants") or []

        athletes = [
            athlete_from_participant(item)
            for item in participants
        ]
        athletes = [
            item for item in athletes
            if item.get("id")
        ]

        team_source_id = (
            str(event["team_id"])
            if event.get("team_id")
            else None
        )

        team_name = (
            team_ar_map.get(team_source_id)
            or event.get("team_name")
            or ""
        )

        player_id = player_name = None
        assist_id = assist_name = None
        player_in_id = player_in_name = None
        player_out_id = player_out_name = None

        if event.get("event_type") == "substitution":
            # ESPN participants: الداخل أولًا، الخارج ثانيًا.
            if len(athletes) >= 1:
                player_in_id, player_in_name = resolve_player(
                    athletes[0], player_map
                )

            if len(athletes) >= 2:
                player_out_id, player_out_name = resolve_player(
                    athletes[1], player_map
                )

        else:
            if len(athletes) >= 1:
                player_id, player_name = resolve_player(
                    athletes[0], player_map
                )

            if len(athletes) >= 2:
                assist_id, assist_name = resolve_player(
                    athletes[1], player_map
                )

        updates.append({
            "id": event["id"],
            "match_id": event["match_id"],
            "source": event["source"],
            "source_event_key": event["source_event_key"],
            "event_type": event["event_type"],
            "minute": event.get("minute"),
            "extra_time": event.get("extra_time"),
            "team_id": event.get("team_id"),
            "team_name": team_name,
            "player_id": player_id,
            "player_name": player_name or "",
            "assist_player_id": assist_id,
            "assist_player_name": assist_name or "",
            "player_out_id": player_out_id,
            "player_out_name": player_out_name or "",
            "player_in_id": player_in_id,
            "player_in_name": player_in_name or "",
            "card": event.get("card"),
            "home_score": event.get("home_score"),
            "away_score": event.get("away_score"),
            "raw_event": raw,
        })

    for batch in chunks(updates):
        request(
            "POST",
            "match_events",
            params={
                "on_conflict": "source,source_event_key",
            },
            body=batch,
        )

    return len(updates)


def update_matches(matches, team_ar_map):
    updates = []

    for match in matches:
        home_source_id = (
            str(match["home_team_id"])
            if match.get("home_team_id")
            else None
        )

        away_source_id = (
            str(match["away_team_id"])
            if match.get("away_team_id")
            else None
        )

        updates.append({
            "id": match["id"],
            "source": match["source"],
            "source_match_id": match["source_match_id"],
            "competition_id": match.get("competition_id"),
            "competition_name": match.get("competition_name"),
            "season": match.get("season"),
            "kickoff_utc": match.get("kickoff_utc"),
            "kickoff_local": match.get("kickoff_local"),
            "timezone": match.get("timezone"),
            "home_team_id": match.get("home_team_id"),
            "home_team_name": (
                team_ar_map.get(home_source_id)
                or match.get("home_team_name")
                or ""
            ),
            "away_team_id": match.get("away_team_id"),
            "away_team_name": (
                team_ar_map.get(away_source_id)
                or match.get("away_team_name")
                or ""
            ),
            "status": match.get("status"),
            "home_score": match.get("home_score"),
            "away_score": match.get("away_score"),
            "venue": match.get("venue"),
            "home_team_db_id": match.get("home_team_db_id"),
            "away_team_db_id": match.get("away_team_db_id"),
        })

    for batch in chunks(updates):
        request(
            "POST",
            "matches",
            params={
                "on_conflict": "source,source_match_id",
            },
            body=batch,
        )

    return len(updates)


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are required"
        )

    teams = get_all(
        "teams",
        "id,source,source_team_id,name,name_ar",
    )

    team_map = {
        str(row["source_team_id"]): row["id"]
        for row in teams
        if row.get("source") == "espn"
    }

    team_ar_map = {
        str(row["source_team_id"]): (
            row.get("name_ar") or row.get("name")
        )
        for row in teams
        if row.get("source") == "espn"
    }

    events = get_all(
        "match_events",
        (
            "id,match_id,source,source_event_key,event_type,"
            "minute,extra_time,team_id,team_name,player_id,player_name,"
            "assist_player_id,assist_player_name,player_out_id,"
            "player_out_name,player_in_id,player_in_name,card,"
            "home_score,away_score,raw_event"
        ),
    )

    events = [
        event
        for event in events
        if event.get("source") == "espn"
    ]

    players_synced = sync_players(
        events,
        team_map,
    )

    player_map = load_players()

    events_updated = update_events(
        events,
        player_map,
        team_ar_map,
    )

    matches = get_all(
        "matches",
        (
            "id,source,source_match_id,competition_id,competition_name,"
            "season,kickoff_utc,kickoff_local,timezone,home_team_id,"
            "home_team_name,away_team_id,away_team_name,status,home_score,"
            "away_score,venue,home_team_db_id,away_team_db_id"
        ),
    )

    matches = [
        match
        for match in matches
        if match.get("source") == "espn"
    ]

    matches_updated = update_matches(
        matches,
        team_ar_map,
    )

    print(
        "تم تحديث الأسماء: "
        f"لاعبين={players_synced}, "
        f"أحداث={events_updated}, "
        f"مباريات={matches_updated}",
        flush=True,
    )


if __name__ == "__main__":
    main()
