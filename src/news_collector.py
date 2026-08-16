import os
import re
import requests

from datetime import datetime, timezone


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

API_URL = "https://api.thenewsapi.com/v1/news/all"

TIMEOUT = 30

ARTICLES_PER_QUERY = 3


# ============================================================
# QUERIES
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
# SUPABASE
# ============================================================

def supabase_headers():

    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


# ============================================================
# NORMALIZE
# ============================================================

def normalize(text):

    if not text:
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

    if not isinstance(data, list):

        raise Exception(
            "Invalid teams response"
        )

    print(
        f"Teams loaded: {len(data)}"
    )

    return data


# ============================================================
# TEAM INDEX
# ============================================================

def build_team_index(teams):

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

            value = normalize(value)

            if len(value) >= 3:

                names.append(value)

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
                names,
        })

    return index


# ============================================================
# FIND TEAM
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

    teams = sorted(
        team_index,
        key=lambda x: max(
            (
                len(name)
                for name in x["names"]
            ),
            default=0
        ),
        reverse=True
    )

    for team in teams:

        for name in team["names"]:

            if re.search(
                rf"\b{re.escape(name)}\b",
                text
            ):

                return team

    return None


# ============================================================
# CLASSIFY
# ============================================================

def classify(
    title,
    description,
    query_name
):

    text = normalize(
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
        "signings",
    ]

    for word in transfer_words:

        if normalize(word) in text:

            return "transfers"

    # Injury
    injury_words = [
        "injury",
        "injured",
        "injuries",
        "hamstring",
        "knee injury",
        "ankle injury",
    ]

    for word in injury_words:

        if normalize(word) in text:

            return "injury"

    # Manager
    manager_words = [
        "manager",
        "coach",
        "head coach",
        "sacked",
        "sacking",
    ]

    for word in manager_words:

        if normalize(word) in text:

            return "manager"

    # Fantasy
    fantasy_words = [
        "fantasy",
        "fpl",
        "fantasy premier league",
    ]

    for word in fantasy_words:

        if normalize(word) in text:

            return "fantasy"

    # Champions League
    if (
        "champions league" in text
        or
        "uefa champions league" in text
    ):

        return "champions_league"

    return (
        query_name
        .lower()
        .replace(" ", "_")
    )


# ============================================================
# SOURCE
# ============================================================

def get_source(article):

    source = article.get(
        "source"
    )

    if isinstance(
        source,
        str
    ):

        return (
            source.strip()
            or "The News API"
        )

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
# IMAGE
# ============================================================

def get_image(article):

    value = (
        article.get("image_url")
        or article.get("image")
    )

    if not value:
        return None

    return str(value).strip()


# ============================================================
# API REQUEST
# ============================================================

def fetch_news(
    query_name,
    query
):

    print(
        f"Search: {query}"
    )

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
            response.text[:1000]
        )

        return []

    try:

        data = response.json()

    except Exception:

        print(
            "❌ Invalid JSON"
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
# DUPLICATE
# ============================================================

def article_exists(
    source_url
):

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
            "⚠️ Duplicate check failed"
        )

        return False

    data = response.json()

    return (
        isinstance(data, list)
        and len(data) > 0
    )


# ============================================================
# PREPARE
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

        return None

    title = (
        article.get("title")
        or ""
    ).strip()

    description = (
        article.get("description")
        or article.get("snippet")
        or ""
    ).strip()

    url = (
        article.get("url")
        or ""
    ).strip()

    if not title or not url:

        return None

    team = find_team(
        title,
        description,
        team_index
    )

    team_id = None
    team_name = None

    if team:

        if team.get(
            "source_team_id"
        ) is not None:

            team_id = str(
                team[
                    "source_team_id"
                ]
            )

        team_name = team.get(
            "name"
        )

    league = None

    if query_name in [
        "Premier League",
        "La Liga",
        "Serie A",
        "Bundesliga",
        "Ligue 1",
        "Champions League",
    ]:

        league = query_name

    published_at = (
        article.get(
            "published_at"
        )
    )

    return {

        "news_type":
            "EXTERNAL",

        "title": title,
        
        "content": description, 
        
        "source":
            get_source(article),

        "source_url":
            url,

        "source_article_id":
            str(
                article.get(
                    "uuid"
                )
                or article.get(
                    "id"
                )
                or ""
            ),

        "title_original":
            title,

        "summary_original":
            description,

        "title_ar":
            None,

        "summary_ar":
            None,

        "image_url":
            get_image(article),

        "category":
            classify(
                title,
                description,
                query_name
            ),

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

        "facebook_sent":
            False,

        "ai_processed":
            False,
    }


# ============================================================
# SAVE
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
        response.text[:1000]
    )

    return False


# ============================================================
# PROCESS
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
    invalid = 0

    for article in articles:

        try:

            record = prepare_article(
                article,
                query_name,
                team_index
            )

            if not record:

                invalid += 1

                continue

            if article_exists(
                record[
                    "source_url"
                ]
            ):

                duplicates += 1

                print(
                    "⏭️ Duplicate:"
                    f" {record['title_original']}"
                )

                continue

            if save_article(
                record
            ):

                saved += 1

                print(
                    "✅ Saved:"
                    f" {record['title_original']}"
                )

                print(
                    "   Source:"
                    f" {record['source']}"
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
                f"❌ Article error: "
                f"{error}"
            )

    return {
        "received":
            len(articles),

        "saved":
            saved,

        "duplicates":
            duplicates,

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

    print("=" * 70)

    # --------------------------------------------------------
    # ENV
    # --------------------------------------------------------

    if not API_KEY:

        raise Exception(
            "THE_NEWS_API_KEY is missing"
        )

    if not SUPABASE_URL:

        raise Exception(
            "SUPABASE_URL is missing"
        )

    if not SUPABASE_KEY:

        raise Exception(
            "SUPABASE_KEY is missing"
        )

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    total_received = 0
    total_saved = 0
    total_duplicates = 0
    total_invalid = 0

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

        total_invalid += (
            result["invalid"]
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

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
