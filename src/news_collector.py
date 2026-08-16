import os
import re
import requests

from datetime import datetime, timedelta, timezone


# ============================================================
# CONFIGURATION
# ============================================================

THE_NEWS_API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

NEWS_API_URL = "https://api.thenewsapi.com/v1/news/all"

SOURCE_NAME = "The News API"

REQUEST_TIMEOUT = 30

# عدد المقالات المطلوبة في كل طلب
ARTICLES_PER_QUERY = 10


# ============================================================
# FOOTBALL SEARCH QUERIES
# ============================================================

NEWS_QUERIES = {

    # --------------------------------------------------------
    # Premier League
    # --------------------------------------------------------

    "Premier League":
        '"Premier League" | Arsenal | Liverpool | "Manchester City" | '
        '"Manchester United" | Chelsea | Tottenham | Newcastle',

    # --------------------------------------------------------
    # La Liga
    # --------------------------------------------------------

    "La Liga":
        '"La Liga" | "Real Madrid" | Barcelona | "Atletico Madrid" | '
        'Sevilla | Villarreal',

    # --------------------------------------------------------
    # Serie A
    # --------------------------------------------------------

    "Serie A":
        '"Serie A" | "Inter Milan" | "AC Milan" | Juventus | Napoli | '
        'Roma | Lazio | Atalanta',

    # --------------------------------------------------------
    # Bundesliga
    # --------------------------------------------------------

    "Bundesliga":
        'Bundesliga | "Bayern Munich" | "Borussia Dortmund" | '
        '"Bayer Leverkusen" | "RB Leipzig" | Stuttgart',

    # --------------------------------------------------------
    # Ligue 1
    # --------------------------------------------------------

    "Ligue 1":
        '"Ligue 1" | PSG | "Paris Saint-Germain" | Marseille | Lyon | '
        'Monaco | Lille | Nice',

    # --------------------------------------------------------
    # Champions League
    # --------------------------------------------------------

    "Champions League":
        '"Champions League" | "UEFA Champions League"',

    # --------------------------------------------------------
    # Transfers
    # --------------------------------------------------------

    "Transfers":
        '"football transfer" | "transfer news" | "transfer market" | '
        '"transfer rumour" | "transfer rumours"',
}


# ============================================================
# SUPABASE HEADERS
# ============================================================

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


# ============================================================
# LOAD TEAMS
# ============================================================

def load_teams():

    url = f"{SUPABASE_URL}/rest/v1/teams"

    params = {
        "select": "id,source_team_id,name,short_name,tla"
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            f"Failed to load teams "
            f"{response.status_code}: {response.text}"
        )

    teams = response.json()

    print(f"Teams loaded: {len(teams)}")

    return teams


# ============================================================
# NORMALIZE TEXT
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = text.lower()

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
# BUILD TEAM SEARCH INDEX
# ============================================================

def build_team_index(teams):

    index = []

    for team in teams:

        names = []

        for field in [
            team.get("name"),
            team.get("short_name"),
            team.get("tla")
        ]:

            if field:
                names.append(
                    normalize_text(field)
                )

        index.append({
            "db_id": team.get("id"),
            "source_team_id": team.get("source_team_id"),
            "name": team.get("name"),
            "names": names
        })

    return index


# ============================================================
# FIND TEAM
# ============================================================

def find_team(text, team_index):

    normalized = normalize_text(text)

    if not normalized:
        return None

    for team in team_index:

        for name in team["names"]:

            if not name:
                continue

            if len(name) < 3:
                continue

            if re.search(
                rf"\b{re.escape(name)}\b",
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

    # Transfers
    transfer_words = [
        "transfer",
        "transfers",
        "transfer news",
        "transfer market",
        "transfer rumour",
        "transfer rumours",
        "signing",
        "signs",
        "joins"
    ]

    for word in transfer_words:

        if normalize_text(word) in text:

            return "transfers"

    # Injuries
    injury_words = [
        "injury",
        "injured",
        "injuries",
        "fitness",
        "hamstring",
        "knee injury"
    ]

    for word in injury_words:

        if normalize_text(word) in text:

            return "injury"

    # Manager
    manager_words = [
        "manager",
        "coach",
        "head coach",
        "managerial"
    ]

    for word in manager_words:

        if normalize_text(word) in text:

            return "manager"

    # Fantasy
    fantasy_words = [
        "fantasy",
        "fpl",
        "fantasy premier league"
    ]

    for word in fantasy_words:

        if normalize_text(word) in text:

            return "fantasy"

    # Champions League
    if (
        "champions league" in text
        or "uefa champions league" in text
    ):

        return "champions_league"

    # Otherwise use query
    return query_category.lower().replace(
        " ",
        "_"
    )


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news(query):

    params = {
        "api_token": THE_NEWS_API_KEY,

        "search": query,

        "search_fields": "title,description,keywords",

        "categories": "sports",

        "language": "en",

        "limit": ARTICLES_PER_QUERY,

        "page": 1,

        "sort": "published_at"
    }

    response = requests.get(
        NEWS_API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            f"The News API error "
            f"{response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    return data.get("data", [])


# ============================================================
# CHECK EXISTING ARTICLE
# ============================================================

def article_exists(source_url):

    if not source_url:
        return False

    url = f"{SUPABASE_URL}/rest/v1/news"

    params = {
        "source_url": f"eq.{source_url}",
        "select": "id",
        "limit": 1
    }

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            f"Supabase duplicate check failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return len(response.json()) > 0


# ============================================================
# PARSE DATE
# ============================================================

def parse_published_at(value):

    if not value:
        return None

    try:

        # Example:
        # 2026-08-16T12:30:00Z

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        ).astimezone(
            timezone.utc
        ).isoformat()

    except Exception:

        return None


# ============================================================
# PREPARE ARTICLE
# ============================================================

def prepare_article(
    article,
    query_category,
    team_index
):

    title = (
        article.get("title")
        or ""
    ).strip()

    description = (
        article.get("description")
        or ""
    ).strip()

    url = (
        article.get("url")
        or ""
    ).strip()

    uuid = (
        article.get("uuid")
        or article.get("id")
    )

    if not title or not url:
        return None

    # --------------------------------------------------------
    # Find team
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

        team_id = str(
            team["source_team_id"]
        )

        team_name = team["name"]

    # --------------------------------------------------------
    # Classification
    # --------------------------------------------------------

    category = classify_article(
        title,
        description,
        query_category
    )

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    source_data = article.get(
        "source"
    ) or {}

    source_name = (
        source_data.get("name")
        or SOURCE_NAME
    )

    # --------------------------------------------------------
    # Image
    # --------------------------------------------------------

    image_url = (
        article.get("image_url")
        or article.get("image")
    )

    # --------------------------------------------------------
    # Published
    # --------------------------------------------------------

    published_at = parse_published_at(
        article.get("published_at")
    )

    # --------------------------------------------------------
    # Database record
    # --------------------------------------------------------

    return {

        "source": source_name,

        "source_url": url,

        "source_article_id": (
            str(uuid)
            if uuid
            else None
        ),

        "title_original": title,

        "summary_original": description,

        "image_url": image_url,

        "published_at": published_at,

        "collected_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "category": category,

        "league": (
            query_category
            if query_category
            in [
                "Premier League",
                "La Liga",
                "Serie A",
                "Bundesliga",
                "Ligue 1"
            ]
            else None
        ),

        "team_id": team_id,

        "team_name": team_name,

        "player_name": None,

        "news_type": "EXTERNAL",

        "status": "NEW",

        "telegram_sent": False,

        "facebook_sent": False,

        "ai_processed": False
    }


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(article):

    url = f"{SUPABASE_URL}/rest/v1/news"

    response = requests.post(
        url,
        headers={
            **SUPABASE_HEADERS,
            "Prefer": (
                "resolution=ignore-duplicates,"
                "return=minimal"
            )
        },
        json=article,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code not in [
        200,
        201,
        204
    ]:

        raise Exception(
            f"Supabase news insert failed "
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

    articles = fetch_news(query)

    print(
        f"Articles received: "
        f"{len(articles)}"
    )

    saved = 0
    duplicates = 0
    invalid = 0

    for article in articles:

        source_url = (
            article.get("url")
            or ""
        ).strip()

        if not source_url:

            invalid += 1

            continue

        # ----------------------------------------------------
        # Duplicate
        # ----------------------------------------------------

        if article_exists(
            source_url
        ):

            duplicates += 1

            continue

        # ----------------------------------------------------
        # Prepare
        # ----------------------------------------------------

        record = prepare_article(
            article,
            query_category,
            team_index
        )

        if not record:

            invalid += 1

            continue

        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        save_article(record)

        saved += 1

        print(
            f"✅ Saved: "
            f"{record['title_original']}"
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

    return saved


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("FOOTBALL NEWS COLLECTOR")
    print("=" * 70)

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    if not THE_NEWS_API_KEY:

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

    print(
        "News API : The News API"
    )

    print(
        "Database : Supabase"
    )

    # --------------------------------------------------------
    # Teams
    # --------------------------------------------------------

    teams = load_teams()

    team_index = build_team_index(
        teams
    )

    print(
        f"Team index: "
        f"{len(team_index)}"
    )

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    total_saved = 0

    total_queries = len(
        NEWS_QUERIES
    )

    print(
        f"Queries: {total_queries}"
    )

    for query_category, query in (
        NEWS_QUERIES.items()
    ):

        try:

            saved = process_query(
                query_category,
                query,
                team_index
            )

            total_saved += saved

        except Exception as error:

            print("")

            print(
                f"❌ ERROR in "
                f"{query_category}:"
            )

            print(error)

            print(
                "Continuing..."
            )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"Queries processed : "
        f"{total_queries}"
    )

    print(
        f"Articles saved   : "
        f"{total_saved}"
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
