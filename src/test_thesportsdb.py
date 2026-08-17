import os
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TIMEZONE = ZoneInfo("Africa/Cairo")

REQUEST_TIMEOUT = 30

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"


# ============================================================
# FIVE BIG LEAGUES
# ============================================================

COMPETITIONS = {

    "Premier League": {
        "slug": "eng.1",
        "code": "PL",
        "country": "England",
    },

    "La Liga": {
        "slug": "esp.1",
        "code": "PD",
        "country": "Spain",
    },

    "Serie A": {
        "slug": "ita.1",
        "code": "SA",
        "country": "Italy",
    },

    "Bundesliga": {
        "slug": "ger.1",
        "code": "BL1",
        "country": "Germany",
    },

    "Ligue 1": {
        "slug": "fra.1",
        "code": "FL1",
        "country": "France",
    },

}


# ============================================================
# SUPABASE HEADERS
# ============================================================

SUPABASE_HEADERS = {

    "apikey": SUPABASE_KEY,

    "Authorization": (
        f"Bearer {SUPABASE_KEY}"
    ),

    "Content-Type": "application/json",

    "Prefer": (
        "resolution=merge-duplicates,"
        "return=minimal"
    ),

}


# ============================================================
# DATE HELPERS
# ============================================================

def get_target_dates():

    now = datetime.now(TIMEZONE)

    today = now.date()

    yesterday = (
        today -
        timedelta(days=1)
    )

    return yesterday, today


# ============================================================
# ESPN API
# ============================================================

def get_league_scoreboard(
    league_slug,
    date
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{league_slug}/scoreboard"
    )

    params = {
        "dates": date.strftime("%Y%m%d")
    }

    response = requests.get(

        url,

        params=params,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code != 200:

        raise Exception(

            f"ESPN API error "
            f"{response.status_code}: "
            f"{response.text}"

        )

    return response.json()


# ============================================================
# GET COMPETITION
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
            "id,code,name"

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
    events
):

    teams = {}


    for event in events:

        competition = event.get(
            "competitions",
            []
        )

        if not competition:

            continue


        competitors = competition[0].get(
            "competitors",
            []
        )


        for competitor in competitors:

            team = competitor.get(
                "team",
                {}
            )

            source_team_id = team.get(
                "id"
            )

            if not source_team_id:

                continue


            source_team_id = str(
                source_team_id
            )


            key = (
                "espn",
                source_team_id
            )


            teams[key] = {

                "source":
                    "espn",

                "source_team_id":
                    source_team_id,

                "name":
                    team.get(
                        "displayName"
                    ),

                "short_name":
                    team.get(
                        "shortDisplayName"
                    ),

                "tla":
                    team.get(
                        "abbreviation"
                    ),

                "crest_url":
                    team.get(
                        "logo"
                    ),

            }


    if not teams:

        return {}


    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/teams"
    )


    params = {

        "on_conflict":
            "source,source_team_id"

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
            "eq.espn",

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

            "Failed to retrieve ESPN "
            "team database IDs: "
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

    event,

    competition_id,

    competition_name,

    season,

    team_db_ids

):

    event_id = event.get(
        "id"
    )

    if not event_id:

        raise Exception(
            "ESPN event does not contain id."
        )


    event_date = event.get(
        "date"
    )

    if not event_date:

        raise Exception(
            f"ESPN event {event_id} "
            "does not contain date."
        )


    competitions = event.get(
        "competitions",
        []
    )

    if not competitions:

        raise Exception(

            f"ESPN event {event_id} "
            "does not contain competition."

        )


    competition = competitions[0]


    competitors = competition.get(
        "competitors",
        []
    )


    if len(competitors) != 2:

        raise Exception(

            f"ESPN event {event_id} "
            "does not have exactly "
            "two teams."

        )


    home_team = None
    away_team = None


    for competitor in competitors:

        if competitor.get(
            "homeAway"
        ) == "home":

            home_team = competitor

        elif competitor.get(
            "homeAway"
        ) == "away":

            away_team = competitor


    if not home_team or not away_team:

        raise Exception(

            f"Could not determine home/away "
            f"teams for ESPN event {event_id}."

        )


    home_team_data = home_team.get(
        "team",
        {}
    )

    away_team_data = away_team.get(
        "team",
        {}
    )


    home_source_id = str(
        home_team_data.get("id")
    )

    away_source_id = str(
        away_team_data.get("id")
    )


    home_key = (
        "espn",
        home_source_id
    )

    away_key = (
        "espn",
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
            "ID for home team: "
            f"{home_team_data.get('displayName')} "
            f"({home_source_id})"

        )


    if away_db_id is None:

        raise Exception(

            "Could not find Supabase "
            "ID for away team: "
            f"{away_team_data.get('displayName')} "
            f"({away_source_id})"

        )


    # --------------------------------------------------------
    # Score
    # --------------------------------------------------------

    home_score = home_team.get(
        "score"
    )

    away_score = away_team.get(
        "score"
    )


    if home_score is not None:

        try:
            home_score = int(home_score)
        except (TypeError, ValueError):
            pass


    if away_score is not None:

        try:
            away_score = int(away_score)
        except (TypeError, ValueError):
            pass


    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    status = (
        competition
        .get("status", {})
        .get("type", {})
    )


    status_name = status.get(
        "name"
    )

    status_detail = status.get(
        "detail"
    )

    status_short = status.get(
        "shortDetail"
    )


    # --------------------------------------------------------
    # Season
    # --------------------------------------------------------

    event_season = (
        event
        .get("season", {})
        .get("year")
    )

    if event_season is None:

        event_season = season


    # --------------------------------------------------------
    # Venue
    # --------------------------------------------------------

    venue = (
        competition
        .get("venue", {})
        .get("fullName")
    )


    # --------------------------------------------------------
    # Cairo time
    # --------------------------------------------------------

    utc_datetime = datetime.fromisoformat(
        event_date.replace(
            "Z",
            "+00:00"
        )
    )

    cairo_datetime = (
        utc_datetime.astimezone(
            TIMEZONE
        )
    )


    # --------------------------------------------------------
    # Record
    # --------------------------------------------------------

    return {

        "source":
            "espn",

        "source_match_id":
            str(event_id),

        "competition_id":
            competition_id,

        "competition_name":
            competition_name,

        "season":
            event_season,

        "kickoff_utc":
            event_date,

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
            home_team_data.get(
                "displayName"
            ),

        "away_team_name":
            away_team_data.get(
                "displayName"
            ),

        "status":
            status_short
            or status_detail
            or status_name,

        "home_score":
            home_score,

        "away_score":
            away_score,

        "venue":
            venue,

        "last_updated_at":
            event.get(
                "date"
            ),

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
    # ENVIRONMENT
    # ========================================================

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

    yesterday, today = (
        get_target_dates()
    )


    target_dates = {

        yesterday,

        today

    }


    # ========================================================
    # CURRENT SEASON
    # ========================================================

    now = datetime.now(
        TIMEZONE
    )

    season = (
        now.year
        if now.month >= 7
        else now.year - 1
    )


    # ========================================================
    # HEADER
    # ========================================================

    print("=" * 70)

    print(
        "ESPN FIXTURES PIPELINE"
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
        f"Season    : {season}"
    )

    print(
        "Collection: Yesterday + Today ONLY"
    )

    print("=" * 70)


    # ========================================================
    # COUNTERS
    # ========================================================

    total_matches = 0

    total_teams = 0

    total_yesterday = 0

    total_today = 0


    # ========================================================
    # LEAGUES
    # ========================================================

    for league_name, league_info in (
        COMPETITIONS.items()
    ):

        slug = league_info["slug"]

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

            # ------------------------------------------------
            # Supabase competition
            # ------------------------------------------------

            competition_id = (
                get_competition_id(
                    competition_code
                )
            )


            print(
                "Supabase Competition ID: "
                f"{competition_id}"
            )


            # ------------------------------------------------
            # Get ESPN matches
            # ------------------------------------------------

            all_events = []


            for target_date in sorted(
                target_dates
            ):

                data = (
                    get_league_scoreboard(
                        slug,
                        target_date
                    )
                )


                events = data.get(
                    "events",
                    []
                )


                print(
                    f"{target_date}: "
                    f"{len(events)} matches"
                )


                all_events.extend(
                    events
                )


            # ------------------------------------------------
            # Remove duplicate ESPN events
            # ------------------------------------------------

            unique_events = {}

            for event in all_events:

                event_id = event.get(
                    "id"
                )

                if event_id:

                    unique_events[
                        str(event_id)
                    ] = event


            events = list(
                unique_events.values()
            )


            # ------------------------------------------------
            # Teams
            # ------------------------------------------------

            team_db_ids = (
                upsert_teams(
                    events
                )
            )


            total_teams += len(
                team_db_ids
            )


            print(
                "Teams processed: "
                f"{len(team_db_ids)}"
            )


            # ------------------------------------------------
            # Prepare matches
            # ------------------------------------------------

            records = []


            yesterday_count = 0

            today_count = 0


            for event in events:

                event_date = event.get(
                    "date"
                )

                if not event_date:

                    continue


                utc_datetime = (
                    datetime.fromisoformat(
                        event_date.replace(
                            "Z",
                            "+00:00"
                        )
                    )
                )


                cairo_datetime = (
                    utc_datetime.astimezone(
                        TIMEZONE
                    )
                )


                match_date = (
                    cairo_datetime.date()
                )


                if match_date not in target_dates:

                    continue


                record = prepare_match(

                    event,

                    competition_id,

                    league_name,

                    season,

                    team_db_ids

                )


                records.append(
                    record
                )


                if match_date == yesterday:

                    yesterday_count += 1

                elif match_date == today:

                    today_count += 1


            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            saved = upsert_matches(
                records
            )


            total_matches += saved

            total_yesterday += (
                yesterday_count
            )

            total_today += (
                today_count
            )


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
                f"ERROR in {league_name}:"
            )

            print(
                error
            )

            print(
                "Continuing..."
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
        f"Yesterday matches: "
        f"{total_yesterday}"
    )

    print(
        f"Today matches    : "
        f"{total_today}"
    )

    print(
        f"Teams processed   : "
        f"{total_teams}"
    )

    print(
        f"Matches processed : "
        f"{total_matches}"
    )

    print("")

    print(
        "Source : ESPN"
    )

    print(
        "Database mode: UPSERT"
    )

    print(
        "Date range: YESTERDAY + TODAY"
    )

    print(
        "Events: separate pipeline"
    )

    print(
        "Status: SUCCESS"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
