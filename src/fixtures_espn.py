import os
import json
import hashlib
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

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer"
)


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

    "Authorization":
        f"Bearer {SUPABASE_KEY}",

    "Content-Type":
        "application/json",

    "Prefer":
        "resolution=merge-duplicates,"
        "return=minimal",

}


# ============================================================
# TARGET DATES
# ============================================================

def get_target_dates():

    now = datetime.now(
        TIMEZONE
    )

    today = now.date()

    yesterday = (
        today -
        timedelta(days=1)
    )

    return yesterday, today


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
# DATETIME
# ============================================================

def parse_datetime(value):

    return datetime.fromisoformat(

        value.replace(
            "Z",
            "+00:00"
        )

    )


# ============================================================
# ESPN REQUEST
# ============================================================

def espn_get(
    url,
    params=None
):

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
# ESPN SCOREBOARD
# ============================================================

def get_league_scoreboard(
    slug,
    date
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{slug}/scoreboard"
    )

    params = {

        "dates":
            date.strftime("%Y%m%d")

    }

    return espn_get(
        url,
        params
    )


# ============================================================
# ESPN MATCH SUMMARY
# ============================================================

def get_match_summary(
    event_id,
    league_slug
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{league_slug}/summary"
    )

    params = {

        "event":
            str(event_id)

    }

    return espn_get(
        url,
        params
    )


# ============================================================
# SUPABASE REQUEST
# ============================================================

def supabase_request(

    method,

    table,

    params=None,

    json_body=None

):

    if not SUPABASE_URL:

        raise Exception(
            "SUPABASE_URL is missing."
        )

    if not SUPABASE_KEY:

        raise Exception(
            "SUPABASE_KEY is missing."
        )

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/{table}"
    )

    response = requests.request(

        method,

        url,

        headers=SUPABASE_HEADERS,

        params=params,

        json=json_body,

        timeout=REQUEST_TIMEOUT

    )

    if response.status_code not in [
        200,
        201,
        204
    ]:

        raise Exception(

            f"Supabase {table} "
            f"request failed "
            f"{response.status_code}: "
            f"{response.text}"

        )

    if not response.content:

        return []

    return response.json()


# ============================================================
# GET SUPABASE COMPETITION ID
# ============================================================

def get_competition_id(
    competition_code
):

    data = supabase_request(

        "GET",

        "competitions",

        {

            "code":
                f"eq.{competition_code}",

            "source":
                "eq.espn",

            "select":
                "id,code,name"

        }

    )

    if not data:

        raise Exception(

            f"Competition "
            f"{competition_code} "
            "does not exist in Supabase "
            "with source=espn."

        )

    return data[0]["id"]


# ============================================================
# UPSERT TEAMS
# ============================================================

def upsert_teams(
    events
):

    teams = {}


    # --------------------------------------------------------
    # Extract unique teams
    # --------------------------------------------------------

    for event in events:

        competitions = (
            event.get(
                "competitions",
                []
            )
        )

        if not competitions:
            continue


        competitors = (
            competitions[0].get(
                "competitors",
                []
            )
        )


        for competitor in competitors:

            team = competitor.get(
                "team",
                {}
            )

            source_team_id = (
                team.get("id")
            )

            if source_team_id is None:
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
                    (
                        team.get(
                            "displayName"
                        )
                        or
                        team.get(
                            "name"
                        )
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


    # --------------------------------------------------------
    # UPSERT
    # --------------------------------------------------------

    supabase_request(

        "POST",

        "teams",

        {

            "on_conflict":
                "source,source_team_id"

        },

        list(
            teams.values()
        )

    )


    # --------------------------------------------------------
    # GET INTERNAL DATABASE IDS
    # --------------------------------------------------------

    source_ids = [

        item["source_team_id"]

        for item in teams.values()

    ]


    data = supabase_request(

        "GET",

        "teams",

        {

            "source":
                "eq.espn",

            "source_team_id":
                "in.("
                +
                ",".join(source_ids)
                +
                ")",

            "select":
                "id,source,source_team_id"

        }

    )


    result = {}


    for row in data:

        result[

            (
                row["source"],
                str(
                    row["source_team_id"]
                )
            )

        ] = row["id"]


    return result


# ============================================================
# PREPARE MATCH
# ============================================================

def prepare_match(

    event,

    competition_id,

    competition_name,

    fallback_season,

    team_db_ids

):

    event_id = event.get(
        "id"
    )

    event_date = event.get(
        "date"
    )


    competitions = (
        event.get(
            "competitions",
            []
        )
    )


    if (
        not event_id
        or
        not event_date
        or
        not competitions
    ):

        raise Exception(

            f"Invalid ESPN match payload: "
            f"{event_id}"

        )


    competition = (
        competitions[0]
    )


    competitors = (
        competition.get(
            "competitors",
            []
        )
    )


    home = next(

        (

            item

            for item in competitors

            if item.get(
                "homeAway"
            ) == "home"

        ),

        None

    )


    away = next(

        (

            item

            for item in competitors

            if item.get(
                "homeAway"
            ) == "away"

        ),

        None

    )


    if not home or not away:

        raise Exception(

            f"Could not determine "
            f"home/away teams for "
            f"ESPN event {event_id}."

        )


    home_team = (
        home.get(
            "team",
            {}
        )
    )

    away_team = (
        away.get(
            "team",
            {}
        )
    )


    home_source_id = str(
        home_team.get("id")
    )

    away_source_id = str(
        away_team.get("id")
    )


    home_db_id = team_db_ids.get(

        (
            "espn",
            home_source_id
        )

    )


    away_db_id = team_db_ids.get(

        (
            "espn",
            away_source_id
        )

    )


    if home_db_id is None:

        raise Exception(

            f"Missing Supabase database ID "
            f"for home team "
            f"{home_team.get('displayName')} "
            f"({home_source_id})"

        )


    if away_db_id is None:

        raise Exception(

            f"Missing Supabase database ID "
            f"for away team "
            f"{away_team.get('displayName')} "
            f"({away_source_id})"

        )


    status_type = (

        competition
        .get(
            "status",
            {}
        )
        .get(
            "type",
            {}
        )

    )


    local_datetime = (

        parse_datetime(
            event_date
        )

        .astimezone(
            TIMEZONE
        )

    )


    season = (

        event
        .get(
            "season",
            {}
        )
        .get(
            "year"
        )

        or

        fallback_season

    )


    # --------------------------------------------------------
    # SCORE
    # --------------------------------------------------------

    home_score = home.get(
        "score"
    )

    away_score = away.get(
        "score"
    )


    try:

        home_score = (

            int(home_score)

            if home_score is not None

            else None

        )

    except (
        TypeError,
        ValueError
    ):

        home_score = None


    try:

        away_score = (

            int(away_score)

            if away_score is not None

            else None

        )

    except (
        TypeError,
        ValueError
    ):

        away_score = None


    # --------------------------------------------------------
    # VENUE
    # --------------------------------------------------------

    venue = (

        competition
        .get(
            "venue",
            {}
        )
        .get(
            "fullName"
        )

    )


    # --------------------------------------------------------
    # LAST UPDATED
    # --------------------------------------------------------

    last_updated_at = (

        event.get(
            "lastUpdated"
        )

        or

        event.get(
            "date"
        )

    )


    return {

        "source":
            "espn",

        "source_match_id":
            int(event_id),

        "competition_id":
            competition_id,

        "competition_name":
            competition_name,

        "season":
            season,

        "kickoff_utc":
            event_date,

        "kickoff_local":
            local_datetime.isoformat(),

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
            (
                home_team.get(
                    "displayName"
                )
                or
                home_team.get(
                    "name"
                )
            ),

        "away_team_name":
            (
                away_team.get(
                    "displayName"
                )
                or
                away_team.get(
                    "name"
                )
            ),

        "status":
            (
                status_type.get(
                    "shortDetail"
                )
                or
                status_type.get(
                    "detail"
                )
                or
                status_type.get(
                    "name"
                )
                or
                "UNKNOWN"
            ),

        "home_score":
            home_score,

        "away_score":
            away_score,

        "venue":
            venue,

        "last_updated_at":
            last_updated_at,

    }


# ============================================================
# UPSERT MATCHES
# ============================================================

def upsert_matches(
    records
):

    if not records:
        return 0


    supabase_request(

        "POST",

        "matches",

        {

            "on_conflict":
                "source,source_match_id"

        },

        records

    )


    return len(records)


# ============================================================
# GET INTERNAL MATCH IDS
# ============================================================

def get_match_db_ids(
    source_match_ids
):

    if not source_match_ids:
        return {}


    ids = [

        str(item)

        for item in source_match_ids

    ]


    data = supabase_request(

        "GET",

        "matches",

        {

            "source":
                "eq.espn",

            "source_match_id":
                "in.("
                +
                ",".join(ids)
                +
                ")",

            "select":
                "id,source_match_id"

        }

    )


    return {

        str(
            row["source_match_id"]
        ):
        row["id"]

        for row in data

    }


# ============================================================
# EVENT TYPE
# ============================================================

def get_event_type(
    detail
):

    event_type = (
        detail
        .get(
            "type",
            {}
        )
        .get(
            "text",
            ""
        )
        or
        ""
    )


    text = event_type.lower()


    # --------------------------------------------------------
    # SUBSTITUTION
    # --------------------------------------------------------

    if "substitution" in text:
        return "substitution"


    # --------------------------------------------------------
    # CARDS
    # --------------------------------------------------------

    if "yellow card" in text:
        return "yellow_card"


    if "red card" in text:
        return "red_card"


    # --------------------------------------------------------
    # GOALS
    # --------------------------------------------------------

    if (
        "goal" in text
        or
        detail.get(
            "scoringPlay"
        )
    ):

        return "goal"


    # --------------------------------------------------------
    # PENALTY
    # --------------------------------------------------------

    if "penalty" in text:
        return "penalty"


    # --------------------------------------------------------
    # VAR
    # --------------------------------------------------------

    if (
        "var" in text
        or
        "review" in text
    ):

        return "var"


    # --------------------------------------------------------
    # FALLBACK
    # --------------------------------------------------------

    normalized = (

        text
        .replace(
            " ",
            "_"
        )

    )


    return normalized or "other"


# ============================================================
# EVENT UNIQUE KEY
# ============================================================

def make_event_key(

    match_source_id,

    detail,

    index

):

    source_event_id = (
        detail.get(
            "id"
        )
    )


    if source_event_id:

        return (

            f"{match_source_id}:"
            f"{source_event_id}"

        )


    raw = json.dumps(

        detail,

        sort_keys=True,

        ensure_ascii=False,

        separators=(
            ",",
            ":"
        )

    )


    digest = hashlib.sha256(

        raw.encode(
            "utf-8"
        )

    ).hexdigest()[:24]


    return (

        f"{match_source_id}:"
        f"{index}:"
        f"{digest}"

    )


# ============================================================
# PREPARE MATCH EVENTS
# ============================================================

def prepare_match_events(

    event,

    match_db_id,

    league_slug

):

    try:

        summary = get_match_summary(

            event["id"],

            league_slug

        )

    except Exception as error:

        print(

            f"WARNING: Could not fetch "
            f"summary for "
            f"{event.get('name')} "
            f"(ESPN {event.get('id')}): "
            f"{error}"

        )

        return []


    # --------------------------------------------------------
    # ESPN KEY EVENTS
    # --------------------------------------------------------

    details = (

        summary.get(
            "keyEvents"
        )

        or

        summary.get(
            "details"
        )

        or

        []

    )


    records = []


    for index, detail in enumerate(
        details
    ):

        event_type = (
            get_event_type(
                detail
            )
        )


        # ----------------------------------------------------
        # CLOCK
        # ----------------------------------------------------

        clock = (

            detail.get(
                "clock",
                {}
            )

            or

            {}

        )


        display_clock = (
            clock.get(
                "displayValue",
                ""
            )
        )


        clock_value = clock.get(
            "value"
        )


        minute = None


        if isinstance(

            clock_value,

            (
                int,
                float
            )

        ):

            minute = int(
                clock_value // 60
            )


        # ----------------------------------------------------
        # EXTRA TIME
        # ----------------------------------------------------

        extra_time = None


        if (

            display_clock

            and

            "+"

            in

            display_clock

        ):

            try:

                extra_part = (
                    display_clock
                    .split(
                        "+"
                    )[1]
                    .replace(
                        "'",
                        ""
                    )
                )


                extra_time = int(
                    extra_part
                )

            except (
                ValueError,
                IndexError
            ):

                extra_time = None


        # ----------------------------------------------------
        # TEAM
        # ----------------------------------------------------

        team = (

            detail.get(
                "team",
                {}
            )

            or

            {}

        )


        team_source_id = (
            team.get(
                "id"
            )
        )


        # ----------------------------------------------------
        # PLAYERS
        # ----------------------------------------------------

        athletes = (

            detail.get(
                "athletesInvolved"
            )

            or

            []

        )


        player = (

            athletes[0]

            if len(
                athletes
            ) >= 1

            else

            {}

        )


        assist = (

            athletes[1]

            if len(
                athletes
            ) >= 2

            else

            {}

        )


        # ----------------------------------------------------
        # EVENT KEY
        # ----------------------------------------------------

        event_key = make_event_key(

            event["id"],

            detail,

            index

        )


        # ----------------------------------------------------
        # RECORD
        # ----------------------------------------------------

        record = {

            "match_id":
                match_db_id,

            "source":
                "espn",

            "source_event_key":
                event_key,

            "event_type":
                event_type,

            "minute":
                minute,

            "extra_time":
                extra_time,

            "team_id":
                (
                    str(
                        team_source_id
                    )

                    if team_source_id
                    is not None

                    else None
                ),

            "team_name":
                (
                    team.get(
                        "displayName"
                    )
                    or
                    team.get(
                        "name"
                    )
                ),

            "player_id":
                (
                    str(
                        player.get(
                            "id"
                        )
                    )

                    if player.get(
                        "id"
                    ) is not None

                    else None
                ),

            "player_name":
                player.get(
                    "displayName"
                ),

            "assist_player_id":
                (
                    str(
                        assist.get(
                            "id"
                        )
                    )

                    if assist.get(
                        "id"
                    ) is not None

                    else None
                ),

            "assist_player_name":
                assist.get(
                    "displayName"
                ),

            "player_out_id":
                None,

            "player_out_name":
                None,

            "player_in_id":
                None,

            "player_in_name":
                None,

            "card":
                (
                    detail
                    .get(
                        "type",
                        {}
                    )
                    .get(
                        "text"
                    )

                    if event_type in [
                        "yellow_card",
                        "red_card"
                    ]

                    else None
                ),

            "home_score":
                detail.get(
                    "homeScore"
                ),

            "away_score":
                detail.get(
                    "awayScore"
                ),

            "raw_event":
                detail,

        }


        # ----------------------------------------------------
        # SUBSTITUTION
        # ----------------------------------------------------

        if event_type == "substitution":

            if len(
                athletes
            ) >= 2:

                record[
                    "player_out_id"
                ] = (

                    str(
                        athletes[0].get(
                            "id"
                        )
                    )

                    if athletes[0].get(
                        "id"
                    ) is not None

                    else None

                )


                record[
                    "player_out_name"
                ] = (

                    athletes[0].get(
                        "displayName"
                    )

                )


                record[
                    "player_in_id"
                ] = (

                    str(
                        athletes[1].get(
                            "id"
                        )
                    )

                    if athletes[1].get(
                        "id"
                    ) is not None

                    else None

                )


                record[
                    "player_in_name"
                ] = (

                    athletes[1].get(
                        "displayName"
                    )

                )


        records.append(
            record
        )


    return records


# ============================================================
# UPSERT MATCH EVENTS
# ============================================================

def upsert_match_events(
    records
):

    if not records:
        return 0


    supabase_request(

        "POST",

        "match_events",

        {

            "on_conflict":
                "source,source_event_key"

        },

        records

    )


    return len(records)


# ============================================================
# PROCESS ONE MATCH
# ============================================================

def process_match_events(

    event,

    match_db_id,

    league_slug

):

    records = prepare_match_events(

        event,

        match_db_id,

        league_slug

    )


    saved = upsert_match_events(
        records
    )


    print(

        f"{event.get('name')} "
        f": {saved} events"

    )


    return saved


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
    # SEASON
    # ========================================================

    season = get_current_season()


    # ========================================================
    # HEADER
    # ========================================================

    print(
        "=" * 70
    )

    print(
        "ESPN FIXTURES + MATCH EVENTS"
    )

    print(
        "=" * 70
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
        "Source    : ESPN"
    )

    print(
        "Collection: Yesterday + Today ONLY"
    )

    print(
        "=" * 70
    )


    # ========================================================
    # COUNTERS
    # ========================================================

    total_teams = 0

    total_matches = 0

    total_events = 0


    # ========================================================
    # FIVE LEAGUES
    # ========================================================

    for league_name, league in (
        COMPETITIONS.items()
    ):

        print("")

        print(
            "=" * 70
        )

        print(
            league_name
        )

        print(
            "=" * 70
        )


        try:

            # =================================================
            # COMPETITION
            # =================================================

            competition_id = (
                get_competition_id(
                    league["code"]
                )
            )


            # =================================================
            # GET SCOREBOARDS
            # =================================================

            all_events = []


            for target_date in sorted(
                target_dates
            ):

                data = (
                    get_league_scoreboard(

                        league["slug"],

                        target_date

                    )
                )


                day_events = (
                    data.get(
                        "events",
                        []
                    )
                )


                print(

                    f"{target_date}: "
                    f"{len(day_events)} matches"

                )


                all_events.extend(
                    day_events
                )


            # =================================================
            # REMOVE DUPLICATE MATCHES
            # =================================================

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


            # =================================================
            # TEAMS
            # =================================================

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


            # =================================================
            # PREPARE MATCHES
            # =================================================

            match_records = []

            selected_events = []


            for event in events:

                event_date = event.get(
                    "date"
                )


                if not event_date:
                    continue


                match_date = (

                    parse_datetime(
                        event_date
                    )

                    .astimezone(
                        TIMEZONE
                    )

                    .date()

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


                match_records.append(
                    record
                )


                selected_events.append(
                    event
                )


            # =================================================
            # UPSERT MATCHES
            # =================================================

            saved_matches = (
                upsert_matches(
                    match_records
                )
            )


            total_matches += (
                saved_matches
            )


            print(

                "Matches upserted: "
                f"{saved_matches}"

            )


            # =================================================
            # GET INTERNAL MATCH IDS
            # =================================================

            match_db_ids = (
                get_match_db_ids(

                    [

                        record[
                            "source_match_id"
                        ]

                        for record
                        in match_records

                    ]

                )
            )


            # =================================================
            # MATCH EVENTS
            # =================================================

            league_event_count = 0


            for event in selected_events:

                source_match_id = str(
                    event["id"]
                )


                match_db_id = (
                    match_db_ids.get(
                        source_match_id
                    )
                )


                if match_db_id is None:

                    print(

                        "WARNING: Missing "
                        "Supabase match ID "
                        f"for ESPN event "
                        f"{source_match_id}"

                    )

                    continue


                saved_events = (
                    process_match_events(

                        event,

                        match_db_id,

                        league["slug"]

                    )
                )


                league_event_count += (
                    saved_events
                )


                total_events += (
                    saved_events
                )


            print(

                "Events processed: "
                f"{league_event_count}"

            )


        except Exception as error:

            print("")

            print(

                f"ERROR in "
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

        "Teams processed   : "
        f"{total_teams}"

    )


    print(

        "Matches processed : "
        f"{total_matches}"

    )


    print(

        "Events processed  : "
        f"{total_events}"

    )


    print(
        "Source            : ESPN"
    )

    print(
        "Database mode     : UPSERT"
    )

    print(
        "Date range        : YESTERDAY + TODAY"
    )

    print(
        "Match Events      : ENABLED"
    )

    print(
        "Idempotency       : ENABLED"
    )

    print(
        "Status            : SUCCESS"
    )


    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
