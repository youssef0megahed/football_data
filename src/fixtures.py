import os
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
    "X-Auth-Token": FOOTBALL_DATA_TOKEN
}


SUPABASE_HEADERS = {

    "apikey": SUPABASE_KEY,

    "Authorization": (
        f"Bearer {SUPABASE_KEY}"
    ),

    "Content-Type": "application/json",

    "Prefer": (
        "resolution=merge-duplicates,"
        "return=minimal"
    )

}


# ============================================================
# CURRENT SEASON
# ============================================================

def get_current_season():

    now = datetime.now(TIMEZONE)

    # European football season normally
    # starts around July.

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
            f"{response.text}"

        )

    data = response.json()

    return data.get(
        "matches",
        []
    )


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

    """
    Save all teams found in the season matches.

    Returns:

    {
        ("football-data.org", "5335"): 25,
        ("football-data.org", "94"): 26
    }

    The value is the internal Supabase teams.id.
    """

    teams = {}


    # --------------------------------------------------------
    # Extract unique teams
    # --------------------------------------------------------

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


            source_team_id = team.get(
                "id"
            )

            if source_team_id is None:

                continue


            source_team_id = str(
                source_team_id
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


    # --------------------------------------------------------
    # UPSERT teams
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Get internal Supabase IDs
    # --------------------------------------------------------

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

    kickoff_utc = match.get(
        "utcDate"
    )

    if not kickoff_utc:

        raise Exception(
            "Match does not contain utcDate."
        )


    cairo_datetime = convert_to_cairo(
        kickoff_utc
    )


    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # Teams
    # --------------------------------------------------------

    home_team = match.get(
        "homeTeam",
        {}
    )

    away_team = match.get(
        "awayTeam",
        {}
    )


    home_source_id = str(
        home_team.get("id")
    )


    away_source_id = str(
        away_team.get("id")
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


    # --------------------------------------------------------
    # Safety checks
    # --------------------------------------------------------

    if home_db_id is None:

        raise Exception(

            "Could not find Supabase "
            "database ID for home team: "
            f"{home_team.get('name')} "
            f"({home_source_id})"

        )


    if away_db_id is None:

        raise Exception(

            "Could not find Supabase "
            "database ID for away team: "
            f"{away_team.get('name')} "
            f"({away_source_id})"

        )


    # --------------------------------------------------------
    # Match record
    # --------------------------------------------------------

    return {

        "source":
            "football-data.org",

        "source_match_id":
            match.get("id"),

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


        # ----------------------------------------------------
        # Source team IDs
        # ----------------------------------------------------

        "home_team_id":
            home_source_id,

        "away_team_id":
            away_source_id,


        # ----------------------------------------------------
        # Supabase internal team IDs
        # ----------------------------------------------------

        "home_team_db_id":
            home_db_id,

        "away_team_db_id":
            away_db_id,


        # ----------------------------------------------------
        # Team names
        # ----------------------------------------------------

        "home_team_name":
            home_team.get("name"),

        "away_team_name":
            away_team.get("name"),


        # ----------------------------------------------------
        # Match status
        # ----------------------------------------------------

        "status":
            match.get("status"),


        # ----------------------------------------------------
        # Score
        # ----------------------------------------------------

        "home_score":
            home_score,

        "away_score":
            away_score,


        # ----------------------------------------------------
        # Other information
        # ----------------------------------------------------

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
        201
    ]:

        raise Exception(

            "Supabase matches upsert "
            f"failed {response.status_code}: "
            f"{response.text}"

        )


    return len(matches)


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


    # --------------------------------------------------------
    # IMPORTANT
    #
    # We intentionally collect ONLY:
    #
    # 1. Yesterday
    # 2. Today
    #
    # Tomorrow is NOT collected.
    # --------------------------------------------------------

    target_dates = {

        yesterday,

        today

    }


    # ========================================================
    # CURRENT SEASON
    # ========================================================

    season = get_current_season()


    # ========================================================
    # HEADER
    # ========================================================

    print(
        "=" * 70
    )

    print(
        "FOOTBALL DATA PIPELINE"
    )

    print(
        "=" * 70
    )

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
        f"Season    : {season}"
    )

    print(
        "Collection: Yesterday + Today ONLY"
    )

    print(
        "=" * 70
    )


    # ========================================================
    # GLOBAL COUNTERS
    # ========================================================

    total_matches_processed = 0

    total_teams_processed = 0


    total_yesterday = 0

    total_today = 0


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

        print(
            "=" * 70
        )

        print(
            f"🏆 {league_name}"
        )

        print(
            "=" * 70
        )


        try:

            # =================================================
            # GET COMPETITION ID
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
            # GET SEASON MATCHES
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
            # SAVE TEAMS
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
            # PREPARE MATCHES
            # =================================================

            matches_to_update = []


            yesterday_count = 0

            today_count = 0


            for match in matches:

                kickoff = match.get(
                    "utcDate"
                )


                if not kickoff:

                    continue


                cairo_datetime = (
                    convert_to_cairo(
                        kickoff
                    )
                )


                match_date = (
                    cairo_datetime.date()
                )


                # ------------------------------------------------
                # ONLY YESTERDAY + TODAY
                # ------------------------------------------------

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


                # ------------------------------------------------
                # Counters
                # ------------------------------------------------

                if match_date == yesterday:

                    yesterday_count += 1


                elif match_date == today:

                    today_count += 1


            # =================================================
            # UPSERT MATCHES
            # =================================================

            saved = upsert_matches(
                matches_to_update
            )


            total_matches_processed += (
                saved
            )


            total_yesterday += (
                yesterday_count
            )


            total_today += (
                today_count
            )


            # =================================================
            # LEAGUE SUMMARY
            # =================================================

            print(
                "Yesterday : "
                f"{yesterday_count}"
            )

            print(
                "Today     : "
                f"{today_count}"
            )

            print(
                "Matches upserted: "
                f"{saved}"
            )


        except Exception as error:

            print("")

            print(
                f"❌ ERROR in "
                f"{league_name}:"
            )

            print(
                error
            )

            print(
                "Continuing with next league..."
            )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")

    print(
        "=" * 70
    )

    print(
        "FINAL SUMMARY"
    )

    print(
        "=" * 70
    )


    print(
        "Yesterday matches: "
        f"{total_yesterday}"
    )


    print(
        "Today matches    : "
        f"{total_today}"
    )


    print(
        "Teams processed   : "
        f"{total_teams_processed}"
    )


    print(
        "Matches processed : "
        f"{total_matches_processed}"
    )


    print("")

    print(
        "Football API requests: 5"
    )

    print(
        "Database mode: UPSERT"
    )

    print(
        "Team relationships: ENABLED"
    )

    print(
        "Date range: YESTERDAY + TODAY"
    )

    print(
        "Events: handled by separate events pipeline"
    )

    print(
        "Status: SUCCESS"
    )


    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
