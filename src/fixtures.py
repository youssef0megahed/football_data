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

BASE_URL = "https://api.football-data.org/v4/competitions"

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
# HEADERS
# ============================================================

FOOTBALL_HEADERS = {
    "X-Auth-Token": FOOTBALL_DATA_TOKEN
}

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}


# ============================================================
# CURRENT SEASON
# ============================================================

def get_current_season():

    now = datetime.now(TIMEZONE)

    if now.month >= 7:
        return now.year

    return now.year - 1


# ============================================================
# GET COMPETITION MATCHES
# ============================================================

def get_competition_matches(competition_code, season):

    url = f"{BASE_URL}/{competition_code}/matches"

    params = {
        "season": season
    }

    response = requests.get(
        url,
        headers=FOOTBALL_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(
            f"Football API error "
            f"{response.status_code}: {response.text}"
        )

    data = response.json()

    return data.get("matches", [])


# ============================================================
# CONVERT UTC TO CAIRO
# ============================================================

def convert_to_cairo(utc_date):

    utc_datetime = datetime.fromisoformat(
        utc_date.replace("Z", "+00:00")
    )

    return utc_datetime.astimezone(TIMEZONE)


# ============================================================
# GET COMPETITION ID FROM SUPABASE
# ============================================================

def get_competition_id(competition_code):

    url = f"{SUPABASE_URL}/rest/v1/competitions"

    params = {
        "code": f"eq.{competition_code}",
        "source": "eq.football-data.org",
        "select": "id"
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(
            f"Supabase competition lookup failed "
            f"{response.status_code}: {response.text}"
        )

    data = response.json()

    if not data:
        raise Exception(
            f"Competition {competition_code} "
            f"does not exist in Supabase."
        )

    return data[0]["id"]


# ============================================================
# CONVERT MATCH TO DATABASE RECORD
# ============================================================

def prepare_match(match, competition_id, competition_name, season):

    kickoff_utc = match["utcDate"]

    cairo_datetime = convert_to_cairo(kickoff_utc)

    score = match.get("score", {})
    full_time = score.get("fullTime", {})

    home_score = full_time.get("home")
    away_score = full_time.get("away")

    home_team = match["homeTeam"]
    away_team = match["awayTeam"]

    return {
        "source": "football-data.org",

        "source_match_id": match["id"],

        "competition_id": competition_id,

        "competition_name": competition_name,

        "season": season,

        "kickoff_utc": kickoff_utc,

        "kickoff_local": cairo_datetime.isoformat(),

        "timezone": "Africa/Cairo",

        "home_team_id": str(home_team["id"]),

        "home_team_name": home_team["name"],

        "away_team_id": str(away_team["id"]),

        "away_team_name": away_team["name"],

        "status": match["status"],

        "home_score": home_score,

        "away_score": away_score,

        "venue": match.get("venue"),

        "last_updated_at": match.get("lastUpdated"),
    }


# ============================================================
# UPSERT MATCHES INTO SUPABASE
# ============================================================

def save_matches(matches):

    if not matches:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/matches"

    response = requests.post(
        url,
        headers=SUPABASE_HEADERS,
        json=matches,
        timeout=30
    )

    if response.status_code not in [200, 201]:
        raise Exception(
            f"Supabase insert failed "
            f"{response.status_code}: {response.text}"
        )

    return len(matches)


# ============================================================
# MAIN
# ============================================================

def main():

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

    now = datetime.now(TIMEZONE)

    today = now.date()

    tomorrow = today + timedelta(days=1)

    season = get_current_season()

    print("=" * 70)
    print("FOOTBALL DATA PIPELINE")
    print("=" * 70)

    print(f"Timezone : Africa/Cairo")
    print(f"Today    : {today}")
    print(f"Tomorrow : {tomorrow}")
    print(f"Season   : {season}")

    total_matches = 0
    total_today = 0
    total_tomorrow = 0

    # ========================================================
    # PROCESS FIVE LEAGUES
    # ========================================================

    for league_name, league_info in COMPETITIONS.items():

        competition_code = league_info["code"]

        print("")
        print("=" * 70)
        print(f"🏆 {league_name}")
        print("=" * 70)

        try:

            # ------------------------------------------------
            # Get Supabase competition ID
            # ------------------------------------------------

            competition_id = get_competition_id(
                competition_code
            )

            print(
                f"Supabase Competition ID: "
                f"{competition_id}"
            )

            # ------------------------------------------------
            # Get season matches
            # ------------------------------------------------

            matches = get_competition_matches(
                competition_code,
                season
            )

            print(
                f"Season matches received: "
                f"{len(matches)}"
            )

            database_records = []

            today_count = 0
            tomorrow_count = 0

            # ------------------------------------------------
            # Process matches
            # ------------------------------------------------

            for match in matches:

                cairo_datetime = convert_to_cairo(
                    match["utcDate"]
                )

                match_date = cairo_datetime.date()

                # --------------------------------------------
                # We currently collect only today/tomorrow
                # --------------------------------------------

                if match_date not in [today, tomorrow]:
                    continue

                record = prepare_match(
                    match,
                    competition_id,
                    league_name,
                    season
                )

                database_records.append(record)

                if match_date == today:
                    today_count += 1

                elif match_date == tomorrow:
                    tomorrow_count += 1

            # ------------------------------------------------
            # Save to Supabase
            # ------------------------------------------------

            saved = save_matches(
                database_records
            )

            total_matches += saved

            total_today += today_count

            total_tomorrow += tomorrow_count

            print(
                f"Today: {today_count}"
            )

            print(
                f"Tomorrow: {tomorrow_count}"
            )

            print(
                f"Saved to Supabase: {saved}"
            )

        except Exception as error:

            print("")
            print(
                f"❌ ERROR in {league_name}:"
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
        f"Today matches    : "
        f"{total_today}"
    )

    print(
        f"Tomorrow matches : "
        f"{total_tomorrow}"
    )

    print(
        f"Total saved      : "
        f"{total_matches}"
    )

    print("")
    print("Football API requests: 5")

    print("Status: SUCCESS")

    print("=" * 70)


if __name__ == "__main__":
    main()
