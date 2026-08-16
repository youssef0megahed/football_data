import os
import re
import requests

from datetime import datetime, timezone


# ============================================================
# CONFIGURATION
# ============================================================

THE_NEWS_API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

NEWS_API_URL = "https://www.thenewsapi.com/v1/news/all"

SOURCE_NAME = "The News API"

REQUEST_TIMEOUT = 30

# عدد الأخبار المطلوبة من كل Query
ARTICLES_PER_QUERY = 10


# ============================================================
# NEWS QUERIES
# ============================================================

NEWS_QUERIES = {

    # ========================================================
    # PREMIER LEAGUE
    # ========================================================

    "Premier League":
        '"Premier League" | Arsenal | Liverpool | '
        '"Manchester City" | "Manchester United" | '
        'Chelsea | Tottenham | Newcastle',

    # ========================================================
    # LA LIGA
    # ========================================================

    "La Liga":
        '"La Liga" | "Real Madrid" | Barcelona | '
        '"Atletico Madrid" | Sevilla | Villarreal',

    # ========================================================
    # SERIE A
    # ========================================================

    "Serie A":
        '"Serie A" | "Inter Milan" | "AC Milan" | '
        'Juventus | Napoli | Roma | Lazio | Atalanta',

    # ========================================================
    # BUNDESLIGA
    # ========================================================

    "Bundesliga":
        'Bundesliga | "Bayern Munich" | '
        '"Borussia Dortmund" | "Bayer Leverkusen" | '
        '"RB Leipzig" | Stuttgart',

    # ========================================================
    # LIGUE 1
    # ========================================================

    "Ligue 1":
        '"Ligue 1" | PSG | "Paris Saint-Germain" | '
        'Marseille | Lyon | Monaco | Lille | Nice',

    # ========================================================
    # CHAMPIONS LEAGUE
    # ========================================================

    "Champions League":
        '"Champions League" | "UEFA Champions League"',

    # ========================================================
    # TRANSFERS
    # ========================================================

    "Transfers":
        '"football transfer" | "transfer news" | '
        '"transfer market" | "transfer rumour" | '
        '"transfer rumours"',
}


# ============================================================
# SUPABASE HEADERS
# ============================================================

def get_supabase_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

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
# LOAD TEAMS
# ============================================================

def load_teams():

    url = (
        f"{SUPABASE_URL}/rest/v1/teams"
    )

    params = {
        "select": "id,source_team_id,name,short_name,tla"
    }

    response = requests.get(
        url,
        headers=get_supabase_headers(),
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            "Failed to load teams "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not isinstance(data, list):

        raise Exception(
            "Supabase teams response "
            "is not a list."
        )

    print(
        f"Teams loaded: {len(data)}"
    )

    return data


# ============================================================
# BUILD TEAM INDEX
# ============================================================

def build_team_index(teams):

    index = []

    for team in teams:

        if not isinstance(team, dict):
            continue

        names = []

        for field in [
            team.get("name"),
            team.get("short_name"),
            team.get("tla")
        ]:

            if not field:
                continue

            normalized = normalize_text(
                field
            )

            if (
                normalized
                and len(normalized) >= 3
            ):

                names.append(normalized)

        if not names:
            continue

        index.append({

            "db_id": team.get("id"),

            "source_team_id":
                team.get("source_team_id"),

            "name":
                team.get("name"),

            "short_name":
                team.get("short_name"),

            "tla":
                team.get("tla"),

            "names":
                names,
        })

    return index


# ============================================================
# FIND TEAM
# ============================================================

def find_team(text, team_index):

    normalized = normalize_text(
        text
    )

    if not normalized:
        return None

    # الأطول أولًا لتجنب مطابقة اسم قصير
    # قبل الاسم الكامل
    sorted_teams = sorted(
        team_index,
        key=lambda x: max(
            [
                len(name)
                for name in x["names"]
            ],
            default=0
        ),
        reverse=True
    )

    for team in sorted_teams:

        for name in team["names"]:

            if not name:
                continue

            pattern = (
                rf"\b{re.escape(name)}\b"
            )

            if re.search(
                pattern,
                normalized
            ):

                return team

    return None


# ============================================================
# CLASSIFY ARTICLE
# ============================================================

def classify_article(
    title,
    description,
    query_category
):

    text = normalize_text(
        f"{title} {description}"
    )

    # --------------------------------------------------------
    # TRANSFERS
    # --------------------------------------------------------

    transfer_words = [
        "transfer",
        "transfers",
        "transfer news",
        "transfer market",
        "transfer rumour",
        "transfer rumours",
        "signing",
        "signs",
        "joins",
        "deal",
    ]

    for word in transfer_words:

        if normalize_text(word) in text:

            return "transfers"

    # --------------------------------------------------------
    # INJURIES
    # --------------------------------------------------------

    injury_words = [
        "injury",
        "injured",
        "injuries",
        "fitness",
        "hamstring",
        "knee injury",
        "ankle injury",
    ]

    for word in injury_words:

        if normalize_text(word) in text:

            return "injury"

    # --------------------------------------------------------
    # MANAGER
    # --------------------------------------------------------

    manager_words = [
        "manager",
        "coach",
        "head coach",
        "managerial",
        "manager sacking",
        "manager sacked",
    ]

    for word in manager_words:

        if normalize_text(word) in text:

            return "manager"

    # --------------------------------------------------------
    # FANTASY
    # --------------------------------------------------------

    fantasy_words = [
        "fantasy",
        "fpl",
        "fantasy premier league",
    ]

    for word in fantasy_words:

        if normalize_text(word) in text:

            return "fantasy"

    # --------------------------------------------------------
    # CHAMPIONS LEAGUE
    # --------------------------------------------------------

    if (
        "champions league" in text
        or "uefa champions league" in text
    ):

        return "champions_league"

    # --------------------------------------------------------
    # GENERAL
    # --------------------------------------------------------

    return (
        query_category
        .lower()
        .replace(" ", "_")
    )


# ============================================================
# PARSE DATE
# ============================================================

def parse_published_at(value):

    if not value:
        return None

    try:

        value = str(value)

        if value.endswith("Z"):

            value = value[:-1] + "+00:00"

        parsed = datetime.fromisoformat(
            value
        )

        if parsed.tzinfo is None:

            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:

        return None


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news(query):

    params = {

        "api_token":
            THE_NEWS_API_KEY,

        "search":
            query,

        "search_fields":
            "title,description,keywords",

        "categories":
            "sports",

        "language":
            "en",

        "limit":
            ARTICLES_PER_QUERY,

        "page":
            1,

        "sort":
            "published_at",
    }

    response = requests.get(
        NEWS_API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            "The News API error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    if not isinstance(data, dict):

        raise Exception(
            "The News API response "
            "is not an object."
        )

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
# CHECK DUPLICATE
# ============================================================

def article_exists(source_url):

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
        headers=get_supabase_headers(),
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            "Supabase duplicate check "
            f"failed {response.status_code}: "
            f"{response.text}"
        )

    result = response.json()

    return (
        isinstance(result, list)
        and len(result) > 0
    )


# ============================================================
# GET SOURCE NAME
# ============================================================

def get_source_name(article):

    source_data = article.get(
        "source"
    )

    # --------------------------------------------------------
    # source = dictionary
    # --------------------------------------------------------

    if isinstance(
        source_data,
        dict
    ):

        return (
            source_data.get("name")
            or source_data.get("title")
            or SOURCE_NAME
        )

    # --------------------------------------------------------
    # source = string
    # --------------------------------------------------------

    if isinstance(
        source_data,
        str
    ):

        source_name = (
            source_data.strip()
        )

        if source_name:

            return source_name

    # --------------------------------------------------------
    # fallback
    # --------------------------------------------------------

    return SOURCE_NAME


# ============================================================
# GET IMAGE
# ============================================================

def get_image_url(article):

    image = (
        article.get("image_url")
        or article.get("image")
        or article.get("imageUrl")
    )

    if image is None:
        return None

    image = str(
        image
    ).strip()

    return image or None


# ============================================================
# PREPARE ARTICLE
# ============================================================

def prepare_article(
    article,
    query_category,
    team_index
):

    if not isinstance(
        article,
        dict
    ):

        return None

    # --------------------------------------------------------
    # Basic data
    # --------------------------------------------------------

    title = (
        article.get("title")
        or ""
    ).strip()

    description = (
        article.get("description")
        or ""
    ).strip()

    source_url = (
        article.get("url")
        or ""
    ).strip()

    if not title:
        return None

    if not source_url:
        return None

    # --------------------------------------------------------
    # Article ID
    # --------------------------------------------------------

    article_id = (
        article.get("uuid")
        or article.get("id")
    )

    if article_id is not None:

        article_id = str(
            article_id
        )

    # --------------------------------------------------------
    # Team matching
    # --------------------------------------------------------

    combined_text = (
        f"{title} {description}"
    )

    team = find_team(
        combined_text,
        team_index
    )

    team_id = None
    team_name = None

    if team:

        source_team_id = (
            team.get(
                "source_team_id"
            )
        )

        if source_team_id is not None:

            team_id = str(
                source_team_id
            )

        team_name = team.get(
            "name"
        )

    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    category = classify_article(
        title,
        description,
        query_category
    )

    # --------------------------------------------------------
    # League
    # --------------------------------------------------------

    league = None

    if query_category in [
        "Premier League",
        "La Liga",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
        "Champions League",
    ]:

        league = query_category

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    source_name = get_source_name(
        article
    )

    # --------------------------------------------------------
    # Image
    # --------------------------------------------------------

    image_url = get_image_url(
        article
    )

    # --------------------------------------------------------
    # Date
    # --------------------------------------------------------

    published_at = parse_published_at(
        article.get("published_at")
    )

    # --------------------------------------------------------
    # Database record
    # --------------------------------------------------------

    return {

        "news_type":
            "EXTERNAL",

        "source":
            source_name,

        "source_url":
            source_url,

        "source_article_id":
            article_id,

        "title_original":
            title,

        "summary_original":
            description,

        "title_ar":
            None,

        "summary_ar":
            None,

        "image_url":
            image_url,

        "category":
            category,

        "league":
            league,

        "team_id":
            team_id,

        "team_name":
            team_name,

        "player_name":
            None,

        "published_at":
            published_at,

        "collected_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "status":
            "NEW",

        "telegram_sent":
            False,

        "telegram_sent_at":
            None,

        "facebook_sent":
            False,

        "facebook_sent_at":
            None,

        "ai_processed":
            False,

        "ai_processed_at":
            None,
    }


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(article):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    headers = {
        **get_supabase_headers(),

        "Prefer":
            "resolution=ignore-duplicates,"
            "return=minimal",
    }

    response = requests.post(
        url,
        headers=headers,
        json=article,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code not in [
        200,
        201,
        204,
    ]:

        raise Exception(
            "Supabase insert failed "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# PROCESS QUERY
# ============================================================

def process_query(
    query_category,
    query,
    team_index
):

    print("")
    print("-" * 70)

    print(
        f"Query: {query_category}"
    )

    try:

        articles = fetch_news(
            query
        )

    except Exception as error:

        print(
            f"❌ API ERROR: {error}"
        )

        return {
            "received": 0,
            "saved": 0,
            "duplicates": 0,
            "invalid": 0,
        }

    print(
        f"Articles received: "
        f"{len(articles)}"
    )

    received = len(
        articles
    )

    saved = 0
    duplicates = 0
    invalid = 0

    for article in articles:

        try:

            if not isinstance(
                article,
                dict
            ):

                invalid += 1

                continue

            source_url = (
                article.get("url")
                or ""
            ).strip()

            if not source_url:

                invalid += 1

                continue

            # ------------------------------------------------
            # Duplicate
            # ------------------------------------------------

            if article_exists(
                source_url
            ):

                duplicates += 1

                print(
                    f"⏭️ Duplicate: "
                    f"{article.get('title', '')}"
                )

                continue

            # ------------------------------------------------
            # Prepare
            # ------------------------------------------------

            record = prepare_article(
                article,
                query_category,
                team_index
            )

            if not record:

                invalid += 1

                continue

            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            save_article(
                record
            )

            saved += 1

            team_label = (
                record.get(
                    "team_name"
                )
                or "-"
            )

            print(
                f"✅ Saved: "
                f"{record['title_original']}"
            )

            print(
                f"   Source: "
                f"{record['source']}"
            )

            print(
                f"   Category: "
                f"{record['category']}"
            )

            print(
                f"   Team: "
                f"{team_label}"
            )

        except Exception as error:

            invalid += 1

            print(
                f"❌ Article error: "
                f"{error}"
            )

            continue

    print("")
    print(
        f"Received   : {received}"
    )

    print(
        f"Saved      : {saved}"
    )

    print(
        f"Duplicates : {duplicates}"
    )

    print(
        f"Invalid    : {invalid}"
    )

    return {
        "received": received,
        "saved": saved,
        "duplicates": duplicates,
        "invalid": invalid,
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

    # ========================================================
    # ENVIRONMENT CHECK
    # ========================================================

    if not THE_NEWS_API_KEY:

        raise Exception(
            "THE_NEWS_API_KEY "
            "is missing."
        )

    if not SUPABASE_URL:

        raise Exception(
            "SUPABASE_URL "
            "is missing."
        )

    if not SUPABASE_KEY:

        raise Exception(
            "SUPABASE_KEY "
            "is missing."
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

    # ========================================================
    # PROCESS
    # ========================================================

    total_received = 0
    total_saved = 0
    total_duplicates = 0
    total_invalid = 0

    total_queries = len(
        NEWS_QUERIES
    )

    print(
        f"Queries: "
        f"{total_queries}"
    )

    for query_category, query in (
        NEWS_QUERIES.items()
    ):

        result = process_query(
            query_category,
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
        f"{total_queries}"
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
