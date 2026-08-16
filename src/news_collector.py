import os
import re
import requests

from datetime import datetime, timezone, timedelta


# ============================================================
# FOOTBALL NEWS COLLECTOR
# ============================================================

API_URL = "https://api.thenewsapi.com/v1/news/all"

API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TIMEOUT = 30

# عدد الأخبار المطلوبة لكل Query
ARTICLES_PER_QUERY = 3

# نطلب من API آخر 48 ساعة
API_LOOKBACK_HOURS = 48

# حماية إضافية داخل البرنامج
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
    "Transfers": 'football + transfer',
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
    "footballer",
    "soccer player",
    "transfer",
    "transfers",
]


# ============================================================
# TRANSFER KEYWORDS
# ============================================================

TRANSFER_KEYWORDS = [
    "transfer",
    "transfers",
    "transfer market",
    "transfer news",
    "transfer window",
    "transfer target",
    "transfer targets",
    "transfer rumour",
    "transfer rumours",
    "transfer rumor",
    "transfer rumors",
    "signing",
    "signings",
    "signed",
    "joins",
    "joined",
    "deal",
    "agrees deal",
    "agreement",
]


# ============================================================
# INJURY KEYWORDS
# ============================================================

INJURY_KEYWORDS = [
    "injury",
    "injured",
    "injuries",
    "hamstring",
    "knee injury",
    "ankle injury",
    "fitness",
    "sidelined",
    "ruled out",
]


# ============================================================
# MANAGER KEYWORDS
# ============================================================

MANAGER_KEYWORDS = [
    "manager",
    "head coach",
    "coach",
    "sacked",
    "sacking",
    "appointed",
    "new manager",
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
# NORMALIZE TEXT
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
# IS RECENT
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
# FOOTBALL FILTER
# ============================================================

def is_football_article(
    title,
    description,
    keywords="",
    categories=None
):

    text = normalize(
        f"{title} {description} {keywords}"
    )

    # The API category is useful as an additional signal.
    if isinstance(categories, list):

        normalized_categories = [
            normalize(x)
            for x in categories
            if x
        ]

        if "sports" in normalized_categories:
            return True

    for keyword in FOOTBALL_KEYWORDS:

        if normalize(keyword) in text:
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
            "Teams request failed: "
            f"{response.status_code} "
            f"{response.text[:1000]}"
        )

    data = response.json()

    if not isinstance(data, list):

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

        if not isinstance(team, dict):
            continue

        names = []

        for value in [
            team.get("name"),
            team.get("short_name"),
            team.get("tla"),
        ]:

            if not value:
                continue

            normalized = normalize(value)

            if len(normalized) >= 3:
                names.append(normalized)

        if not names:
            continue

        index.append({
            "id": team.get("id"),
            "source_team_id": team.get(
                "source_team_id"
            ),
            "name": team.get("name"),
            "short_name": team.get(
                "short_name"
            ),
            "tla": team.get("tla"),
            "names": list(
                dict.fromkeys(names)
            ),
        })

    return index


# ============================================================
# FIND TEAM
# ============================================================

def find_team(
    title,
    description,
    keywords,
    team_index
):

    text = normalize(
        f"{title} {description} {keywords}"
    )

    if not text:
        return None

    # Longer names first to avoid
    # short-name false positives.
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
# SOURCE
# ============================================================

def get_source(article):

    source = article.get("source")

    if isinstance(source, str):

        source = source.strip()

        if source:
            return source

    if isinstance(source, dict):

        return (
            source.get("name")
            or source.get("title")
            or "The News API"
        )

    return "The News API"


# ============================================================
# IMAGE
# ============================================================

def get_image(article):

    image = (
        article.get("image_url")
        or article.get("image")
    )

    if not image:
        return None

    return str(image).strip()


# ============================================================
# CLASSIFY
# ============================================================

def classify_article(
    title,
    description,
    keywords,
    query_name
):

    text = normalize(
        f"{title} {description} {keywords}"
    )

    # --------------------------------------------------------
    # TRANSFERS
    # --------------------------------------------------------

    for keyword in TRANSFER_KEYWORDS:

        if normalize(keyword) in text:
            return "transfers"

    # --------------------------------------------------------
    # INJURIES
    # --------------------------------------------------------

    for keyword in INJURY_KEYWORDS:

        if normalize(keyword) in text:
            return "injury"

    # --------------------------------------------------------
    # MANAGER
    # --------------------------------------------------------

    for keyword in MANAGER_KEYWORDS:

        if normalize(keyword) in text:
            return "manager"

    # --------------------------------------------------------
    # CHAMPIONS LEAGUE
    # --------------------------------------------------------

    if "champions league" in text:
        return "champions_league"

    # --------------------------------------------------------
    # LEAGUES
    # --------------------------------------------------------

    league_categories = {
        "Premier League":
            "premier_league",

        "La Liga":
            "la_liga",

        "Serie A":
            "serie_a",

        "Bundesliga":
            "bundesliga",

        "Ligue 1":
            "ligue_1",

        "Champions League":
            "champions_league",

        "Transfers":
            "transfers",
    }

    return league_categories.get(
        query_name,
        "football"
    )


# ============================================================
# GET LEAGUE
# ============================================================

def get_league(
    query_name
):

    return {

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

    }.get(query_name)


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

    now = datetime.now(
        timezone.utc
    )

    published_after = (
        now
        - timedelta(
            hours=API_LOOKBACK_HOURS
        )
    ).strftime(
        "%Y-%m-%dT%H:%M:%S"
    )

    params = {

        "api_token":
            API_KEY,

        "search":
            query,

        "search_fields":
            "title,description,keywords,main_text",

        "language":
            "en",

        "categories":
            "sports",

        "published_after":
            published_after,

        "sort":
            "published_at",

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
            response.text[:3000]
        )

        return []

    try:

        data = response.json()

    except Exception:

        print(
            "❌ Invalid JSON response"
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

        return []

    return articles


# ============================================================
# DUPLICATE CHECK
# ============================================================

def article_exists(
    source_url,
    source_article_id
):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    # --------------------------------------------------------
    # First check source_article_id
    # --------------------------------------------------------

    if source_article_id:

        params = {

            "source_article_id":
                f"eq.{source_article_id}",

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

        if response.status_code == 200:

            data = response.json()

            if (
                isinstance(data, list)
                and len(data) > 0
            ):
                return True

    # --------------------------------------------------------
    # Then check URL
    # --------------------------------------------------------

    if source_url:

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

        if response.status_code == 200:

            data = response.json()

            if (
                isinstance(data, list)
                and len(data) > 0
            ):
                return True

    return False


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
    # BASIC DATA
    # ========================================================

    title = (
        article.get("title")
        or ""
    ).strip()

    description = (
        article.get("description")
        or article.get("snippet")
        or ""
    ).strip()

    keywords = (
        article.get("keywords")
        or ""
    )

    source_url = (
        article.get("url")
        or ""
    ).strip()

    published_at = (
        article.get("published_at")
    )

    categories = article.get(
        "categories"
    )


    # ========================================================
    # REQUIRED FIELDS
    # ========================================================

    if not title:
        return None, "missing_title"

    if not source_url:
        return None, "missing_url"


    # ========================================================
    # DATE
    # ========================================================

    article_date = parse_article_date(
        published_at
    )

    if article_date is None:
        return None, "invalid_date"

    if not is_recent_article(
        published_at
    ):
        return None, "old"


    # ========================================================
    # FOOTBALL FILTER
    # ========================================================

    if not is_football_article(
        title,
        description,
        keywords,
        categories
    ):
        return None, "not_football"


    # ========================================================
    # TEAM DETECTION
    # ========================================================

    team = find_team(
        title,
        description,
        keywords,
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
        keywords,
        query_name
    )


    # ========================================================
    # LEAGUE
    # ========================================================

    league = get_league(
        query_name
    )


    # ========================================================
    # SOURCE ARTICLE ID
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

    content = (
        description
        or title
    )


    # ========================================================
    # COLLECTED TIME
    # ========================================================

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()


    # ========================================================
    # DATABASE RECORD
    # ========================================================

    record = {

        # Required
        "title":
            title,

        "content":
            content,

        # General
        "news_type":
            "EXTERNAL",

        # IMPORTANT:
        # match_id intentionally omitted.
        # General news does not belong
        # to a specific match.

        # Source
        "source":
            get_source(article),

        "source_url":
            source_url,

        "source_article_id":
            source_article_id,

        # Original
        "title_original":
            title,

        "summary_original":
            description,

        # Arabic
        "title_ar":
            None,

        "summary_ar":
            None,

        # Media
        "image_url":
            get_image(article),

        # Classification
        "category":
            category,

        "league":
            league,

        # Team
        "team_id":
            team_id,

        "team_name":
            team_name,

        # Player
        "player_name":
            None,

        # Dates
        "published_at":
            article_date.isoformat(),

        "collected_at":
            collected_at,

        # Status
        "status":
            "NEW",

        # Telegram
        "telegram_sent":
            False,

        "telegram_sent_at":
            None,

        # Facebook
        "facebook_sent":
            False,

        "facebook_sent_at":
            None,

        # AI
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
    record
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
        json=record,
        timeout=TIMEOUT
    )

    if response.status_code in [
        200,
        201,
        204,
    ]:
        return True

    print(
        "❌ Supabase error:"
    )

    print(
        response.text[:3000]
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

            record, status = prepare_article(
                article,
                query_name,
                team_index
            )

            # ------------------------------------------------
            # OLD
            # ------------------------------------------------

            if status == "old":

                old_articles += 1

                print(
                    "⏭️ Old article: "
                    f"{article.get('title', '')}"
                )

                continue


            # ------------------------------------------------
            # NOT FOOTBALL
            # ------------------------------------------------

            if status == "not_football":

                non_football += 1

                print(
                    "⏭️ Not football: "
                    f"{article.get('title', '')}"
                )

                continue


            # ------------------------------------------------
            # INVALID
            # ------------------------------------------------

            if status != "ok":

                invalid += 1

                print(
                    f"⏭️ Invalid article: "
                    f"{status}"
                )

                continue


            # ------------------------------------------------
            # DUPLICATE
            # ------------------------------------------------

            if article_exists(
                record.get(
                    "source_url"
                ),
                record.get(
                    "source_article_id"
                )
            ):

                duplicates += 1

                print(
                    "⏭️ Duplicate: "
                    f"{record['title']}"
                )

                continue


            # ------------------------------------------------
            # SAVE
            # ------------------------------------------------

            if save_article(
                record
            ):

                saved += 1

                print(
                    "✅ Saved: "
                    f"{record['title']}"
                )

                print(
                    "   Source: "
                    f"{record['source']}"
                )

                print(
                    "   Published: "
                    f"{record['published_at']}"
                )

                print(
                    "   Category: "
                    f"{record['category']}"
                )

                print(
                    "   League: "
                    f"{record['league'] or '-'}"
                )

                print(
                    "   Team: "
                    f"{record['team_name'] or '-'}"
                )

        except Exception as error:

            invalid += 1

            print(
                "❌ Article processing error:"
            )

            print(
                str(error)
            )


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
        f"API lookback: "
        f"{API_LOOKBACK_HOURS} hours"
    )

    print(
        f"Safety filter: "
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
    # PROCESS QUERIES
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
