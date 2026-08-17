import os
import json
import hashlib
import time
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
MAX_RETRIES = 4

ESPN_BASE_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer"
)


# ============================================================
# COMPETITIONS
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
# LOGGING
# ============================================================

def log(message):

    now = datetime.now(
        TIMEZONE
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    print(
        f"[{now} Cairo] {message}",
        flush=True
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_environment():

    missing = []

    if not SUPABASE_URL:
        missing.append(
            "SUPABASE_URL"
        )

    if not SUPABASE_KEY:
        missing.append(
            "SUPABASE_KEY"
        )

    if missing:

        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# RETRY
# ============================================================

def retry_call(
    operation,
    label,
):

    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:

            return operation()

        except Exception as error:

            last_error = error

            if attempt >= MAX_RETRIES:
                break

            delay = (
                2 ** (attempt - 1)
            )

            log(
                f"{label} failed "
                f"(attempt {attempt}/"
                f"{MAX_RETRIES}): "
                f"{error}"
            )

            log(
                f"Retrying in {delay}s..."
            )

            time.sleep(
                delay
            )

    raise RuntimeError(
        f"{label} failed after "
        f"{MAX_RETRIES} attempts: "
        f"{last_error}"
    )


# ============================================================
# ESPN REQUEST
# ============================================================

def espn_get(
    url,
    params=None,
):

    def request():

        response = requests.get(

            url,

            params=params,

            timeout=REQUEST_TIMEOUT,

        )

        if response.status_code == 200:

            return response.json()

        if response.status_code in {
            408,
            429,
            500,
            502,
            503,
            504,
        }:

            raise RuntimeError(
                f"ESPN transient HTTP "
                f"{response.status_code}"
            )

        raise RuntimeError(

            f"ESPN HTTP "
            f"{response.status_code}: "
            f"{response.text[:500]}"

        )

    return retry_call(
        request,
        f"ESPN GET {url}",
    )


# ============================================================
# SUPABASE REQUEST
# ============================================================

def supabase_request(

    method,

    table,

    params=None,

    json_body=None,

):

    url = (
        f"{SUPABASE_URL}"
        f"/rest/v1/{table}"
    )

    def request():

        response = requests.request(

            method,

            url,

            headers=SUPABASE_HEADERS,

            params=params,

            json=json_body,

            timeout=REQUEST_TIMEOUT,

        )

        if response.status_code in {
            200,
            201,
            204,
        }:

            if not response.content:
                return []

            return response.json()

        if response.status_code in {
            408,
            409,
            429,
            500,
            502,
            503,
            504,
        }:

            raise RuntimeError(

                f"Supabase transient HTTP "
                f"{response.status_code}"

            )

        raise RuntimeError(

            f"Supabase {table} "
            f"HTTP {response.status_code}: "
            f"{response.text[:500]}"

        )

    return retry_call(
        request,
        f"Supabase {method} {table}",
    )


# ============================================================
# DATETIME
# ============================================================

def parse_datetime(
    value,
):

    return datetime.fromisoformat(

        value.replace(
            "Z",
            "+00:00"
        )

    )


# ============================================================
# TARGET DATES
# ============================================================

def get_target_dates():

    today = datetime.now(
        TIMEZONE
    ).date()

    return {

        today - timedelta(
            days=1
        ),

        today,

        today + timedelta(
            days=1
        ),

    }


# ============================================================
# ESPN TEAMS
# ============================================================

def get_league_teams(
    league_slug,
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{league_slug}/teams"
    )

    return espn_get(
        url
    )


# ============================================================
# EXTRACT TEAMS
# ============================================================

def extract_teams_from_response(
    data,
):

    teams = []

    for sport in data.get(
        "sports",
        []
    ):

        for league in sport.get(
            "leagues",
            []
        ):

            for item in league.get(
                "teams",
                []
            ):

                team = item.get(
                    "team",
                    item
                )

                if team:

                    teams.append(
                        team
                    )

    return teams


# ============================================================
# EXTRACT TEAMS FROM MATCHES
# ============================================================

def extract_teams_from_events(
    events,
):

    teams = {}

    for event in events:

        competitions = event.get(
            "competitions",
            []
        )

        if not competitions:
            continue

        competitors = (
            competitions[0]
            .get(
                "competitors",
                []
            )
        )

        for competitor in competitors:

            team = competitor.get(
                "team",
                {}
            )

            team_id = team.get(
                "id"
            )

            if team_id is None:
                continue

            teams[
                str(team_id)
            ] = team

    return list(
        teams.values()
    )


# ============================================================
# UPSERT TEAMS
# ============================================================

def upsert_espn_teams(
    teams,
):

    records = {}

    for team in teams:

        source_team_id = team.get(
            "id"
        )

        if source_team_id is None:
            continue

        source_team_id = str(
            source_team_id
        )

        records[
            source_team_id
        ] = {

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
                    or
                    team.get(
                        "shortDisplayName"
                    )
                ),

            "short_name":
                (
                    team.get(
                        "shortDisplayName"
                    )
                    or
                    team.get(
                        "name"
                    )
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

    if not records:
        return {}

    # مهم:
    # لا نرسل name_ar
    # حتى لا نمسح الاسم العربي الموجود.

    supabase_request(

        "POST",

        "teams",

        {
            "on_conflict":
                "source,source_team_id"
        },

        list(
            records.values()
        ),

    )

    source_ids = list(
        records.keys()
    )

    rows = supabase_request(

        "GET",

        "teams",

        {

            "source":
                "eq.espn",

            "source_team_id":
                "in.("
                + ",".join(
                    source_ids
                )
                + ")",

            "select":
                "id,source,source_team_id,name,name_ar",

        },

    )

    return {

        (
            "espn",
            str(
                row[
                    "source_team_id"
                ]
            ),
        ):
            row["id"]

        for row in rows

    }


# ============================================================
# SYNC TEAMS
# ============================================================

def sync_all_league_teams():

    log(
        "=== TEAM SYNC START ==="
    )

    team_db_ids = {}

    for league_name, league in (
        COMPETITIONS.items()
    ):

        try:

            data = get_league_teams(
                league["slug"]
            )

            teams = (
                extract_teams_from_response(
                    data
                )
            )

            ids = upsert_espn_teams(
                teams
            )

            team_db_ids.update(
                ids
            )

            log(
                f"{league_name}: "
                f"{len(ids)} teams synchronized"
            )

        except Exception as error:

            log(
                f"ERROR teams "
                f"{league_name}: "
                f"{error}"
            )

            continue

    log(
        f"=== TEAM SYNC END === "
        f"total={len(team_db_ids)}"
    )

    return team_db_ids


# ============================================================
# COMPETITION
# ============================================================

def get_competition_id(
    competition_code,
):

    rows = supabase_request(

        "GET",

        "competitions",

        {

            "code":
                f"eq.{competition_code}",

            "source":
                "eq.espn",

            "select":
                "id,code,name",

            "limit":
                "1",

        },

    )

    if not rows:

        raise RuntimeError(

            f"Competition "
            f"{competition_code} "
            f"not found in Supabase"

        )

    return rows[0]["id"]


# ============================================================
# SCOREBOARD
# ============================================================

def get_league_scoreboard(
    league_slug,
    date,
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{league_slug}/scoreboard"
    )

    params = {

        "dates":
            date.strftime(
                "%Y%m%d"
            )

    }

    return espn_get(
        url,
        params
    )


# ============================================================
# MATCH SUMMARY
# ============================================================

def get_match_summary(
    event_id,
    league_slug,
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
# STATUS
# ============================================================

def normalize_status(
    event,
):

    competitions = event.get(
        "competitions",
        []
    )

    if not competitions:
        return "SCHEDULED"

    status = (
        competitions[0]
        .get(
            "status",
            {}
        )
    )

    status_type = (
        status.get(
            "type",
            {}
        )
    )

    state = str(

        status_type.get(
            "state"
        )

        or

        status_type.get(
            "name"
        )

        or ""

    ).upper()

    if state in {
        "IN",
        "IN_PLAY",
        "IN_PROGRESS",
        "LIVE",
    }:

        return "IN_PLAY"

    if state in {
        "PAUSED",
        "HALFTIME",
    }:

        return "PAUSED"

    if state in {
        "POSTPONED",
    }:

        return "POSTPONED"

    if state in {
        "CANCELED",
        "CANCELLED",
    }:

        return "CANCELED"

    if state in {
        "POST",
        "FINAL",
        "FINISHED",
        "COMPLETE",
    }:

        return "FINISHED"

    return "SCHEDULED"


# ============================================================
# SCORE
# ============================================================

def safe_int(
    value,
):

    if value is None:
        return None

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# PREPARE MATCH
# ============================================================

def prepare_match(

    event,

    competition_id,

    competition_name,

    fallback_season,

    team_db_ids,

):

    event_id = event.get(
        "id"
    )

    event_date = event.get(
        "date"
    )

    competitions = event.get(
        "competitions",
        []
    )

    if (
        not event_id
        or
        not event_date
        or
        not competitions
    ):

        raise RuntimeError(
            f"Invalid ESPN event "
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

        raise RuntimeError(

            f"Missing home/away "
            f"teams for event "
            f"{event_id}"

        )

    home_team = home.get(
        "team",
        {}
    )

    away_team = away.get(
        "team",
        {}
    )

    home_source_id = str(
        home_team.get(
            "id"
        )
    )

    away_source_id = str(
        away_team.get(
            "id"
        )
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

    if (
        home_db_id is None
        or
        away_db_id is None
    ):

        extra_teams = (
            extract_teams_from_events(
                [event]
            )
        )

        extra_ids = (
            upsert_espn_teams(
                extra_teams
            )
        )

        team_db_ids.update(
            extra_ids
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

    if (
        home_db_id is None
        or
        away_db_id is None
    ):

        raise RuntimeError(

            f"Could not map teams "
            f"for event {event_id}"

        )

    local_datetime = (
        parse_datetime(
            event_date
        ).astimezone(
            TIMEZONE
        )
    )

    season = (
        event.get(
            "season",
            {}
        ).get(
            "year"
        )
        or
        fallback_season
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
            normalize_status(
                event
            ),

        "home_score":
            safe_int(
                home.get(
                    "score"
                )
            ),

        "away_score":
            safe_int(
                away.get(
                    "score"
                )
            ),

        "venue":
            competition.get(
                "venue",
                {}
            ).get(
                "fullName"
            ),

        "last_updated_at":
            datetime.now(
                TIMEZONE
            ).isoformat(),

    }


# ============================================================
# UPSERT MATCHES
# ============================================================

def upsert_matches(
    records,
):

    if not records:
        return

    supabase_request(

        "POST",

        "matches",

        {
            "on_conflict":
                "source,source_match_id"
        },

        records,

    )


# ============================================================
# GET MATCH DB IDS
# ============================================================

def get_match_db_ids(
    source_match_ids,
):

    if not source_match_ids:
        return {}

    ids = ",".join(

        str(value)

        for value in source_match_ids

    )

    rows = supabase_request(

        "GET",

        "matches",

        {

            "source":
                "eq.espn",

            "source_match_id":
                f"in.({ids})",

            "select":
                "id,source_match_id",

        },

    )

    return {

        str(
            row[
                "source_match_id"
            ]
        ):
            row["id"]

        for row in rows

    }


# ============================================================
# EVENT TYPE
# ============================================================

def detect_event_type(
    detail,
):

    event_type = detail.get(
        "type",
        {}
    )

    text = (

        event_type.get(
            "text",
            ""
        )

        or

        event_type.get(
            "name",
            ""
        )

        or ""

    ).lower()

    if (
        "substitution" in text
        or
        "sub" in text
    ):

        return "substitution"

    if "yellow" in text:

        return "yellow_card"

    if (
        "red" in text
        or
        "sending off" in text
    ):

        return "red_card"

    if (
        "goal" in text
        or
        detail.get(
            "scoringPlay"
        )
    ):

        return "goal"

    if (
        "var" in text
        or
        "review" in text
    ):

        return "var"

    if "penalty" in text:

        return "penalty"

    if (
        "kickoff" in text
        or
        "kick off" in text
    ):

        return "kickoff"

    if (
        "half" in text
        and
        (
            "start" in text
        )
    ):

        return "start_2nd_half"

    if (
        "half" in text
        and
        (
            "end" in text
            or
            "time" in text
        )
    ):

        return "halftime"

    if (
        "end" in text
        and
        (
            "game" in text
            or
            "match" in text
            or
            "regular" in text
        )
    ):

        return "fulltime"

    cleaned = (
        text
        .replace(
            " ",
            "_"
        )
        .replace(
            "-",
            "_"
        )
    )

    return (
        cleaned
        or
        "other"
    )


# ============================================================
# EVENT KEY
# ============================================================

def make_event_key(

    match_source_id,

    detail,

    index,

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
        ),

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

    league_slug,

):

    summary = get_match_summary(

        event["id"],

        league_slug,

    )

    details = (

        summary.get(
            "keyEvents"
        )

        or

        summary.get(
            "details"
        )

        or []

    )

    records = []

    for index, detail in enumerate(
        details
    ):

        if not isinstance(
            detail,
            dict
        ):

            continue

        event_type = (
            detect_event_type(
                detail
            )
        )

        clock = (
            detail.get(
                "clock",
                {}
            )
            or {}
        )

        clock_value = (
            clock.get(
                "value"
            )
        )

        display_clock = (
            clock.get(
                "displayValue",
                ""
            )
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

        extra_time = None

        if "+" in str(
            display_clock
        ):

            try:

                extra_time = int(

                    str(
                        display_clock
                    )
                    .split(
                        "+",
                        1
                    )[1]
                    .replace(
                        "'",
                        ""
                    )

                )

            except (
                ValueError,
                IndexError,
            ):

                pass

        team = (
            detail.get(
                "team",
                {}
            )
            or {}
        )

        athletes = (
            detail.get(
                "athletesInvolved"
            )
            or []
        )

        player = (
            athletes[0]
            if athletes
            else {}
        )

        assist = (

            athletes[1]

            if len(
                athletes
            ) > 1

            else {}

        )

        def text_id(
            value
        ):

            if value is None:
                return None

            return str(
                value
            )

        record = {

            "match_id":
                match_db_id,

            "source":
                "espn",

            "source_event_key":
                make_event_key(

                    event["id"],

                    detail,

                    index,

                ),

            "event_type":
                event_type,

            "minute":
                minute,

            "extra_time":
                extra_time,

            "team_id":
                text_id(
                    team.get(
                        "id"
                    )
                ),

            "team_name":
                team.get(
                    "displayName"
                ),

            "player_id":
                text_id(
                    player.get(
                        "id"
                    )
                ),

            "player_name":
                player.get(
                    "displayName"
                ),

            "assist_player_id":
                text_id(
                    assist.get(
                        "id"
                    )
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
                None,

            "home_score":
                safe_int(
                    detail.get(
                        "homeScore"
                    )
                ),

            "away_score":
                safe_int(
                    detail.get(
                        "awayScore"
                    )
                ),

            "raw_event":
                detail,

        }

        if event_type in {
            "yellow_card",
            "red_card",
        }:

            record["card"] = (

                detail.get(
                    "type",
                    {}
                ).get(
                    "text"
                )

            )

        if (
            event_type ==
            "substitution"
        ):

            if len(
                athletes
            ) >= 2:

                player_out = (
                    athletes[0]
                )

                player_in = (
                    athletes[1]
                )

                record[
                    "player_out_id"
                ] = text_id(
                    player_out.get(
                        "id"
                    )
                )

                record[
                    "player_out_name"
                ] = (
                    player_out.get(
                        "displayName"
                    )
                )

                record[
                    "player_in_id"
                ] = text_id(
                    player_in.get(
                        "id"
                    )
                )

                record[
                    "player_in_name"
                ] = (
                    player_in.get(
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
    records,
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

        records,

    )

    return len(
        records
    )


# ============================================================
# PROCESS LEAGUE
# ============================================================

def process_league(

    league_name,

    league,

    target_dates,

    season,

    totals,

    team_db_ids,

):

    log(
        f"=== {league_name} START ==="
    )

    competition_id = (
        get_competition_id(
            league["code"]
        )
    )

    all_events = []

    # --------------------------------------------------------
    # SCOREBOARDS
    # --------------------------------------------------------

    for target_date in sorted(
        target_dates
    ):

        data = (
            get_league_scoreboard(

                league["slug"],

                target_date,

            )
        )

        day_events = (
            data.get(
                "events",
                []
            )
        )

        log(

            f"{league_name} "
            f"{target_date}: "
            f"{len(day_events)} matches"

        )

        all_events.extend(
            day_events
        )

    # --------------------------------------------------------
    # REMOVE DUPLICATES
    # --------------------------------------------------------

    unique_events = {

        str(
            event["id"]
        ):
            event

        for event in all_events

        if event.get(
            "id"
        )

    }

    events = list(
        unique_events.values()
    )

    # --------------------------------------------------------
    # TEAMS FROM MATCHES
    # --------------------------------------------------------

    event_teams = (
        extract_teams_from_events(
            events
        )
    )

    team_ids = (
        upsert_espn_teams(
            event_teams
        )
    )

    team_db_ids.update(
        team_ids
    )

    # --------------------------------------------------------
    # PREPARE MATCHES
    # --------------------------------------------------------

    match_records = []

    selected_events = []

    for event in events:

        event_date = event.get(
            "date"
        )

        if not event_date:
            continue

        local_date = (

            parse_datetime(
                event_date
            )
            .astimezone(
                TIMEZONE
            )
            .date()

        )

        if (
            local_date
            not in target_dates
        ):

            continue

        record = prepare_match(

            event,

            competition_id,

            league_name,

            season,

            team_db_ids,

        )

        match_records.append(
            record
        )

        selected_events.append(
            event
        )

    # --------------------------------------------------------
    # UPSERT MATCHES
    # --------------------------------------------------------

    upsert_matches(
        match_records
    )

    totals[
        "matches"
    ] += len(
        match_records
    )

    # --------------------------------------------------------
    # GET INTERNAL IDS
    # --------------------------------------------------------

    match_db_ids = (
        get_match_db_ids(

            [
                record[
                    "source_match_id"
                ]

                for record in match_records

            ]

        )
    )

    # --------------------------------------------------------
    # EVENTS
    # --------------------------------------------------------

    today = datetime.now(
        TIMEZONE
    ).date()

    league_event_count = 0

    for event in selected_events:

        match_db_id = (
            match_db_ids.get(
                str(
                    event["id"]
                )
            )
        )

        if match_db_id is None:

            raise RuntimeError(

                f"Missing database ID "
                f"for ESPN event "
                f"{event['id']}"

            )

        status = normalize_status(
            event
        )

        event_date = (

            parse_datetime(
                event["date"]
            )
            .astimezone(
                TIMEZONE
            )
            .date()

        )

        # ----------------------------------------------------
        # FUTURE MATCH
        #
        # Don't request summary unnecessarily.
        # ----------------------------------------------------

        if (
            status ==
            "SCHEDULED"
            and
            event_date >
            today
        ):

            continue

        try:

            event_records = (
                prepare_match_events(

                    event,

                    match_db_id,

                    league["slug"],

                )
            )

            saved = (
                upsert_match_events(
                    event_records
                )
            )

            league_event_count += saved

            totals[
                "events"
            ] += saved

            if event_records:

                log(

                    f"Events updated: "
                    f"{league_name} "
                    f"match={event['id']} "
                    f"events={saved}"

                )

        except Exception as error:

            # ------------------------------------------------
            # Important:
            # Match itself has already been saved.
            # If event fetching fails, don't lose the match.
            # ------------------------------------------------

            log(

                f"ERROR events for "
                f"{league_name} "
                f"match={event['id']}: "
                f"{error}"

            )

            totals[
                "event_errors"
            ] += 1

    log(

        f"=== {league_name} END === "
        f"matches={len(match_records)} "
        f"events={league_event_count}"

    )


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()

    now = datetime.now(
        TIMEZONE
    )

    target_dates = (
        get_target_dates()
    )

    # الموسم يبدأ عادة في يوليو.
    season = (
        now.year
        if now.month >= 7
        else now.year - 1
    )

    totals = {

        "matches":
            0,

        "events":
            0,

        "event_errors":
            0,

    }

    errors = []

    log(
        "=================================================="
    )

    log(
        "ESPN FOOTBALL DATA PIPELINE START"
    )

    log(
        f"Target dates: "
        f"{sorted(target_dates)}"
    )

    log(
        f"Season: {season}"
    )

    log(
        "Mode: UPSERT / IDEMPOTENT / NO DELETE"
    )

    log(
        "=================================================="
    )

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    try:

        team_db_ids = (
            sync_all_league_teams()
        )

    except Exception as error:

        team_db_ids = {}

        errors.append(
            f"Team sync: {error}"
        )

        log(
            f"CRITICAL TEAM SYNC ERROR: "
            f"{error}"
        )

    # --------------------------------------------------------
    # LEAGUES
    # --------------------------------------------------------

    for league_name, league in (
        COMPETITIONS.items()
    ):

        try:

            process_league(

                league_name,

                league,

                target_dates,

                season,

                totals,

                team_db_ids,

            )

        except Exception as error:

            errors.append(

                f"{league_name}: "
                f"{error}"

            )

            log(

                f"ERROR {league_name}: "
                f"{error}"

            )

            # Continue with next league.

            continue

    # --------------------------------------------------------
    # FINAL LOG
    # --------------------------------------------------------

    log(
        "=================================================="
    )

    log(
        "ESPN FOOTBALL DATA PIPELINE END"
    )

    log(
        f"Matches updated: "
        f"{totals['matches']}"
    )

    log(
        f"Events updated: "
        f"{totals['events']}"
    )

    log(
        f"Event errors: "
        f"{totals['event_errors']}"
    )

    log(
        f"League errors: "
        f"{len(errors)}"
    )

    log(
        "=================================================="
    )

    if errors:

        for error in errors:

            log(
                f"PIPELINE ERROR: "
                f"{error}"
            )

        raise RuntimeError(
            "One or more pipeline sections failed."
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
