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

ARTICLES_PER_QUERY = 5

API_LOOKBACK_HOURS = 48
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
# LEAGUES
# ============================================================

LEAGUE_NAMES = {
    "Premier League": "Premier League",
    "La Liga": "La Liga",
    "Serie A": "Serie A",
    "Bundesliga": "Bundesliga",
    "Ligue 1": "Ligue 1",
    "Champions League": "Champions League",
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
    "football club",
    "football team",
]


# ============================================================
# AMERICAN FOOTBALL / NON-SOCCER
# ============================================================

NON_SOCCER_KEYWORDS = [
    "nfl",
    "ncaa",
    "college football",
    "american football",
    "touchdown",
    "quarterback",
    "qb",
    "running back",
    "wide receiver",
    "tight end",
    "linebacker",
    "defensive tackle",
    "offensive line",
    "rushing yards",
    "passing yards",
    "receiving yards",
    "field goal",
    "super bowl",
    "draft pick",
    "nfl draft",
    "college football transfer",
    "transfer portal",
    "de'von achane",
    "mcmillan",
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
    "loan",
    "loan deal",
    "free agent",
    "medical",
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
    "setback",
    "injury update",
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
    "managerial",
]


# ============================================================
# MATCH KEYWORDS
# ============================================================

MATCH_KEYWORDS = [
    "match",
    "fixture",
    "fixtures",
    "kickoff",
    "kick-off",
    "starting xi",
    "starting lineup",
    "lineup",
    "line-up",
    "live",
    "match report",
    "preview",
    "result",
    "win",
    "draw",
    "defeat",
    "goal",
    "goals",
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
# NORMALIZE
# ============================================================

def normalize(text):

    if text is None:
        return ""

    text = str(text).lower()

    replacements = {
        "&": " and ",
        "’": "'",
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(
        r"[^a-z0-9\s'-]",
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
# DATE PARSER
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
# RECENT ARTICLE
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
# KEYWORD MATCH
# ============================================================

def contains_keyword(
    text,
    keywords
):

    normalized_text = normalize(text)

    for keyword in keywords:

        keyword_normalized = normalize(
            keyword
        )

        if not keyword_normalized:
            continue

        if keyword_normalized in normalized_text:
            return True

    return False


# ============================================================
# NON SOCCER FILTER
# ============================================================

def is_non_soccer(
    title,
    description,
    keywords
):

    text = (
        f"{title} "
        f"{description} "
        f"{keywords}"
    )

    return contains_keyword(
        text,
        NON_SOCCER_KEYWORDS
    )


# ============================================================
# FOOTBALL FILTER
# ============================================================

def is_football_article(
    title,
    description,
    keywords="",
    categories=None
):

    text = (
        f"{title} "
        f"{description} "
        f"{keywords}"
    )

    # First reject American Football.
    if is_non_soccer(
        title,
        description,
        keywords
    ):
        return False

    normalized_text = normalize(
        text
    )

    if any(
        normalize(keyword) in normalized_text
        for keyword in FOOTBALL_KEYWORDS
    ):
        return True

    if isinstance(
        categories,
        list
    ):

        normalized_categories = [
            normalize(x)
            for x in categories
            if x
        ]

        if "sports" in normalized_categories:

            # Sports alone is NOT enough.
            # Require some soccer signal.
            soccer_signals = [
                "fc",
                "afc",
                "cf",
                "sc",
                "united",
                "city",
                "real madrid",
                "barcelona",
                "arsenal",
                "chelsea",
                "liverpool",
                "bayern",
                "juventus",
                "milan",
                "inter",
                "psg",
            ]

            for signal in soccer_signals:

                if normalize(signal) in normalized_text:
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
            "tla,"
            "league"
        )
    }

    response = requests.get(
        url,
        headers=supabase_headers(),
        params=params,
        timeout=TIMEOUT
    )

    # --------------------------------------------------------
    # Fallback if league column does not exist.
    # --------------------------------------------------------

    if response.status_code != 200:

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

            "league":
                team.get("league"),

            "names":
                list(
                    dict.fromkeys(
                        names
                    )
                ),
        })

    return index


# ============================================================
# TEAM FINDER
# ============================================================

def find_teams(
    title,
    description,
    keywords,
    team_index
):

    text = normalize(
        f"{title} {description} {keywords}"
    )

    found = []

    # Longest names first.
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

            if len(name) <= 3:
                pattern = (
                    rf"\b{re.escape(name)}\b"
                )

                if not re.search(
                    pattern,
                    text
                ):
                    continue

            else:

                if name not in text:
                    continue

            found.append(
                team
            )

            break

    return found


# ============================================================
# GET TEAM LEAGUE
# ============================================================

def get_team_league(
    team
):

    if not team:
        return None

    league = team.get(
        "league"
    )

    if league:
        return league

    return None


# ============================================================
# LEAGUE ALIASES
# ============================================================

LEAGUE_ALIASES = {

    "Premier League": [
        "premier league",
        "english premier league",
    ],

    "La Liga": [
        "la liga",
        "laliga",
        "spanish la liga",
        "spanish league",
    ],

    "Serie A": [
        "serie a",
        "italian serie a",
        "italian league",
    ],

    "Bundesliga": [
        "bundesliga",
        "german bundesliga",
        "german league",
    ],

    "Ligue 1": [
        "ligue 1",
        "ligue1",
        "french ligue 1",
        "french league",
    ],

    "Champions League": [
        "champions league",
        "uefa champions league",
    ],
}


# ============================================================
# DETECT EXPLICIT LEAGUE
# ============================================================

def detect_explicit_leagues(
    text
):

    normalized_text = normalize(
        text
    )

    found = []

    for league, aliases in (
        LEAGUE_ALIASES.items()
    ):

        for alias in aliases:

            if normalize(alias) in normalized_text:

                found.append(
                    league
                )

                break

    return found


# ============================================================
# DETERMINE LEAGUE
# ============================================================

def determine_league(
    query_name,
    title,
    description,
    keywords,
    found_teams
):

    text = (
        f"{title} "
        f"{description} "
        f"{keywords}"
    )

    explicit_leagues = (
        detect_explicit_leagues(
            text
        )
    )

    # --------------------------------------------------------
    # Champions League
    # --------------------------------------------------------

    if (
        query_name
        == "Champions League"
    ):

        if (
            "Champions League"
            in explicit_leagues
        ):
            return (
                "Champions League"
            )

        # A Champions League query must
        # contain a Champions League signal.
        return None


    # --------------------------------------------------------
    # Transfers
    # --------------------------------------------------------

    if query_name == "Transfers":

        if explicit_leagues:

            # Prefer actual league mention.
            for league in [
                "Premier League",
                "La Liga",
                "Serie A",
                "Bundesliga",
                "Ligue 1",
            ]:

                if league in explicit_leagues:
                    return league

        # Try team league.
        for team in found_teams:

            league = get_team_league(
                team
            )

            if league:
                return league

        return None


    # --------------------------------------------------------
    # League query
    # --------------------------------------------------------

    requested_league = (
        LEAGUE_NAMES.get(
            query_name
        )
    )

    if not requested_league:
        return None


    # --------------------------------------------------------
    # Explicit league match
    # --------------------------------------------------------

    if requested_league in (
        explicit_leagues
    ):
        return requested_league


    # --------------------------------------------------------
    # Team based validation
    # --------------------------------------------------------

    for team in found_teams:

        team_league = get_team_league(
            team
        )

        if not team_league:
            continue

        if normalize(
            team_league
        ) == normalize(
            requested_league
        ):
            return requested_league

        # Explicitly reject team from another league.
        return None


    # --------------------------------------------------------
    # No league and no known team:
    # For a league query, reject it.
    # --------------------------------------------------------

    return None


# ============================================================
# DETECT CATEGORY
# ============================================================

def classify_article(
    title,
    description,
    keywords,
    query_name
):

    text = (
        f"{title} "
        f"{description} "
        f"{keywords}"
    )

    normalized = normalize(
        text
    )

    # Transfers first.
    for keyword in TRANSFER_KEYWORDS:

        if normalize(keyword) in normalized:
            return "transfers"


    # Injuries.
    for keyword in INJURY_KEYWORDS:

        if normalize(keyword) in normalized:
            return "injury"


    # Managers.
    for keyword in MANAGER_KEYWORDS:

        if normalize(keyword) in normalized:
            return "manager"


    # Champions League.
    if (
        "champions league"
        in normalized
    ):
        return "champions_league"


    # Match.
    for keyword in MATCH_KEYWORDS:

        if normalize(keyword) in normalized:
            return "match"


    # League query fallback.
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
# SOURCE
# ============================================================

def get_source(
    article
):

    source = article.get(
        "source"
    )

    if isinstance(
        source,
        str
    ):

        source = source.strip()

        if source:
            return source

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

        return []

    if not isinstance(
        data,
        dict
    ):

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
    # UUID / source article ID
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
                isinstance(
                    data,
                    list
                )
                and len(data) > 0
            ):
                return True


    # --------------------------------------------------------
    # URL
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
                isinstance(
                    data,
                    list
                )
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
    # DATA
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
    # REQUIRED
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
    # NON SOCCER
    # ========================================================

    if is_non_soccer(
        title,
        description,
        keywords
    ):

        return None, "non_soccer"


    # ========================================================
    # FOOTBALL
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

    found_teams = find_teams(
        title,
        description,
        keywords,
        team_index
    )


    # ========================================================
    # LEAGUE VALIDATION
    # ========================================================

    league = determine_league(
        query_name,
        title,
        description,
        keywords,
        found_teams
    )

    if league is None:

        return None, "wrong_league"


    # ========================================================
    # MAIN TEAM
    # ========================================================

    team = None

    if found_teams:

        # Prefer a team that belongs to
        # the determined league.

        for candidate in found_teams:

            candidate_league = (
                get_team_league(
                    candidate
                )
            )

            if (
                candidate_league
                and normalize(
                    candidate_league
                )
                == normalize(
                    league
                )
            ):

                team = candidate

                break

        if team is None:

            team = found_teams[0]


    # ========================================================
    # TEAM DATA
    # ========================================================

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
    # COLLECTED
    # ========================================================

    collected_at = datetime.now(
        timezone.utc
    ).isoformat()


    # ========================================================
    # RECORD
    # ========================================================

    record = {

        # Required fields
        "title":
            title,

        "content":
            content,

        # News type
        "news_type":
            "EXTERNAL",

        # DO NOT set match_id.
        # General news is not tied
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
# SAVE
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

    if response.status_code in (
        200,
        201,
        204,
    ):

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
    print(
        "-" * 70
    )

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
    not_football = 0
    non_soccer = 0
    wrong_league = 0
    invalid = 0


    for article in articles:

        try:

            record, status = (
                prepare_article(
                    article,
                    query_name,
                    team_index
                )
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
            # NON SOCCER
            # ------------------------------------------------

            if status == "non_soccer":

                non_soccer += 1

                print(
                    "⛔ Non-soccer: "
                    f"{article.get('title', '')}"
                )

                continue


            # ------------------------------------------------
            # NOT FOOTBALL
            # ------------------------------------------------

            if status == "not_football":

                not_football += 1

                print(
                    "⛔ Not football: "
                    f"{article.get('title', '')}"
                )

                continue


            # ------------------------------------------------
            # WRONG LEAGUE
            # ------------------------------------------------

            if status == "wrong_league":

                wrong_league += 1

                print(
                    "⛔ Wrong league: "
                    f"{article.get('title', '')}"
                )

                continue


            # ------------------------------------------------
            # INVALID
            # ------------------------------------------------

            if status != "ok":

                invalid += 1

                print(
                    "⛔ Invalid: "
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
                    f"{record['league']}"
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
        f"Non-soccer     : {non_soccer}"
    )

    print(
        f"Not football   : {not_football}"
    )

    print(
        f"Wrong league   : {wrong_league}"
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

        "non_soccer":
            non_soccer,

        "not_football":
            not_football,

        "wrong_league":
            wrong_league,

        "invalid":
            invalid,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "=" * 70
    )

    print(
        "FOOTBALL NEWS COLLECTOR"
    )

    print(
        "=" * 70
    )

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
        f"Max article age: "
        f"{MAX_ARTICLE_AGE_HOURS} hours"
    )

    print(
        "=" * 70
    )


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
    # TEAMS
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
    total_non_soccer = 0
    total_not_football = 0
    total_wrong_league = 0
    total_invalid = 0


    # ========================================================
    # RUN QUERIES
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

        total_non_soccer += (
            result["non_soccer"]
        )

        total_not_football += (
            result["not_football"]
        )

        total_wrong_league += (
            result["wrong_league"]
        )

        total_invalid += (
            result["invalid"]
        )


    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("")
    print(
        "=" * 70
    )

    print(
        "FINAL SUMMARY"
    )

    print(
        "=" * 70
    )

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
        f"Non-soccer        : "
        f"{total_non_soccer}"
    )

    print(
        f"Not football      : "
        f"{total_not_football}"
    )

    print(
        f"Wrong league      : "
        f"{total_wrong_league}"
    )

    print(
        f"Invalid           : "
        f"{total_invalid}"
    )

    print(
        "Status            : SUCCESS"
    )

    print(
        "=" * 70
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
