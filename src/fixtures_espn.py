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
# TARGET DATES
# ============================================================

def get_target_dates():

    now = datetime.now(TIMEZONE)

    today = now.date()

    yesterday = today - timedelta(days=1)

    return yesterday, today


# ============================================================
# CURRENT SEASON
# ============================================================

def get_current_season():

    now = datetime.now(TIMEZONE)

    if now.month >= 7:
        return now.year

    return now.year - 1


# ============================================================
# ESPN GET
# ============================================================

def espn_get(url, params=None):

    response = requests.get(

        url,

        params=params,

        timeout=REQUEST_TIMEOUT,

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
    league_slug,
    target_date,
):

    url = (
        f"{ESPN_BASE_URL}/"
        f"{league_slug}/scoreboard"
    )

    params = {

        "dates":
            target_date.strftime("%Y%m%d"),

    }

    return espn_get(
        url,
        params,
    )


# ============================================================
# ESPN MATCH SUMMARY
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
            str(event_id),

    }

    return espn_get(
        url,
        params,
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

        timeout=REQUEST_TIMEOUT,

    )

    if response.status_code not in [
        200,
        201,
        204,
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
# GET COMPETITION ID
# ============================================================

def get_competition_id(
    competition_code,
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
                "id,code,name",

        },

    )

    if not data:

        raise Exception(

            f"Competition "
            f"{competition_code} "
            f"with source=espn "
            f"does not exist in Supabase."

        )

    return data[0]["id"]


# ============================================================
# UPSERT TEAMS
# ============================================================

def upsert_teams(events):

    teams = {}

    for event in events:

        competitions = (
            event.get(
                "competitions",
                [],
            )
        )

        if not competitions:
            continue

        competitors = (
            competitions[0].get(
                "competitors",
                [],
            )
        )

        for competitor in competitors:

            team = competitor.get(
                "team",
                {},
            )

            source_team_id = team.get(
                "id"
            )

            if source_team_id is None:
                continue

            source_team_id = str(
                source_team_id
            )

            key = (
                "espn",
                source_team_id,
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

    supabase_request(

        "POST",

        "teams",

        {

            "on_conflict":
                "source,source_team_id",

        },

        list(
            teams.values()
        ),

    )

    source_ids = [

        team["source_team_id"]

        for team in teams.values()

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
                "id,source,source_team_id",

        },

    )

    result = {}

    for row in data:

        result[

            (
                row["source"],
                str(
                    row["source_team_id"]
                ),
            )

        ] = row["id"]

    return result


# ============================================================
# PARSE DATETIME
# ============================================================

def parse_datetime(value):

    return datetime.fromisoformat(

        value.replace(
            "Z",
            "+00:00",
        )

    )


# ============================================================
# GET TEAM NAME
# ============================================================

def get_team_name(team):

    return (

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

    )


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

    event_id = event.get("id")

    event_date = event.get("date")

    competitions = (
        event.get(
            "competitions",
            [],
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

            f"Invalid ESPN match "
            f"payload: {event_id}"

        )

    competition = competitions[0]

    competitors = (
        competition.get(
            "competitors",
            [],
        )
    )

    home = None
    away = None

    for competitor in competitors:

        if competitor.get(
            "homeAway"
        ) == "home":

            home = competitor

        elif competitor.get(
            "homeAway"
        ) == "away":

            away = competitor

    if not home or not away:

        raise Exception(

            f"Could not determine "
            f"home/away teams for "
            f"ESPN event {event_id}."

        )

    home_team = home.get(
        "team",
        {},
    )

    away_team = away.get(
        "team",
        {},
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
            home_source_id,
        )

    )

    away_db_id = team_db_ids.get(

        (
            "espn",
            away_source_id,
        )

    )

    if home_db_id is None:

        raise Exception(

            f"Missing Supabase team ID "
            f"for home team "
            f"{get_team_name(home_team)} "
            f"({home_source_id})"

        )

    if away_db_id is None:

        raise Exception(

            f"Missing Supabase team ID "
            f"for away team "
            f"{get_team_name(away_team)} "
            f"({away_source_id})"

        )

    status_type = (

        competition
        .get(
            "status",
            {},
        )
        .get(
            "type",
            {},
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
            {},
        )
        .get(
            "year"
        )

        or

        fallback_season

    )

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
        ValueError,
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
        ValueError,
    ):

        away_score = None

    venue = (

        competition
        .get(
            "venue",
            {},
        )
        .get(
            "fullName"
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
            get_team_name(
                home_team
            ),

        "away_team_name":
            get_team_name(
                away_team
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
            event_date,

    }


# ============================================================
# UPSERT MATCHES
# ============================================================

def upsert_matches(records):

    if not records:
        return

    supabase_request(

        "POST",

        "matches",

        {

            "on_conflict":
                "source,source_match_id",

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
                "id,source_match_id",

        },

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
#
# IMPORTANT:
# This is ONLY classification.
# It NEVER filters events.
# ============================================================

def get_event_type(detail):

    type_data = detail.get(
        "type",
        {},
    )

    if not isinstance(
        type_data,
        dict,
    ):

        type_data = {}

    text = (

        type_data.get(
            "text"
        )

        or

        type_data.get(
            "name"
        )

        or

        ""

    )

    text_lower = text.lower()

    if (
        "substitution"
        in text_lower
    ):

        return "substitution"

    if (
        "yellow"
        in text_lower
    ):

        return "yellow_card"

    if (
        "red"
        in text_lower
    ):

        return "red_card"

    if (
        "goal"
        in text_lower
    ):

        return "goal"

    if detail.get(
        "scoringPlay"
    ):

        return "goal"

    if (
        "penalty"
        in text_lower
    ):

        return "penalty"

    if (
        "var"
        in text_lower
        or
        "review"
        in text_lower
    ):

        return "var"

    if text_lower:

        return (

            text_lower
            .replace(
                " ",
                "_",
            )

        )

    return "other"


# ============================================================
# EVENT UNIQUE KEY
# ============================================================

def make_event_key(

    match_source_id,

    detail,

    index,

):

    source_event_id = detail.get(
        "id"
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
            ":",
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
# GET ALL ESPN EVENTS
#
# We intentionally collect ALL available
# event-like objects from the summary.
# ============================================================

def get_all_match_events(
    summary,
):

    collected = []

    seen = set()

    # --------------------------------------------------------
    # keyEvents
    # --------------------------------------------------------

    key_events = summary.get(
        "keyEvents",
        [],
    )

    if isinstance(
        key_events,
        list,
    ):

        for item in key_events:

            if not isinstance(
                item,
                dict,
            ):

                continue

            raw_id = item.get(
                "id"
            )

            fingerprint = (

                f"id:{raw_id}"

                if raw_id

                else

                json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                )

            )

            if fingerprint in seen:
                continue

            seen.add(
                fingerprint
            )

            collected.append(
                item
            )

    # --------------------------------------------------------
    # details
    #
    # Only add details that are not already
    # represented in keyEvents.
    # --------------------------------------------------------

    details = summary.get(
        "details",
        [],
    )

    if isinstance(
        details,
        list,
    ):

        for item in details:

            if not isinstance(
                item,
                dict,
            ):

                continue

            raw_id = item.get(
                "id"
            )

            fingerprint = (

                f"id:{raw_id}"

                if raw_id

                else

                json.dumps(
                    item,
                    sort_keys=True,
                    ensure_ascii=False,
                )

            )

            if fingerprint in seen:
                continue

            seen.add(
                fingerprint
            )

            collected.append(
                item
            )

    return collected


# ============================================================
# PARSE MINUTE
# ============================================================

def parse_event_clock(detail):

    clock = detail.get(
        "clock",
        {},
    )

    if not isinstance(
        clock,
        dict,
    ):

        clock = {}

    display_clock = (

        clock.get(
            "displayValue"
        )

        or

        ""

    )

    clock_value = clock.get(
        "value"
    )

    minute = None

    if isinstance(
        clock_value,
        (
            int,
            float,
        ),
    ):

        minute = int(
            clock_value // 60
        )

    else:

        digits = ""

        for char in display_clock:

            if char.isdigit():

                digits += char

            else:

                break

        if digits:

            try:

                minute = int(
                    digits
                )

            except ValueError:

                minute = None

    extra_time = None

    if "+" in display_clock:

        try:

            part = (
                display_clock
                .split("+", 1)[1]
                .replace(
                    "'",
                    "",
                )
                .strip()
            )

            extra_time = int(
                part
            )

        except (
            ValueError,
            IndexError,
        ):

            extra_time = None

    return minute, extra_time


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

    details = get_all_match_events(
        summary
    )

    records = []

    for index, detail in enumerate(
        details
    ):

        event_type = get_event_type(
            detail
        )

        minute, extra_time = (
            parse_event_clock(
                detail
            )
        )

        team = detail.get(
            "team",
            {},
        )

        if not isinstance(
            team,
            dict,
        ):

            team = {}

        team_source_id = team.get(
            "id"
        )

        athletes = detail.get(
            "athletesInvolved",
            [],
        )

        if not isinstance(
            athletes,
            list,
        ):

            athletes = []

        player = (
            athletes[0]
            if len(athletes) >= 1
            and isinstance(
                athletes[0],
                dict,
            )
            else {}
        )

        assist = (
            athletes[1]
            if len(athletes) >= 2
            and isinstance(
                athletes[1],
                dict,
            )
            else {}
        )

        event_key = make_event_key(

            event["id"],

            detail,

            index,

        )

        type_data = detail.get(
            "type",
            {},
        )

        if not isinstance(
            type_data,
            dict,
        ):

            type_data = {}

        card = None

        if event_type in (
            "yellow_card",
            "red_card",
        ):

            card = (

                type_data.get(
                    "text"
                )

                or

                type_data.get(
                    "name"
                )

            )

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
                get_team_name(
                    team
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
                card,

            "home_score":
                detail.get(
                    "homeScore"
                ),

            "away_score":
                detail.get(
                    "awayScore"
                ),

            # IMPORTANT:
            # Keep the complete ESPN event.
            "raw_event":
                detail,

        }

        # ----------------------------------------------------
        # SUBSTITUTION
        # ----------------------------------------------------

        if event_type == "substitution":

            if len(athletes) >= 2:

                player_out = athletes[0]
                player_in = athletes[1]

                if isinstance(
                    player_out,
                    dict,
                ):

                    if player_out.get(
                        "id"
                    ) is not None:

                        record[
                            "player_out_id"
                        ] = str(
                            player_out["id"]
                        )

                    record[
                        "player_out_name"
                    ] = player_out.get(
                        "displayName"
                    )

                if isinstance(
                    player_in,
                    dict,
                ):

                    if player_in.get(
                        "id"
                    ) is not None:

                        record[
                            "player_in_id"
                        ] = str(
                            player_in["id"]
                        )

                    record[
                        "player_in_name"
                    ] = player_in.get(
                        "displayName"
                    )

        records.append(
            record
        )

    return records


# ============================================================
# UPSERT MATCH EVENTS
# ============================================================

def upsert_match_events(records):

    if not records:

        return 0

    # --------------------------------------------------------
    # Remove duplicates inside current batch
    # --------------------------------------------------------

    unique = {}

    for record in records:

        key = (
            record[
                "source"
            ],
            record[
                "source_event_key"
            ],
        )

        unique[key] = record

    records = list(
        unique.values()
    )

    supabase_request(

        "POST",

        "match_events",

        {

            "on_conflict":
                "source,source_event_key",

        },

        records,

    )

    return len(records)


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
        today,
    }

    season = get_current_season()

    # ========================================================
    # HEADER
    # ========================================================

    print("=" * 70)

    print(
        "ESPN FIXTURES + ALL MATCH EVENTS"
    )

    print("=" * 70)

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
        "Events    : ALL AVAILABLE ESPN EVENTS"
    )

    print("=" * 70)

    # ========================================================
    # COUNTERS
    # ========================================================

    total_teams = 0
    total_matches = 0
    total_events = 0

    # ========================================================
    # LEAGUES
    # ========================================================

    for league_name, league in (
        COMPETITIONS.items()
    ):

        print("")
        print("=" * 70)
        print(league_name)
        print("=" * 70)

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
            # SCOREBOARDS
            # =================================================

            all_events = []

            for target_date in sorted(
                target_dates
            ):

                data = (
                    get_league_scoreboard(

                        league["slug"],

                        target_date,

                    )
                )

                day_events = data.get(
                    "events",
                    [],
                )

                print(
                    f"{target_date}: "
                    f"{len(day_events)} matches"
                )

                all_events.extend(
                    day_events
                )

            # =================================================
            # UNIQUE MATCHES
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

            if not events:

                print(
                    "Teams processed: 0"
                )

                print(
                    "Matches upserted: 0"
                )

                print(
                    "Events processed: 0"
                )

                continue

            # =================================================
            # TEAMS
            # =================================================

            team_db_ids = upsert_teams(
                events
            )

            team_count = len(
                team_db_ids
            )

            total_teams += team_count

            print(
                "Teams processed: "
                f"{team_count}"
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

                if match_date not in (
                    target_dates
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

            # =================================================
            # UPSERT MATCHES
            # =================================================

            upsert_matches(
                match_records
            )

            match_count = len(
                match_records
            )

            total_matches += match_count

            print(
                "Matches upserted: "
                f"{match_count}"
            )

            if not match_records:

                print(
                    "Events processed: 0"
                )

                continue

            # =================================================
            # GET MATCH DB IDS
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
            # EVENTS
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

                    raise Exception(

                        "Could not find "
                        "Supabase match ID "
                        f"for ESPN event "
                        f"{source_match_id}"

                    )

                event_records = (
                    prepare_match_events(

                        event,

                        match_db_id,

                        league["slug"],

                    )
                )

                saved_events = (
                    upsert_match_events(
                        event_records
                    )
                )

                league_event_count += (
                    saved_events
                )

                total_events += (
                    saved_events
                )

                print(
                    f"{event.get('name')} "
                    f": {saved_events} events"
                )

            print(
                "Events processed: "
                f"{league_event_count}"
            )

        except Exception as error:

            print("")
            print(
                f"ERROR in {league_name}:"
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
    print("FINAL SUMMARY")
    print("=" * 70)

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
        "Match Events      : ALL AVAILABLE"
    )

    print(
        "Raw ESPN Event    : SAVED"
    )

    print(
        "Idempotency       : ENABLED"
    )

    print(
        "Status            : SUCCESS"
    )

    print("=" * 70)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
