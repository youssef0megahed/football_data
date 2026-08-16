import os
import re
import requests

from datetime import datetime, timezone, timedelta


# ============================================================
# FOOTBALL NEWS COLLECTOR
# ============================================================

API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

API_URL = "https://api.thenewsapi.com/v1/news/all"

TIMEOUT = 30

# The News API free plan returns up to 3 articles per request
ARTICLES_PER_QUERY = 3

# Keep only recent articles
MAX_ARTICLE_AGE_HOURS = 48


# ============================================================
# NEWS QUERIES
# ============================================================

NEWS_QUERIES = {
    "Premier League": '"Premier League"',
    "La Liga": '"La Liga"',
    "Serie A": '"Serie A"',
    "Bundesliga": '"Bundesliga"',
    "Ligue 1": '"Ligue 1"',
    "Champions League": '"Champions League"',
    "Transfers": '"football transfer"',
}


# ============================================================
# FOOTBALL KEYWORDS
# ============================================================

FOOTBALL_KEYWORDS = [
    "football",
    "soccer",
    "premier league",
    "la liga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "champions league",
    "europa league",
    "conference league",
    "uefa",
    "fifa",
    "club world cup",
    "fa cup",
    "carabao cup",
    "copa del rey",
    "coppa italia",
    "dfb pokal",
    "coupe de france",
    "transfer",
    "transfers",
    "footballer",
    "soccer player",
]


# ============================================================
# SUPABASE HEADERS
# ============================================================

def supabase_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text).lower()

    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# PARSE DATE
# ============================================================

def parse_article_date(value):

    if not value:
        return None

    try:

        value = str(value)

        if value.endswith("Z"):
            value = value[:-1] + "+00:00"

        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:

        return None


# ============================================================
# CHECK ARTICLE AGE
# ============================================================

def is_recent_article(
    published_at
):

    article_date = parse_article_date(
        published_at
    )

    if article_date is None:
        return False

    now = datetime.now(
        timezone.utc
    )

    minimum_date = (
        now
        - timedelta(
            hours=MAX_ARTICLE_AGE_HOURS
        )
    )

    return article_date >= minimum_date


# ============================================================
# FOOTBALL RELEVANCE
# ============================================================

def is_football_article(
    title,
    description
):

    text = normalize(
        f"{title} {description}"
    )

    if not text:
        return False

    for keyword in FOOTBALL_KEYWORDS:

        keyword_normalized = normalize(
            keyword
        )

        if keyword_normalized in text:
            return True

    return False


# ============================================================
# LOAD TEAMS
# ============================================================

def load_teams():

    url = (
        f"{SUPABASE_URL}/rest/v1/teams"
    )

    params = {
        "select": (
            "id,"
            "source_team_id,"
            "name,"
            "short_name,"
            "tla"
        )
    }

    response = requests.get(
        url,
        headers=supabase_headers(),
        params=params,
        timeout=TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            f"Teams error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not isinstance(
        data,
        list
    ):

        raise Exception(
            "Invalid teams response"
        )

    print(
        f"Teams loaded: {len(data)}"
    )

    return data


# ============================================================
# BUILD TEAM INDEX
# ============================================================

def build_team_index(
    teams
):

    index = []

    for team in teams:

        if not isinstance(
            team,
            dict
        ):
            continue

        names = []

        for value in [
            team.get("name"),
            team.get("short_name"),
            team.get("tla"),
        ]:

            if not value:
                continue

            normalized = normalize(
                value
            )

            if len(normalized) >= 3:

                names.append(
                    normalized
                )

        if not names:
            continue

        index.append({

            "id":
                team.get("id"),

            "source_team_id":
                team.get("source_team_id"),

            "name":
                team.get("name"),

            "short_name":
                team.get("short_name"),

            "tla":
                team.get("tla"),

            "names":
                list(
                    dict.fromkeys(
                        names
                    )
                ),
        })

    return index


# ============================================================
# FIND TEAM IN ARTICLE
# ============================================================

def find_team(
    title,
    description,
    team_index
):

    text = normalize(
        f"{title} {description}"
    )

    if not text:
        return None

    # Longest team names first
    sorted_teams = sorted(
        team_index,
        key=lambda team: max(
            (
                len(name)
                for name in team["names"]
            ),
            default=0
        ),
        reverse=True
    )

    for team in sorted_teams:

        for name in team["names"]:

            pattern = (
                rf"\b{re.escape(name)}\b"
            )

            if re.search(
                pattern,
                text
            ):

                return team

    return None


# ============================================================
# GET SOURCE
# ============================================================

def get_source(
    article
):

    source = article.get(
        "source"
    )

    # The News API normally returns
    # source as a string.
    if isinstance(
        source,
        str
    ):

        source = source.strip()

        if source:
            return source

    # Defensive handling
    if isinstance(
        source,
        dict
    ):

        return (
            source.get("name")
            or source.get("title")
            or "The News API"
        )

    return "The News API"


# ============================================================
# GET IMAGE
# ============================================================

def get_image(
    article
):

    image = (
        article.get("image_url")
        or article.get("image")
    )

    if not image:
        return None

    return str(
        image
    ).strip()


# ============================================================
# CLASSIFY ARTICLE
# ============================================================

def classify_article(
    title,
    description,
    query_name
):

    text = normalize(
        f"{title} {description}"
    )

    # --------------------------------------------------------
    # TRANSFERS
    # --------------------------------------------------------

    transfer_keywords = [
        "transfer",
        "transfers",
        "transfer market",
        "transfer news",
        "transfer rumour",
        "transfer rumours",
        "transfer rumor",
        "transfer rumors",
        "signing",
        "signings",
        "signed",
        "joins",
        "joined",
    ]

    for keyword in transfer_keywords:

        if normalize(
            keyword
        ) in text:

            return "transfers"

    # --------------------------------------------------------
    # INJURIES
    # --------------------------------------------------------

    injury_keywords = [
        "injury",
        "injured",
        "injuries",
        "hamstring",
        "knee injury",
        "ankle injury",
        "fitness",
        "sidelined",
    ]

    for keyword in injury_keywords:

        if normalize(
            keyword
        ) in text:

            return "injury"

    # --------------------------------------------------------
    # MANAGER
    # --------------------------------------------------------

    manager_keywords = [
        "manager",
        "coach",
        "head coach",
        "managerial",
        "sacked",
        "sacking",
        "appointed manager",
    ]

    for keyword in manager_keywords:

        if normalize(
            keyword
        ) in text:

            return "manager"

    # --------------------------------------------------------
    # FANTASY
    # --------------------------------------------------------

    fantasy_keywords = [
        "fantasy",
        "fpl",
        "fantasy premier league",
    ]

    for keyword in fantasy_keywords:

        if normalize(
            keyword
        ) in text:

            return "fantasy"

    # --------------------------------------------------------
    # CHAMPIONS LEAGUE
    # --------------------------------------------------------

    if (
        "champions league" in text
        or
        "uefa champions league" in text
    ):

        return "champions_league"

    # --------------------------------------------------------
    # DEFAULT
    # --------------------------------------------------------

    return (
        query_name
        .lower()
        .replace(" ", "_")
    )


# ============================================================
# GET LEAGUE
# ============================================================

def get_league(
    query_name
):

    supported_leagues = {

        "Premier League":
            "Premier League",

        "La Liga":
            "La Liga",

        "Serie A":
            "Serie A",

        "Bundesliga":
            "Bundesliga",

        "Ligue 1":
            "Ligue 1",

        "Champions League":
            "Champions League",
    }

    return supported_leagues.get(
        query_name
    )


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news(
    query_name,
    query
):

    print(
        f"Search: {query}"
    )

    # IMPORTANT:
    # Keep this request intentionally simple.
    # This exact structure was verified
    # successfully with HTTP 200.

    params = {

        "api_token":
            API_KEY,

        "search":
            query,

        "language":
            "en",

        "limit":
            ARTICLES_PER_QUERY,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=TIMEOUT
    )

    print(
        f"HTTP: {response.status_code}"
    )

    if response.status_code != 200:

        print(
            "❌ The News API error:"
        )

        print(
            response.text[:2000]
        )

        return []

    try:

        data = response.json()

    except Exception:

        print(
            "❌ API returned invalid JSON"
        )

        print(
            response.text[:1000]
        )

        return []

    if not isinstance(
        data,
        dict
    ):

        print(
            "❌ Invalid API response"
        )

        return []

    articles = data.get(
        "data",
        []
    )

    if not isinstance(
        articles,
        list
    ):

        print(
            "❌ API data is not a list"
        )

        return []

    return articles


# ============================================================
# CHECK DUPLICATE
# ============================================================

def article_exists(
    source_url
):

    if not source_url:
        return False

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    params = {

        "source_url":
            f"eq.{source_url}",

        "select":
            "id",

        "limit":
            "1",
    }

    response = requests.get(
        url,
        headers=supabase_headers(),
        params=params,
        timeout=TIMEOUT
    )

    if response.status_code != 200:

        print(
            "⚠️ Duplicate check failed:"
        )

        print(
            response.text[:500]
        )

        return False

    data = response.json()

    return (
        isinstance(
            data,
            list
        )
        and
        len(data) > 0
    )


# ============================================================
# PREPARE ARTICLE
# ============================================================

def prepare_article(
    article,
    query_name,
    team_index
):

    if not isinstance(
        article,
        dict
    ):

        return None, "invalid"


    # ========================================================
    # TITLE
    # ========================================================

    title = (
        article.get("title")
        or ""
    ).strip()

    if not title:

        return None, "missing_title"


    # ========================================================
    # DESCRIPTION / SNIPPET
    # ========================================================

    description = (
        article.get("description")
        or article.get("snippet")
        or ""
    ).strip()


    # ========================================================
    # URL
    # ========================================================

    source_url = (
        article.get("url")
        or ""
    ).strip()

    if not source_url:

        return None, "missing_url"


    # ========================================================
    # DATE
    # ========================================================

    published_at = (
        article.get(
            "published_at"
        )
    )

    article_date = parse_article_date(
        published_at
    )

    if article_date is None:

        return None, "invalid_date"


    # ========================================================
    # RECENT FILTER
    # ========================================================

    if not is_recent_article(
        published_at
    ):

        return None, "old"


    # ========================================================
    # FOOTBALL FILTER
    # ========================================================

    if not is_football_article(
        title,
        description
    ):

        return None, "not_football"


    # ========================================================
    # TEAM
    # ========================================================

    team = find_team(
        title,
        description,
        team_index
    )

    team_id = None
    team_name = None

    if team:

        source_team_id = team.get(
            "source_team_id"
        )

        if source_team_id is not None:

            team_id = str(
                source_team_id
            )

        team_name = team.get(
            "name"
        )


    # ========================================================
    # CATEGORY
    # ========================================================

    category = classify_article(
        title,
        description,
        query_name
    )


    # ========================================================
    # LEAGUE
    # ========================================================

    league = get_league(
        query_name
    )


    # ========================================================
    # ARTICLE ID
    # ========================================================

    source_article_id = (
        article.get("uuid")
        or article.get("id")
        or ""
    )

    source_article_id = str(
        source_article_id
    )


    # ========================================================
    # CONTENT
    # ========================================================

    content = description

    if not content:

        content = title


    # ========================================================
    # TIMESTAMPS
    # ========================================================

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()


    # ========================================================
    # RECORD
    # ========================================================

    record = {

        # ----------------------------------------------------
        # REQUIRED DATABASE FIELDS
        # ----------------------------------------------------

        "title":
            title,

        "content":
            content,

        # ----------------------------------------------------
        # NEWS
        # ----------------------------------------------------

        "news_type":
            "EXTERNAL",

        # ----------------------------------------------------
        # MATCH
        # ----------------------------------------------------

        # External/general news may not
        # belong to a specific match.
        #
        # Therefore match_id is intentionally
        # omitted and remains NULL.
        #
        # Do NOT use a fake match ID.

        # ----------------------------------------------------
        # SOURCE
        # ----------------------------------------------------

        "source":
            get_source(article),

        "source_url":
            source_url,

        "source_article_id":
            source_article_id,

        # ----------------------------------------------------
        # ORIGINAL CONTENT
        # ----------------------------------------------------

        "title_original":
            title,

        "summary_original":
            description,

        # ----------------------------------------------------
        # ARABIC CONTENT
        # ----------------------------------------------------

        # AI Engine will fill these later.
        "title_ar":
            None,

        "summary_ar":
            None,

        # ----------------------------------------------------
        # MEDIA
        # ----------------------------------------------------

        "image_url":
            get_image(article),

        # ----------------------------------------------------
        # CLASSIFICATION
        # ----------------------------------------------------

        "category":
            category,

        "league":
            league,

        # ----------------------------------------------------
        # TEAM
        # ----------------------------------------------------

        "team_id":
            team_id,

        "team_name":
            team_name,

        # ----------------------------------------------------
        # PLAYER
        # ----------------------------------------------------

        "player_name":
            None,

        # ----------------------------------------------------
        # DATES
        # ----------------------------------------------------

        "published_at":
            article_date.isoformat(),

        "collected_at":
            collected_at,

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        "status":
            "NEW",

        # ----------------------------------------------------
        # TELEGRAM
        # ----------------------------------------------------

        "telegram_sent":
            False,

        "telegram_sent_at":
            None,

        # ----------------------------------------------------
        # FACEBOOK
        # ----------------------------------------------------

        "facebook_sent":
            False,

        "facebook_sent_at":
            None,

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        "ai_processed":
            False,

        "ai_processed_at":
            None,
    }

    return record, "ok"


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(
    article
):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    headers = {
        **supabase_headers(),

        "Prefer":
            "return=minimal",
    }

    response = requests.post(
        url,
        headers=headers,
        json=article,
        timeout=TIMEOUT
    )

    if response.status_code in [
        200,
        201,
        204,
    ]:

        return True

    if response.status_code == 409:

        return False

    print(
        "❌ Supabase error:"
    )

    print(
        response.text[:2000]
    )

    return False


# ============================================================
# PROCESS QUERY
# ============================================================

def process_query(
    query_name,
    query,
    team_index
):

    print("")
    print("-" * 70)

    print(
        f"Query: {query_name}"
    )

    articles = fetch_news(
        query_name,
        query
    )

    print(
        f"Articles received: "
        f"{len(articles)}"
    )

    saved = 0
    duplicates = 0
    old_articles = 0
    non_football = 0
    invalid = 0

    for article in articles:

        try:

            # =================================================
            # PREPARE
            # =================================================

            record, status = prepare_article(
                article,
                query_name,
                team_index
            )

            # =================================================
            # FILTER RESULTS
            # =================================================

            if status == "old":

                old_articles += 1

                print(
                    "⏭️ Old article:"
                    f" {article.get('title', '')}"
                )

                continue

            if status == "not_football":

                non_football += 1

                print(
                    "⏭️ Not football:"
                    f" {article.get('title', '')}"
                )

                continue

            if status != "ok":

                invalid += 1

                print(
                    "⏭️ Invalid article:"
                    f" {status}"
                )

                continue

            # =================================================
            # DUPLICATE
            # =================================================

            if article_exists(
                record[
                    "source_url"
                ]
            ):

                duplicates += 1

                print(
                    "⏭️ Duplicate:"
                    f" {record['title']}"
                )

                continue

            # =================================================
            # SAVE
            # =================================================

            if save_article(
                record
            ):

                saved += 1

                print(
                    "✅ Saved:"
                    f" {record['title']}"
                )

                print(
                    "   Source:"
                    f" {record['source']}"
                )

                print(
                    "   Published:"
                    f" {record['published_at']}"
                )

                print(
                    "   Category:"
                    f" {record['category']}"
                )

                print(
                    "   League:"
                    f" {record['league'] or '-'}"
                )

                print(
                    "   Team:"
                    f" {record['team_name'] or '-'}"
                )

        except Exception as error:

            invalid += 1

            print(
                "❌ Article processing error:"
            )

            print(
                str(error)
            )


    # ========================================================
    # QUERY SUMMARY
    # ========================================================

    print("")
    print(
        f"Saved          : {saved}"
    )

    print(
        f"Duplicates     : {duplicates}"
    )

    print(
        f"Old articles   : {old_articles}"
    )

    print(
        f"Not football   : {non_football}"
    )

    print(
        f"Invalid        : {invalid}"
    )

    return {

        "received":
            len(articles),

        "saved":
            saved,

        "duplicates":
            duplicates,

        "old":
            old_articles,

        "non_football":
            non_football,

        "invalid":
            invalid,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("FOOTBALL NEWS COLLECTOR")
    print("=" * 70)

    print(
        "News API : The News API"
    )

    print(
        "Database : Supabase"
    )

    print(
        f"Articles/query: "
        f"{ARTICLES_PER_QUERY}"
    )

    print(
        f"Max article age: "
        f"{MAX_ARTICLE_AGE_HOURS} hours"
    )

    print("=" * 70)


    # ========================================================
    # ENVIRONMENT
    # ========================================================

    if not API_KEY:

        raise Exception(
            "THE_NEWS_API_KEY is missing."
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
    # LOAD TEAMS
    # ========================================================

    teams = load_teams()

    team_index = build_team_index(
        teams
    )

    print(
        f"Team index: "
        f"{len(team_index)}"
    )

    print(
        f"Queries: "
        f"{len(NEWS_QUERIES)}"
    )


    # ========================================================
    # TOTALS
    # ========================================================

    total_received = 0
    total_saved = 0
    total_duplicates = 0
    total_old = 0
    total_non_football = 0
    total_invalid = 0


    # ========================================================
    # PROCESS ALL QUERIES
    # ========================================================

    for query_name, query in (
        NEWS_QUERIES.items()
    ):

        result = process_query(
            query_name,
            query,
            team_index
        )

        total_received += (
            result["received"]
        )

        total_saved += (
            result["saved"]
        )

        total_duplicates += (
            result["duplicates"]
        )

        total_old += (
            result["old"]
        )

        total_non_football += (
            result["non_football"]
        )

        total_invalid += (
            result["invalid"]
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"Queries processed : "
        f"{len(NEWS_QUERIES)}"
    )

    print(
        f"Articles received : "
        f"{total_received}"
    )

    print(
        f"Articles saved    : "
        f"{total_saved}"
    )

    print(
        f"Duplicates        : "
        f"{total_duplicates}"
    )

    print(
        f"Old articles      : "
        f"{total_old}"
    )

    print(
        f"Not football      : "
        f"{total_non_football}"
    )

    print(
        f"Invalid           : "
        f"{total_invalid}"
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
