import os
import re
import requests

from datetime import datetime, timezone, timedelta


# ============================================================
# CONFIGURATION
# ============================================================

THE_NEWS_API_KEY = os.getenv("THE_NEWS_API_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

NEWS_API_URL = "https://www.thenewsapi.com/v1/news/all"

REQUEST_TIMEOUT = 30

# عدد الأخبار من كل طلب
ARTICLES_PER_QUERY = 10

# جلب الأخبار المنشورة خلال آخر 48 ساعة
LOOKBACK_HOURS = 48


# ============================================================
# BASIC QUERIES
# ============================================================

# نبدأ باستعلامات بسيطة ومستقرة.
# بعد نجاح النظام سنضيف استعلامات الأندية بشكل منفصل.

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
# TEXT NORMALIZATION
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
        headers=supabase_headers(),
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        raise Exception(
            "Failed to load teams "
            f"{response.status_code}: "
            f"{response.text}"
        )

    teams = response.json()

    if not isinstance(teams, list):

        raise Exception(
            "Invalid teams response."
        )

    print(
        f"Teams loaded: {len(teams)}"
    )

    return teams


# ============================================================
# BUILD TEAM INDEX
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

            normalized = normalize_text(
                value
            )

            if len(normalized) >= 3:

                names.append(
                    normalized
                )

        if not names:
            continue

        index.append({

            "db_id":
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

    text = normalize_text(
        f"{title} {description}"
    )

    if not text:
        return None

    # الأسماء الأطول أولًا
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
# CLASSIFICATION
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
        "signings",
        "joins",
        "joined",
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
        "hamstring",
        "knee injury",
        "ankle injury",
        "fitness",
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
        "sacked",
        "sacking",
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
    # LEAGUE
    # --------------------------------------------------------

    return (
        query_category
        .lower()
        .replace(" ", "_")
    )


# ============================================================
# DATE
# ============================================================

def parse_date(value):

    if not value:
        return None

    try:

        value = str(value)

        if value.endswith("Z"):

            value = (
                value[:-1]
                + "+00:00"
            )

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
# GET SOURCE
# ============================================================

def get_source(article):

    source = article.get(
        "source"
    )

    # API قد تعيد source كنص
    if isinstance(
        source,
        str
    ):

        return (
            source.strip()
            or "The News API"
        )

    # احتياطًا لو رجع Object
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

def get_image(article):

    image = (
        article.get("image_url")
        or article.get("image")
        or article.get("imageUrl")
    )

    if not image:
        return None

    return str(
        image
    ).strip()


# ============================================================
# FETCH NEWS
# ============================================================

def fetch_news(
    query
):

    now = datetime.now(
        timezone.utc
    )

    published_after = (
        now
        - timedelta(
            hours=LOOKBACK_HOURS
        )
    ).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

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

        "published_after":
            published_after,

        "sort":
            "published_at",
    }

    response = requests.get(
        NEWS_API_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    # --------------------------------------------------------
    # ERROR HANDLING
    # --------------------------------------------------------

    if response.status_code != 200:

        print(
            f"HTTP {response.status_code}"
        )

        print(
            response.text[:1000]
        )

        return []

    try:

        data = response.json()

    except Exception:

        print(
            "❌ API returned invalid JSON."
        )

        return []

    if not isinstance(
        data,
        dict
    ):

        print(
            "❌ Invalid API response."
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
        timeout=REQUEST_TIMEOUT
    )

    if response.status_code != 200:

        print(
            "❌ Duplicate check failed:"
        )

        print(
            response.text[:500]
        )

        return False

    data = response.json()

    return (
        isinstance(data, list)
        and len(data) > 0
    )


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
    # TITLE
    # --------------------------------------------------------

    title = (
        article.get("title")
        or ""
    ).strip()

    # --------------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------------

    description = (
        article.get("description")
        or article.get("snippet")
        or ""
    ).strip()

    # --------------------------------------------------------
    # URL
    # --------------------------------------------------------

    source_url = (
        article.get("url")
        or ""
    ).strip()

    if not title:
        return None

    if not source_url:
        return None

    # --------------------------------------------------------
    # ARTICLE ID
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
    # TEAM
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CATEGORY
    # --------------------------------------------------------

    category = classify_article(
        title,
        description,
        query_category
    )

    # --------------------------------------------------------
    # LEAGUE
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
    # RETURN RECORD
    # --------------------------------------------------------

    return {

        "news_type":
            "EXTERNAL",

        "source":
            get_source(article),

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
            get_image(article),

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
            parse_date(
                article.get(
                    "published_at"
                )
            ),

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

def save_article(
    article
):

    url = (
        f"{SUPABASE_URL}/rest/v1/news"
    )

    headers = {
        **supabase_headers(),

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

    if response.status_code in [
        200,
        201,
        204,
    ]:

        return True

    # في حالة Unique Constraint
    if response.status_code == 409:

        return False

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

    articles = fetch_news(
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
            # DUPLICATE
            # ------------------------------------------------

            if article_exists(
                source_url
            ):

                duplicates += 1

                print(
                    "⏭️ Duplicate: "
                    f"{article.get('title', '')}"
                )

                continue

            # ------------------------------------------------
            # PREPARE
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
            # SAVE
            # ------------------------------------------------

            was_saved = save_article(
                record
            )

            if not was_saved:

                duplicates += 1

                print(
                    "⏭️ Already exists: "
                    f"{record['title_original']}"
                )

                continue

            saved += 1

            print(
                "✅ Saved: "
                f"{record['title_original']}"
            )

            print(
                "   Source: "
                f"{record['source']}"
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
                "❌ Article error: "
                f"{error}"
            )

    print("")
    print(
        f"Received   : "
        f"{len(articles)}"
    )

    print(
        f"Saved      : "
        f"{saved}"
    )

    print(
        f"Duplicates : "
        f"{duplicates}"
    )

    print(
        f"Invalid    : "
        f"{invalid}"
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
        f"Lookback: "
        f"{LOOKBACK_HOURS} hours"
    )

    print("=" * 70)

    # ========================================================
    # ENVIRONMENT
    # ========================================================

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
    # PROCESS QUERIES
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
