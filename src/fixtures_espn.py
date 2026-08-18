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
# EVENTS THAT CAN BE PUBLISHED
# ============================================================

PUBLISHABLE_EVENT_TYPES = {

    "goal",
    "yellow_card",
    "red_card",
    "substitution",
    "var",
    "penalty",

    "kickoff",
    "start_2nd_half",
    "halftime",
    "fulltime",

}


# ============================================================
# EVENTS THAT MUST NEVER BE PUBLISHED
# ============================================================

IGNORED_EVENT_TYPES = {

    "other",

    "delay",
    "start_delay",
    "end_delay",
    "game_delay",
    "weather_delay",

    "review",
    "official_review",

}


# ============================================================
# SUPABASE HEADERS
# ============================================================

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
# RETRY WITH EXPONENTIAL BACKOFF
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
                f"({attempt}/{MAX_RETRIES}): "
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

def parse_datetime(value):

    if not value:
        return None

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

    return [

        today - timedelta(
            days=1
        ),

        today,

        today + timedelta(
            days=1
        ),

    ]


# ============================================================
# SAFE INTEGER
# ============================================================

def safe_int(value):

    if value is None:
        return None

    try:

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return None


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
                "id,source,source_team_id",

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
# SYNC ALL TEAMS
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
        "=== TEAM SYNC END === "
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
# MATCH STATUS
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

    competition = competitions[0]

    competitors = (
        competition.get(
            "competitors",
            []
        )
    )

    if len(competitors) < 2:

        raise RuntimeError(
            f"Event {event_id} "
            f"does not contain "
            f"two competitors"
        )

    home = None
    away = None

    for competitor in competitors:

        home_away = competitor.get(
            "homeAway"
        )

        if home_away == "home":

            home = competitor

        elif home_away == "away":

            away = competitor

    if home is None:
        home = competitors[0]

    if away is None:
        away = competitors[1]

    home_team = home.get(
        "team",
        {}
    )

    away_team = away.get(
        "team",
        {}
    )

    home_source_id = (
        home_team.get(
            "id"
        )
    )

    away_source_id = (
        away_team.get(
            "id"
        )
    )

    if (
        home_source_id is None
        or
        away_source_id is None
    ):

        raise RuntimeError(
            f"Missing team IDs "
            f"for event {event_id}"
        )

    home_db_id = team_db_ids.get(
        (
            "espn",
            str(
                home_source_id
            ),
        )
    )

    away_db_id = team_db_ids.get(
        (
            "espn",
            str(
                away_source_id
            ),
        )
    )

    kickoff = parse_datetime(
        event_date
    )

    if kickoff is None:

        raise RuntimeError(
            f"Invalid kickoff "
            f"for event {event_id}"
        )

    local_datetime = (
        kickoff.astimezone(
            TIMEZONE
        )
    )

    season = (

        event.get(
            "season",
            {}
        )
        .get(
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
                or
                "Home"
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
                or
                "Away"
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
# GET INTERNAL MATCH IDS
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
# EVENT TYPE DETECTION
# ============================================================

def detect_event_type(
    detail,
):

    event_type = (
        detail.get(
            "type",
            {}
        )
        or {}
    )

    text = (

        event_type.get(
            "text"
        )

        or

        event_type.get(
            "name"
        )

        or ""

    ).lower()

    # --------------------------------------------------------
    # IMPORTANT:
    # Technical ESPN events are ignored.
    # --------------------------------------------------------

    if any(

        value in text

        for value in [

            "delay",
            "postponed",
            "weather",
            "official review",

        ]

    ):

        return "other"

    # --------------------------------------------------------
    # Substitution
    # --------------------------------------------------------

    if (
        "substitution" in text
        or
        "substitute" in text
        or
        "sub" in text
    ):

        return "substitution"

    # --------------------------------------------------------
    # Cards
    # --------------------------------------------------------

    if "yellow" in text:

        return "yellow_card"

    if "red" in text:

        return "red_card"

    # --------------------------------------------------------
    # Goal
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
    # VAR
    # --------------------------------------------------------

    if (
        "var" in text
        or
        "video review" in text
        or
        "review" in text
    ):

        return "var"

    # --------------------------------------------------------
    # Penalty
    # --------------------------------------------------------

    if "penalty" in text:

        return "penalty"

    # --------------------------------------------------------
    # Kickoff
    # --------------------------------------------------------

    if (
        "kickoff" in text
        or
        "kick off" in text
        or
        "match started" in text
    ):

        return "kickoff"

    # --------------------------------------------------------
    # Second half
    # --------------------------------------------------------

    if (
        "second half" in text
        or
        (
            "half" in text
            and
            "start" in text
        )
    ):

        return "start_2nd_half"

    # --------------------------------------------------------
    # Half time
    # --------------------------------------------------------

    if (
        "halftime" in text
        or
        "half time" in text
        or
        (
            "half" in text
            and
            (
                "end" in text
                or
                "ended" in text
            )
        )
    ):

        return "halftime"

    # --------------------------------------------------------
    # Full time
    # --------------------------------------------------------

    if (
        "full time" in text
        or
        "fulltime" in text
        or
        "match ended" in text
        or
        "game ended" in text
    ):

        return "fulltime"

    # --------------------------------------------------------
    # Unknown = OTHER
    #
    # NEVER return raw ESPN type here.
    # This is what prevents start_delay/end_delay
    # from becoming publishable events.
    # --------------------------------------------------------

    return "other"


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
# ATHLETE NAME
# ============================================================

def athlete_name(
    athlete,
):

    if not isinstance(
        athlete,
        dict
    ):

        return ""

    return (

        athlete.get(
            "displayName"
        )

        or

        athlete.get(
            "fullName"
        )

        or

        athlete.get(
            "shortName"
        )

        or

        athlete.get(
            "name"
        )

        or ""

    )


# ============================================================
# ATHLETES (from ESPN's actual "participants" field)
# ============================================================

def extract_athletes(
    detail,
):

    # --------------------------------------------------------
    # ESPN's real match-summary payload nests player data as:
    #   "participants": [{"athlete": {...}}, {"athlete": {...}}]
    #
    # "athletesInvolved" is NOT a field ESPN actually returns
    # for soccer detail events; keeping it only as a defensive
    # fallback in case the schema changes again.
    # --------------------------------------------------------

    participants = (
        detail.get(
            "participants"
        )
        or []
    )

    if participants:

        return [
            participant.get(
                "athlete",
                {}
            )
            or {}

            for participant in participants

            if isinstance(
                participant,
                dict
            )
        ]

    return (
        detail.get(
            "athletesInvolved"
        )
        or []
    )


# ============================================================
# CLOCK
# ============================================================

def extract_clock(
    detail,
):

    clock = (
        detail.get(
            "clock",
            {}
        )
        or {}
    )

    clock_value = clock.get(
        "value"
    )

    display_clock = (
        clock.get(
            "displayValue"
        )
        or
        ""
    )

    minute = None
    extra_time = None

    if isinstance(
        clock_value,
        (
            int,
            float,
        )
    ):

        total_seconds = int(
            clock_value
        )

        minute = (
            total_seconds // 60
        )

        seconds = (
            total_seconds % 60
        )

        if seconds >= 30:

            minute += 1

    if display_clock:

        display_text = (
            str(
                display_clock
            )
            .replace(
                " ",
                ""
            )
        )

        if "+" in display_text:

            try:

                parts = (
                    display_text
                    .replace(
                        "'",
                        ""
                    )
                    .split(
                        "+"
                    )
                )

                minute = int(
                    parts[0]
                )

                extra_time = int(
                    parts[1]
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

    return (
        minute,
        extra_time,
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

        event_type = detect_event_type(
            detail
        )

        # ----------------------------------------------------
        # NEVER store technical / unknown events.
        # ----------------------------------------------------

        if event_type in IGNORED_EVENT_TYPES:
            continue

        if event_type not in PUBLISHABLE_EVENT_TYPES:
            continue

        minute, extra_time = (
            extract_clock(
                detail
            )
        )

        team = (
            detail.get(
                "team",
                {}
            )
            or {}
        )

        athletes = extract_athletes(
            detail
        )

        player = (
            athletes[0]
            if len(athletes) >= 1
            else {}
        )

        assist = (
            athletes[1]
            if len(athletes) >= 2
            else {}
        )

        player_out = {}
        player_in = {}

        if event_type == "substitution":

            # ESPN may return different ordering.
            # First try explicit fields.

            explicit_out = (
                detail.get(
                    "playerOut"
                )
                or
                detail.get(
                    "athleteOut"
                )
                or
                detail.get(
                    "substitutionOut"
                )
            )

            explicit_in = (
                detail.get(
                    "playerIn"
                )
                or
                detail.get(
                    "athleteIn"
                )
                or
                detail.get(
                    "substitutionIn"
                )
            )

            if explicit_out:
                player_out = explicit_out

            if explicit_in:
                player_in = explicit_in

            # Fallback to ESPN's participants order:
            # participants[0] = player coming IN
            # participants[1] = player going OUT
            # (verified against ESPN's own description text,
            # e.g. "X replaces Y" -> X is participants[0]).

            if (
                not player_out
                and
                not player_in
                and
                len(athletes) >= 2
            ):

                player_in = athletes[0]
                player_out = athletes[1]

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
                (
                    team.get(
                        "displayName"
                    )
                    or
                    team.get(
                        "name"
                    )
                    or
                    None
                ),

            "player_id":
                text_id(
                    player.get(
                        "id"
                    )
                ),

            "player_name":
                athlete_name(
                    player
                ),

            "assist_player_id":
                text_id(
                    assist.get(
                        "id"
                    )
                ),

            "assist_player_name":
                athlete_name(
                    assist
                ),

            "player_out_id":
                text_id(
                    player_out.get(
                        "id"
                    )
                    if isinstance(
                        player_out,
                        dict
                    )
                    else None
                ),

            "player_out_name":
                athlete_name(
                    player_out
                ),

            "player_in_id":
                text_id(
                    player_in.get(
                        "id"
                    )
                    if isinstance(
                        player_in,
                        dict
                    )
                    else None
                ),

            "player_in_name":
                athlete_name(
                    player_in
                ),

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

            card_type = (
                detail.get(
                    "type",
                    {}
                )
                or {}
            )

            record["card"] = (
                card_type.get(
                    "text"
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
# EXTRACT + UPSERT PLAYERS
# ============================================================
#
# كل مرة نحفظ فيها أحداث ماتش، نلقط أي لاعب (هداف، صانع، بديل
# داخل/خارج) ونضيفه لجدول players لو لسه مش موجود. لو الاسم
# العربي (name_ar) متسجل قبل كده، مش بنلمسه خالص.
# ============================================================

def extract_players_from_event_records(
    event_records,
    team_db_ids,
):

    players_by_id = {}

    field_pairs = [
        ("player_id", "player_name"),
        ("assist_player_id", "assist_player_name"),
        ("player_out_id", "player_out_name"),
        ("player_in_id", "player_in_name"),
    ]

    for record in event_records:

        team_db_id = team_db_ids.get(
            record.get("team_id")
        )

        for id_field, name_field in field_pairs:

            source_player_id = record.get(id_field)
            name = record.get(name_field)

            if not source_player_id or not name:
                continue

            players_by_id[source_player_id] = {
                "source": "espn",
                "source_player_id": source_player_id,
                "name": name,
                "team_id": team_db_id,
            }

    return list(players_by_id.values())


def upsert_players(
    records,
):

    if not records:
        return 0

    # نبعت بس name/team_id، مش بنبعت name_ar، عشان أي
    # اسم عربي متسجل يدويًا يفضل زي ما هو من غير ما يتمسح.

    supabase_request(

        "POST",

        "players",

        {

            "on_conflict":
                "source,source_player_id"

        },

        records,

        extra_headers={
            "Prefer": (
                "resolution=merge-duplicates,"
                "return=minimal"
            )
        },

    )

    return len(
        records
    )


# ============================================================
# SYNC ONE LEAGUE
# ============================================================

def sync_league(

    league_name,

    league,

    dates,

    team_db_ids,

    totals,

):

    log(
        f"=== {league_name} START ==="
    )

    competition_id = get_competition_id(
        league["code"]
    )

    all_events = {}

    # --------------------------------------------------------
    # SCOREBOARD
    # --------------------------------------------------------

    for target_date in dates:

        try:

            data = get_league_scoreboard(

                league["slug"],

                target_date,

            )

            events = (
                data.get(
                    "events",
                    []
                )
            )

            for event in events:

                event_id = event.get(
                    "id"
                )

                if event_id:

                    all_events[
                        str(event_id)
                    ] = event

        except Exception as error:

            log(
                f"ERROR scoreboard "
                f"{league_name} "
                f"{target_date}: "
                f"{error}"
            )

            continue

    events = list(
        all_events.values()
    )

    log(
        f"{league_name}: "
        f"{len(events)} matches from ESPN"
    )

    if not events:

        log(
            f"=== {league_name} END === "
            "no matches"
        )

        return

    # --------------------------------------------------------
    # SYNC TEAMS FROM MATCHES
    # --------------------------------------------------------

    match_teams = (
        extract_teams_from_events(
            events
        )
    )

    if match_teams:

        ids = upsert_espn_teams(
            match_teams
        )

        team_db_ids.update(
            ids
        )

    # --------------------------------------------------------
    # PREPARE MATCHES
    # --------------------------------------------------------

    match_records = []

    selected_events = []

    fallback_season = str(
        datetime.now(
            TIMEZONE
        ).year
    )

    for event in events:

        try:

            record = prepare_match(

                event,

                competition_id,

                league_name,

                fallback_season,

                team_db_ids,

            )

            match_records.append(
                record
            )

            selected_events.append(
                event
            )

        except Exception as error:

            log(
                f"ERROR preparing "
                f"match "
                f"{event.get('id')}: "
                f"{error}"
            )

            continue

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
    # GET INTERNAL MATCH IDS
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

    league_event_count = 0

    # --------------------------------------------------------
    # MATCH EVENTS
    # --------------------------------------------------------

    for event in selected_events:

        source_match_id = str(
            event["id"]
        )

        match_db_id = match_db_ids.get(
            source_match_id
        )

        if not match_db_id:

            log(
                f"WARNING: internal "
                f"match ID not found "
                f"for {source_match_id}"
            )

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

            try:

                player_records = (
                    extract_players_from_event_records(
                        event_records,
                        team_db_ids,
                    )
                )

                upsert_players(
                    player_records
                )

            except Exception as player_error:

                log(
                    f"WARNING players "
                    f"{league_name} "
                    f"match={source_match_id}: "
                    f"{player_error}"
                )

            if event_records:

                log(

                    f"Events updated: "
                    f"{league_name} "
                    f"match={source_match_id} "
                    f"events={saved}"

                )

        except Exception as error:

            log(

                f"ERROR events "
                f"{league_name} "
                f"match={source_match_id}: "
                f"{error}"

            )

            continue

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

    log(
        "=================================================="
    )

    log(
        "ESPN FIXTURES SYNC START"
    )

    log(
        "Architecture: ESPN -> Python -> Supabase"
    )

    log(
        "=================================================="
    )

    dates = get_target_dates()

    log(
        "Target dates: "
        + ", ".join(
            str(date)
            for date in dates
        )
    )

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    team_db_ids = (
        sync_all_league_teams()
    )

    # --------------------------------------------------------
    # TOTALS
    # --------------------------------------------------------

    totals = {

        "matches":
            0,

        "events":
            0,

    }

    # --------------------------------------------------------
    # LEAGUES
    # --------------------------------------------------------

    failed_leagues = []

    for league_name, league in (
        COMPETITIONS.items()
    ):

        try:

            sync_league(

                league_name,

                league,

                dates,

                team_db_ids,

                totals,

            )

        except Exception as error:

            failed_leagues.append(
                league_name
            )

            log(

                f"FATAL league error "
                f"{league_name}: "
                f"{error}"

            )

            continue

    # --------------------------------------------------------
    # FINAL LOG
    # --------------------------------------------------------

    log(
        "=================================================="
    )

    log(
        "ESPN FIXTURES SYNC END"
    )

    log(
        f"Matches updated: "
        f"{totals['matches']}"
    )

    log(
        f"Events updated: "
        f"{totals['events']}"
    )

    if failed_leagues:

        log(
            "Failed leagues: "
            + ", ".join(
                failed_leagues
            )
        )

    else:

        log(
            "Failed leagues: none"
        )

    log(
        "=================================================="
    )

    # --------------------------------------------------------
    # If every league failed, mark workflow as failed.
    # A single league/API problem should not kill all data.
    # --------------------------------------------------------

    if len(
        failed_leagues
    ) == len(
        COMPETITIONS
    ):

        raise RuntimeError(
            "All competitions failed"
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
