import os
import json
import hashlib
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

FOOTBALL_DATA_TOKEN = os.getenv("FOOTBALL_DATA_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TIMEZONE = ZoneInfo("Africa/Cairo")

FOOTBALL_BASE_URL = (
    "https://api.football-data.org/v4/competitions"
)

FOOTBALL_MATCH_URL = (
    "https://api.football-data.org/v4/matches"
)

REQUEST_TIMEOUT = 30


# ============================================================
# FIVE BIG LEAGUES
# ============================================================

COMPETITIONS = {

    "Premier League": {
        "code": "PL",
        "country": "England"
    },

    "La Liga": {
        "code": "PD",
        "country": "Spain"
    },

    "Serie A": {
        "code": "SA",
        "country": "Italy"
    },

    "Bundesliga": {
        "code": "BL1",
        "country": "Germany"
    },

    "Ligue 1": {
        "code": "FL1",
        "country": "France"
    },

}


# ============================================================
# API HEADERS
# ============================================================

FOOTBALL_HEADERS = {

    "X-Auth-Token":
        FOOTBALL_DATA_TOKEN,

    # Ask API to expose goal details
    "X-Unfold-Goals":
        "true",

}


SUPABASE_HEADERS = {

    "apikey":
        SUPABASE_KEY,

    "Authorization":
        f"Bearer {SUPABASE_KEY}",

    "Content-Type":
        "application/json",

    "Prefer":
        "resolution=merge-duplicates,return=minimal",

}


# ============================================================
# CURRENT SEASON
# ============================================================

def get_current_season():

    now = datetime.now(
        TIMEZONE
    )

    if now.month >= 7:

        return now.year

    return now.year - 1


# ============================================================
# GET ALL SEASON MATCHES
# ============================================================

def get_competition_matches(
    competition_code,
    season
):

    url = (
        f"{FOOTBALL_BASE_URL}/"
        f"{competition_code}/matches"
    )

    params = {
        "season": season
    }

    response = requests.get(

        url,

        headers=FOOTBALL_HEADERS,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            f"Football API error "
            f"{response.status_code}: "
            f"{response.text[:2000]}"

        )

    data = response.json()

    return data.get(
        "matches",
        []
    )


# ============================================================
# GET ONE MATCH DETAILS
# ============================================================

def get_match_details(
    source_match_id
):

    url = (
        f"{FOOTBALL_MATCH_URL}/"
        f"{source_match_id}"
    )

    response = requests.get(

        url,

        headers=FOOTBALL_HEADERS,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            f"Match details API error "
            f"{response.status_code}: "
            f"{response.text[:2000]}"

        )

    data = response.json()

    if not isinstance(
        data,
        dict
    ):

        raise Exception(
            "Invalid match details response"
        )

    return data


# ============================================================
# UTC → CAIRO
# ============================================================

def convert_to_cairo(
    utc_date
):

    utc_datetime = datetime.fromisoformat(

        utc_date.replace(
            "Z",
            "+00:00"
        )

    )

    return utc_datetime.astimezone(
        TIMEZONE
    )


# ============================================================
# GET SUPABASE COMPETITION ID
# ============================================================

def get_competition_id(
    competition_code
):

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/competitions"
    )

    params = {

        "code":
            f"eq.{competition_code}",

        "select":
            "id"

    }

    response = requests.get(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            "Supabase competition lookup "
            f"failed {response.status_code}: "
            f"{response.text}"

        )

    data = response.json()

    if not data:

        raise Exception(

            f"Competition "
            f"{competition_code} "
            "does not exist in Supabase."

        )

    return data[0]["id"]


# ============================================================
# UPSERT TEAMS
# ============================================================

def upsert_teams(
    matches
):

    teams = {}

    for match in matches:

        home_team = match.get(
            "homeTeam",
            {}
        )

        away_team = match.get(
            "awayTeam",
            {}
        )

        for team in [
            home_team,
            away_team
        ]:

            if not team:
                continue

            if team.get("id") is None:
                continue

            source_team_id = str(
                team["id"]
            )

            key = (
                "football-data.org",
                source_team_id
            )

            teams[key] = {

                "source":
                    "football-data.org",

                "source_team_id":
                    source_team_id,

                "name":
                    team.get("name"),

                "short_name":
                    team.get("shortName"),

                "tla":
                    team.get("tla"),

                "crest_url":
                    team.get("crest")

            }

    if not teams:

        return {}

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/teams"
    )

    params = {

        "on_conflict":
            "source,source_team_id",

        "select":
            "id,source,source_team_id"

    }

    response = requests.post(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        json=list(
            teams.values()
        ),

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code not in [
        200,
        201
    ]:

        raise Exception(

            "Supabase teams upsert "
            f"failed {response.status_code}: "
            f"{response.text}"

        )

    source_ids = [

        team["source_team_id"]

        for team in teams.values()

    ]

    params = {

        "source":
            "eq.football-data.org",

        "source_team_id":
            "in.("
            + ",".join(source_ids)
            + ")",

        "select":
            "id,source,source_team_id"

    }

    response = requests.get(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            "Failed to retrieve team "
            f"database IDs "
            f"{response.status_code}: "
            f"{response.text}"

        )

    saved_teams = response.json()

    team_db_ids = {}

    for team in saved_teams:

        key = (

            team["source"],

            str(
                team["source_team_id"]
            )

        )

        team_db_ids[key] = team["id"]

    return team_db_ids


# ============================================================
# PREPARE MATCH
# ============================================================

def prepare_match(

    match,

    competition_id,

    competition_name,

    season,

    team_db_ids

):

    kickoff_utc = match["utcDate"]

    cairo_datetime = convert_to_cairo(
        kickoff_utc
    )

    score = match.get(
        "score",
        {}
    )

    full_time = score.get(
        "fullTime",
        {}
    )

    home_score = full_time.get(
        "home"
    )

    away_score = full_time.get(
        "away"
    )

    home_team = match["homeTeam"]
    away_team = match["awayTeam"]

    home_source_id = str(
        home_team["id"]
    )

    away_source_id = str(
        away_team["id"]
    )

    home_key = (
        "football-data.org",
        home_source_id
    )

    away_key = (
        "football-data.org",
        away_source_id
    )

    home_db_id = team_db_ids.get(
        home_key
    )

    away_db_id = team_db_ids.get(
        away_key
    )

    if home_db_id is None:

        raise Exception(

            "Could not find Supabase "
            "database ID for home team: "
            f"{home_team['name']} "
            f"({home_source_id})"

        )

    if away_db_id is None:

        raise Exception(

            "Could not find Supabase "
            "database ID for away team: "
            f"{away_team['name']} "
            f"({away_source_id})"

        )

    return {

        "source":
            "football-data.org",

        "source_match_id":
            match["id"],

        "competition_id":
            competition_id,

        "competition_name":
            competition_name,

        "season":
            season,

        "kickoff_utc":
            kickoff_utc,

        "kickoff_local":
            cairo_datetime.isoformat(),

        "timezone":
            "Africa/Cairo",

        "home_team_id":
            home_source_id,

        "away_team_id":
            away_source_id,

        "home_team_db_id":
            home_db_id,

        "away_team_db_id":
            away_db_id,

        "home_team_name":
            home_team["name"],

        "away_team_name":
            away_team["name"],

        "status":
            match["status"],

        "home_score":
            home_score,

        "away_score":
            away_score,

        "venue":
            match.get("venue"),

        "last_updated_at":
            match.get("lastUpdated")

    }


# ============================================================
# UPSERT MATCHES
# ============================================================

def upsert_matches(
    matches
):

    if not matches:

        return 0

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/matches"
    )

    params = {

        "on_conflict":
            "source,source_match_id"

    }

    response = requests.post(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        json=matches,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code not in [
        200,
        201,
        204
    ]:

        raise Exception(

            "Supabase matches upsert "
            f"failed {response.status_code}: "
            f"{response.text}"

        )

    return len(matches)


# ============================================================
# GET INTERNAL MATCH IDS
# ============================================================

def get_match_db_ids(
    source_match_ids
):

    if not source_match_ids:

        return {}

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/matches"
    )

    ids = [
        str(x)
        for x in source_match_ids
    ]

    params = {

        "source":
            "eq.football-data.org",

        "source_match_id":
            "in.("
            + ",".join(ids)
            + ")",

        "select":
            "id,source_match_id"

    }

    response = requests.get(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            "Failed to retrieve match IDs "
            f"{response.status_code}: "
            f"{response.text}"

        )

    data = response.json()

    result = {}

    for row in data:

        result[
            str(
                row["source_match_id"]
            )
        ] = row["id"]

    return result


# ============================================================
# EVENT KEY
# ============================================================

def make_event_key(
    match_id,
    event_type,
    event
):

    parts = [

        str(match_id),

        str(event_type),

        str(
            event.get("minute")
            or ""
        ),

        str(
            event.get("extraTime")
            or ""
        ),

    ]

    team = event.get(
        "team",
        {}
    )

    player = event.get(
        "player",
        {}
    )

    scorer = event.get(
        "scorer",
        {}
    )

    player_out = event.get(
        "playerOut",
        {}
    )

    player_in = event.get(
        "playerIn",
        {}
    )

    parts.extend([

        str(
            team.get("id")
            or ""
        ),

        str(
            player.get("id")
            or scorer.get("id")
            or ""
        ),

        str(
            player_out.get("id")
            or ""
        ),

        str(
            player_in.get("id")
            or ""
        ),

        str(
            event.get("card")
            or ""
        ),

    ])

    raw_key = "|".join(
        parts
    )

    return hashlib.sha256(
        raw_key.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# PREPARE GOAL EVENT
# ============================================================

def prepare_goal_event(
    match_id,
    event
):

    team = event.get(
        "team",
        {}
    )

    scorer = event.get(
        "scorer",
        {}
    )

    assist = event.get(
        "assist",
        {}
    )

    return {

        "match_id":
            match_id,

        "source":
            "football-data.org",

        "source_event_key":
            make_event_key(
                match_id,
                "GOAL",
                event
            ),

        "event_type":
            "GOAL",

        "minute":
            event.get("minute"),

        "extra_time":
            event.get("extraTime"),

        "team_id":
            (
                str(team["id"])
                if team.get("id")
                is not None
                else None
            ),

        "team_name":
            team.get("name"),

        "player_id":
            (
                str(scorer["id"])
                if scorer.get("id")
                is not None
                else None
            ),

        "player_name":
            scorer.get("name"),

        "assist_player_id":
            (
                str(assist["id"])
                if assist.get("id")
                is not None
                else None
            ),

        "assist_player_name":
            assist.get("name"),

        "home_score":
            event.get(
                "homeScore"
            ),

        "away_score":
            event.get(
                "awayScore"
            ),

        "raw_event":
            event,

    }


# ============================================================
# PREPARE BOOKING EVENT
# ============================================================

def prepare_booking_event(
    match_id,
    event
):

    team = event.get(
        "team",
        {}
    )

    player = event.get(
        "player",
        {}
    )

    return {

        "match_id":
            match_id,

        "source":
            "football-data.org",

        "source_event_key":
            make_event_key(
                match_id,
                "CARD",
                event
            ),

        "event_type":
            "CARD",

        "minute":
            event.get("minute"),

        "extra_time":
            event.get("extraTime"),

        "team_id":
            (
                str(team["id"])
                if team.get("id")
                is not None
                else None
            ),

        "team_name":
            team.get("name"),

        "player_id":
            (
                str(player["id"])
                if player.get("id")
                is not None
                else None
            ),

        "player_name":
            player.get("name"),

        "card":
            event.get("card"),

        "raw_event":
            event,

    }


# ============================================================
# PREPARE SUBSTITUTION EVENT
# ============================================================

def prepare_substitution_event(
    match_id,
    event
):

    team = event.get(
        "team",
        {}
    )

    player_out = event.get(
        "playerOut",
        {}
    )

    player_in = event.get(
        "playerIn",
        {}
    )

    return {

        "match_id":
            match_id,

        "source":
            "football-data.org",

        "source_event_key":
            make_event_key(
                match_id,
                "SUBSTITUTION",
                event
            ),

        "event_type":
            "SUBSTITUTION",

        "minute":
            event.get("minute"),

        "extra_time":
            event.get("extraTime"),

        "team_id":
            (
                str(team["id"])
                if team.get("id")
                is not None
                else None
            ),

        "team_name":
            team.get("name"),

        "player_out_id":
            (
                str(player_out["id"])
                if player_out.get("id")
                is not None
                else None
            ),

        "player_out_name":
            player_out.get("name"),

        "player_in_id":
            (
                str(player_in["id"])
                if player_in.get("id")
                is not None
                else None
            ),

        "player_in_name":
            player_in.get("name"),

        "raw_event":
            event,

    }


# ============================================================
# PREPARE PENALTY EVENT
# ============================================================

def prepare_penalty_event(
    match_id,
    event
):

    team = event.get(
        "team",
        {}
    )

    scorer = event.get(
        "scorer",
        {}
    )

    return {

        "match_id":
            match_id,

        "source":
            "football-data.org",

        "source_event_key":
            make_event_key(
                match_id,
                "PENALTY",
                event
            ),

        "event_type":
            "PENALTY",

        "minute":
            event.get("minute"),

        "extra_time":
            event.get("extraTime"),

        "team_id":
            (
                str(team["id"])
                if team.get("id")
                is not None
                else None
            ),

        "team_name":
            team.get("name"),

        "player_id":
            (
                str(scorer["id"])
                if scorer.get("id")
                is not None
                else None
            ),

        "player_name":
            scorer.get("name"),

        "home_score":
            event.get(
                "homeScore"
            ),

        "away_score":
            event.get(
                "awayScore"
            ),

        "raw_event":
            event,

    }


# ============================================================
# BUILD EVENTS FROM MATCH DETAILS
# ============================================================

def build_match_events(
    match_db_id,
    match_details
):

    events = []

    # --------------------------------------------------------
    # Goals
    # --------------------------------------------------------

    goals = match_details.get(
        "goals",
        []
    )

    if isinstance(
        goals,
        list
    ):

        for goal in goals:

            if isinstance(
                goal,
                dict
            ):

                events.append(

                    prepare_goal_event(

                        match_db_id,

                        goal

                    )

                )


    # --------------------------------------------------------
    # Bookings
    # --------------------------------------------------------

    bookings = match_details.get(
        "bookings",
        []
    )

    if isinstance(
        bookings,
        list
    ):

        for booking in bookings:

            if isinstance(
                booking,
                dict
            ):

                events.append(

                    prepare_booking_event(

                        match_db_id,

                        booking

                    )

                )


    # --------------------------------------------------------
    # Substitutions
    # --------------------------------------------------------

    substitutions = match_details.get(
        "substitutions",
        []
    )

    if isinstance(
        substitutions,
        list
    ):

        for substitution in substitutions:

            if isinstance(
                substitution,
                dict
            ):

                events.append(

                    prepare_substitution_event(

                        match_db_id,

                        substitution

                    )

                )


    # --------------------------------------------------------
    # Penalties
    # --------------------------------------------------------

    penalties = match_details.get(
        "penalties",
        []
    )

    if isinstance(
        penalties,
        list
    ):

        for penalty in penalties:

            if isinstance(
                penalty,
                dict
            ):

                events.append(

                    prepare_penalty_event(

                        match_db_id,

                        penalty

                    )

                )


    return events


# ============================================================
# DELETE OLD EVENTS
# ============================================================

def delete_match_events(
    match_db_id
):

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/match_events"
    )

    params = {

        "match_id":
            f"eq.{match_db_id}"

    }

    response = requests.delete(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code not in [
        200,
        204
    ]:

        raise Exception(

            "Failed to delete old events "
            f"{response.status_code}: "
            f"{response.text}"

        )


# ============================================================
# UPSERT MATCH EVENTS
# ============================================================

def upsert_match_events(
    events
):

    if not events:

        return 0

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/match_events"
    )

    params = {

        "on_conflict":
            "source,source_event_key"

    }

    response = requests.post(

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        json=events,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code not in [
        200,
        201,
        204
    ]:

        raise Exception(

            "Supabase match_events upsert "
            f"failed {response.status_code}: "
            f"{response.text}"

        )

    return len(events)


# ============================================================
# SYNC ONE FINISHED MATCH EVENTS
# ============================================================

def sync_match_events(
    source_match_id,
    match_db_id
):

    print(
        f"   🔎 Fetching events "
        f"for match {source_match_id}"
    )

    details = get_match_details(
        source_match_id
    )

    status = details.get(
        "status"
    )

    if status != "FINISHED":

        print(
            f"   ⏭️ Match status: "
            f"{status} - events skipped"
        )

        return 0


    events = build_match_events(

        match_db_id,

        details

    )


    # --------------------------------------------------------
    # Replace events for this finished match.
    #
    # This prevents stale/duplicated events
    # if the provider corrects an event.
    # --------------------------------------------------------

    delete_match_events(
        match_db_id
    )


    saved = upsert_match_events(
        events
    )


    print(
        f"   ⚽ Goals: "
        f"{len(details.get('goals', []))}"
    )

    print(
        f"   🟨/🟥 Cards: "
        f"{len(details.get('bookings', []))}"
    )

    print(
        f"   🔄 Substitutions: "
        f"{len(details.get('substitutions', []))}"
    )

    print(
        f"   🥅 Penalties: "
        f"{len(details.get('penalties', []))}"
    )

    print(
        f"   ✅ Events saved: "
        f"{saved}"
    )

    return saved


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # CHECK ENVIRONMENT
    # ========================================================

    if not FOOTBALL_DATA_TOKEN:

        raise Exception(
            "FOOTBALL_DATA_TOKEN is missing."
        )

    if not SUPABASE_URL:

        raise Exception(
            "SUPABASE_URL is missing."
        )

    if not SUPABASE_KEY:

        raise Exception(
            "SUPABASE_KEY is missing."
        )


    # ========================================================
    # DATES
    # ========================================================

    now = datetime.now(
        TIMEZONE
    )

    today = now.date()

    yesterday = (
        today -
        timedelta(days=1)
    )

    tomorrow = (
        today +
        timedelta(days=1)
    )

    target_dates = {

        yesterday,
        today,
        tomorrow

    }


    # ========================================================
    # SEASON
    # ========================================================

    season = get_current_season()


    # ========================================================
    # HEADER
    # ========================================================

    print("=" * 70)

    print(
        "FOOTBALL DATA PIPELINE"
    )

    print("=" * 70)

    print(
        "Timezone  : Africa/Cairo"
    )

    print(
        f"Yesterday : {yesterday}"
    )

    print(
        f"Today     : {today}"
    )

    print(
        f"Tomorrow  : {tomorrow}"
    )

    print(
        f"Season    : {season}"
    )

    print("=" * 70)


    # ========================================================
    # COUNTERS
    # ========================================================

    total_matches_processed = 0

    total_teams_processed = 0

    total_events_saved = 0

    total_finished_matches = 0


    # ========================================================
    # FIVE LEAGUES
    # ========================================================

    for league_name, league_info in (
        COMPETITIONS.items()
    ):

        competition_code = (
            league_info["code"]
        )

        print("")

        print("=" * 70)

        print(
            f"🏆 {league_name}"
        )

        print("=" * 70)


        try:

            # =================================================
            # COMPETITION ID
            # =================================================

            competition_id = (
                get_competition_id(
                    competition_code
                )
            )

            print(
                "Supabase Competition ID: "
                f"{competition_id}"
            )


            # =================================================
            # SEASON MATCHES
            # =================================================

            matches = (
                get_competition_matches(

                    competition_code,

                    season

                )
            )

            print(
                "Season matches received: "
                f"{len(matches)}"
            )


            # =================================================
            # TEAMS
            # =================================================

            team_db_ids = (
                upsert_teams(
                    matches
                )
            )

            teams_count = len(
                team_db_ids
            )

            total_teams_processed += (
                teams_count
            )

            print(
                "Teams processed: "
                f"{teams_count}"
            )


            # =================================================
            # PREPARE TARGET MATCHES
            # =================================================

            matches_to_update = []

            target_matches = []

            yesterday_count = 0

            today_count = 0

            tomorrow_count = 0


            for match in matches:

                cairo_datetime = (
                    convert_to_cairo(
                        match["utcDate"]
                    )
                )

                match_date = (
                    cairo_datetime.date()
                )


                if match_date not in target_dates:

                    continue


                record = prepare_match(

                    match,

                    competition_id,

                    league_name,

                    season,

                    team_db_ids

                )

                matches_to_update.append(
                    record
                )

                target_matches.append(
                    match
                )


                if match_date == yesterday:

                    yesterday_count += 1

                elif match_date == today:

                    today_count += 1

                elif match_date == tomorrow:

                    tomorrow_count += 1


            # =================================================
            # UPSERT MATCHES
            # =================================================

            saved = upsert_matches(
                matches_to_update
            )

            total_matches_processed += (
                saved
            )


            # =================================================
            # GET INTERNAL MATCH IDS
            # =================================================

            source_match_ids = [

                match["id"]

                for match in target_matches

            ]

            match_db_ids = (
                get_match_db_ids(
                    source_match_ids
                )
            )


            # =================================================
            # SYNC FINISHED MATCH EVENTS
            # =================================================

            league_events = 0

            league_finished = 0


            for match in target_matches:

                source_match_id = (
                    match["id"]
                )

                status = (
                    match.get(
                        "status"
                    )
                )

                if status != "FINISHED":

                    continue


                match_db_id = (
                    match_db_ids.get(
                        str(
                            source_match_id
                        )
                    )
                )

                if match_db_id is None:

                    print(
                        "   ❌ Cannot find "
                        "Supabase match ID for "
                        f"{source_match_id}"
                    )

                    continue


                try:

                    events_saved = (
                        sync_match_events(

                            source_match_id,

                            match_db_id

                        )
                    )

                    league_finished += 1

                    league_events += (
                        events_saved
                    )

                    total_finished_matches += 1

                    total_events_saved += (
                        events_saved
                    )


                except Exception as error:

                    print(
                        "   ❌ Event sync error "
                        f"for match "
                        f"{source_match_id}:"
                    )

                    print(
                        f"      {error}"
                    )


            # =================================================
            # LEAGUE SUMMARY
            # =================================================

            print("")

            print(
                "Yesterday : "
                f"{yesterday_count}"
            )

            print(
                "Today     : "
                f"{today_count}"
            )

            print(
                "Tomorrow  : "
                f"{tomorrow_count}"
            )

            print(
                "Matches upserted: "
                f"{saved}"
            )

            print(
                "Finished matches synced: "
                f"{league_finished}"
            )

            print(
                "Events saved: "
                f"{league_events}"
            )


        except Exception as error:

            print("")

            print(
                f"❌ ERROR in "
                f"{league_name}:"
            )

            print(error)

            print(
                "Continuing with next league..."
            )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")

    print("=" * 70)

    print(
        "FINAL SUMMARY"
    )

    print("=" * 70)

    print(
        "Teams processed          : "
        f"{total_teams_processed}"
    )

    print(
        "Matches processed        : "
        f"{total_matches_processed}"
    )

    print(
        "Finished matches synced  : "
        f"{total_finished_matches}"
    )

    print(
        "Match events saved       : "
        f"{total_events_saved}"
    )

    print("")

    print(
        "Football API requests:"
    )

    print(
        "  Competition matches    : 5"
    )

    print(
        "  Match details           : "
        f"{total_finished_matches}"
    )

    print("")

    print(
        "Database mode            : UPSERT"
    )

    print(
        "Team relationships       : ENABLED"
    )

    print(
        "Match events             : ENABLED"
    )

    print(
        "Status                   : SUCCESS"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
