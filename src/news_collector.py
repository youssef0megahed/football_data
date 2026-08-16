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

# ------------------------------------------------------------
# Number of articles requested from The News API per query.
# We fetch 20 and then score/filter them locally.
# ------------------------------------------------------------

ARTICLES_PER_QUERY = 20

# ------------------------------------------------------------
# API lookback and local maximum age.
# ------------------------------------------------------------

API_LOOKBACK_HOURS = 48
MAX_ARTICLE_AGE_HOURS = 48

# ------------------------------------------------------------
# Minimum score required to save an article.
# ------------------------------------------------------------

MIN_SCORE = 35


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
    "Transfers": 'football transfer',
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
# FOOTBALL SIGNALS
# ============================================================

FOOTBALL_KEYWORDS = [
    "football",
    "soccer",
    "premier league",
    "la liga",
    "laliga",
    "serie a",
    "bundesliga",
    "ligue 1",
    "ligue1",
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
    "football player",
    "soccer player",
    "football club",
    "football team",
    "football manager",
    "head coach",
    "starting xi",
    "starting lineup",
    "lineup",
    "matchday",
]


# ============================================================
# EUROPEAN FOOTBALL SIGNALS
# ============================================================

EUROPEAN_FOOTBALL_KEYWORDS = [
    "fc",
    "afc",
    "cf",
    "sc",
    "real madrid",
    "barcelona",
    "atletico madrid",
    "sevilla",
    "valencia",
    "villarreal",
    "athletic bilbao",
    "arsenal",
    "chelsea",
    "liverpool",
    "manchester united",
    "manchester city",
    "tottenham",
    "newcastle",
    "aston villa",
    "west ham",
    "everton",
    "brighton",
    "nottingham forest",
    "bayern munich",
    "bayern",
    "borussia dortmund",
    "rb leipzig",
    "bayer leverkusen",
    "juventus",
    "ac milan",
    "inter milan",
    "inter",
    "napoli",
    "roma",
    "lazio",
    "atalanta",
    "psg",
    "paris saint-germain",
    "marseille",
    "monaco",
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
    "nfl draft",
    "college football transfer",
    "transfer portal",
    "college transfer portal",
    "de'von achane",
    "devon achane",
    "mcmillan",
    "big ten",
    "college rankings",
    "ncaa football",
]


# ============================================================
# FANTASY FOOTBALL FILTER
# ============================================================

FANTASY_NON_SOCCER_KEYWORDS = [
    "fantasy football rankings",
    "fantasy football ranking",
    "fantasy football sleeper",
    "fantasy football sleepers",
    "fantasy football breakout",
    "fantasy football breakouts",
    "fantasy football draft",
    "fantasy football waiver",
    "fantasy football waivers",
    "fantasy points",
    "fantasy lineup",
    "fantasy rankings",
    "draftkings",
    "fanduel",
    "daily fantasy",
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
    "agreed deal",
    "agreement",
    "loan",
    "loan deal",
    "loan move",
    "free agent",
    "medical",
    "release clause",
    "buyout clause",
    "bid",
    "bids",
    "offer",
    "offers",
    "swap deal",
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
    "muscle injury",
    "fitness",
    "sidelined",
    "ruled out",
    "setback",
    "injury update",
    "return from injury",
    "medical update",
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
    "appointment",
    "new manager",
    "managerial",
    "takes charge",
    "in charge",
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
    "starting line-up",
    "lineup",
    "line-up",
    "live",
    "match report",
    "preview",
    "result",
    "results",
    "win",
    "draw",
    "defeat",
    "goal",
    "goals",
    "scored",
    "equaliser",
    "equalizer",
    "full time",
    "half time",
]


# ============================================================
# HIGH QUALITY SOURCES
# ============================================================

PREMIUM_SOURCES = [
    "bbc.co.uk",
    "bbc.com",
    "skysports.com",
    "theguardian.com",
    "espn.com",
    "reuters.com",
    "apnews.com",
    "theathletic.com",
    "goal.com",
    "fourfourtwo.com",
    "90min.com",
    "football365.com",
    "espn.co.uk",
    "uefa.com",
    "fifa.com",
    "premierleague.com",
    "laliga.com",
    "bundesliga.com",
    "ligue1.com",
    "legaseriea.it",
]


# ============================================================
# LEAGUE ALIASES
# ============================================================

LEAGUE_ALIASES = {

    "Premier League": [
        "premier league",
        "english premier league",
        "epl",
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
        "‘": "'",
        "–": "-",
        "—": "-",
        "é": "e",
        "á": "a",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
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

def is_recent_article(published_at):

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

    normalized_text = normalize(
        text
    )

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
# COUNT KEYWORDS
# ============================================================

def count_keywords(
    text,
    keywords
):

    normalized_text = normalize(
        text
    )

    count = 0

    for keyword in keywords:

        keyword_normalized = normalize(
            keyword
        )

        if (
            keyword_normalized
            and keyword_normalized in normalized_text
        ):
            count += 1

    return count


# ============================================================
# NON-SOCCER FILTER
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

    normalized_text = normalize(
        text
    )

    # Strong American football signals.
    strong_signals = [
        "nfl",
        "ncaa",
        "american football",
        "touchdown",
        "quarterback",
        "super bowl",
        "running back",
        "wide receiver",
        "tight end",
        "linebacker",
        "transfer portal",
        "college football",
    ]

    for keyword in strong_signals:

        if normalize(keyword) in normalized_text:
            return True

    # Fantasy American Football.
    for keyword in FANTASY_NON_SOCCER_KEYWORDS:

        if normalize(keyword) in normalized_text:

            # If the article also clearly discusses
            # European football, don't automatically reject.
            european_signal = contains_keyword(
                normalized_text,
                [
                    "premier league",
                    "la liga",
                    "serie a",
                    "bundesliga",
                    "ligue 1",
                    "champions league",
                    "uefa",
                ]
            )

            if not european_signal:
                return True

    return False


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

    if is_non_soccer(
        title,
        description,
        keywords
    ):
        return False

    normalized_text = normalize(
        text
    )

    # Direct football signals.
    for keyword in FOOTBALL_KEYWORDS:

        if normalize(keyword) in normalized_text:
            return True

    # European club signal.
    for keyword in EUROPEAN_FOOTBALL_KEYWORDS:

        if normalize(keyword) in normalized_text:
            return True

    # Categories are only supplementary evidence.
    if isinstance(
        categories,
        list
    ):

        normalized_categories = [
            normalize(x)
            for x in categories
            if x
        ]

        if (
            "sports"
            in normalized_categories
        ):

            soccer_signals = [
                "fc",
                "afc",
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

def get_team_league(team):

    if not team:
        return None

    return team.get(
        "league"
    )


# ============================================================
# DETECT EXPLICIT LEAGUES
# ============================================================

def detect_explicit_leagues(text):

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

    if query_name == "Champions League":

        if (
            "Champions League"
            in explicit_leagues
        ):
            return "Champions League"

        return None


    # --------------------------------------------------------
    # Transfers
    # --------------------------------------------------------

    if query_name == "Transfers":

        if explicit_leagues:

            for league in [
                "Premier League",
                "La Liga",
                "Serie A",
                "Bundesliga",
                "Ligue 1",
            ]:

                if league in explicit_leagues:

                    return league

        # Team-based fallback.
        for team in found_teams:

            league = get_team_league(
                team
            )

            if league:
                return league

        # General transfer news is allowed.
        return None


    # --------------------------------------------------------
    # League Query
    # --------------------------------------------------------

    requested_league = (
        LEAGUE_NAMES.get(
            query_name
        )
    )

    if not requested_league:
        return None


    # Explicit league.
    if requested_league in explicit_leagues:

        # Important:
        # If another league is explicitly mentioned
        # and requested league isn't dominant, reject.
        other_leagues = [
            x
            for x in explicit_leagues
            if x != requested_league
        ]

        if other_leagues:

            # Keep it only if requested league
            # appears in the title.
            title_leagues = detect_explicit_leagues(
                title
            )

            if requested_league not in title_leagues:
                return None

        return requested_league


    # Team-based validation.
    matching_team = False

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

            matching_team = True
            break

    if matching_team:
        return requested_league


    # If no league/team evidence, reject.
    return None


# ============================================================
# CLASSIFY ARTICLE
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

    # --------------------------------------------------------
    # Transfers
    # --------------------------------------------------------

    transfer_count = count_keywords(
        normalized,
        TRANSFER_KEYWORDS
    )

    if transfer_count > 0:
        return "transfers"


    # --------------------------------------------------------
    # Injuries
    # --------------------------------------------------------

    injury_count = count_keywords(
        normalized,
        INJURY_KEYWORDS
    )

    if injury_count > 0:
        return "injury"


    # --------------------------------------------------------
    # Managers
    # --------------------------------------------------------

    manager_count = count_keywords(
        normalized,
        MANAGER_KEYWORDS
    )

    if manager_count > 0:
        return "manager"


    # --------------------------------------------------------
    # Champions League
    # --------------------------------------------------------

    if "champions league" in normalized:

        return "champions_league"


    # --------------------------------------------------------
    # Match
    # --------------------------------------------------------

    match_count = count_keywords(
        normalized,
        MATCH_KEYWORDS
    )

    if match_count > 0:
        return "match"


    # --------------------------------------------------------
    # League category
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
# SCORE ARTICLE
# ============================================================

def score_article(
    article,
    query_name,
    league,
    found_teams
):

    title = (
        article.get("title")
        or ""
    )

    description = (
        article.get("description")
        or article.get("snippet")
        or ""
    )

    keywords = (
        article.get("keywords")
        or ""
    )

    source = normalize(
        article.get("source")
        or ""
    )

    text = normalize(
        f"{title} {description} {keywords}"
    )

    score = 0
    reasons = []


    # ========================================================
    # FRESHNESS
    # ========================================================

    published_at = article.get(
        "published_at"
    )

    article_date = parse_article_date(
        published_at
    )

    if article_date:

        age_hours = (
            datetime.now(
                timezone.utc
            )
            - article_date
        ).total_seconds() / 3600

        if age_hours <= 3:

            score += 30
            reasons.append(
                "very_recent"
            )

        elif age_hours <= 6:

            score += 25
            reasons.append(
                "recent"
            )

        elif age_hours <= 12:

            score += 20
            reasons.append(
                "recent"
            )

        elif age_hours <= 24:

            score += 15

        elif age_hours <= 48:

            score += 8


    # ========================================================
    # SOURCE QUALITY
    # ========================================================

    source_bonus = False

    for premium_source in PREMIUM_SOURCES:

        if premium_source in source:

            score += 15

            reasons.append(
                "trusted_source"
            )

            source_bonus = True

            break

    if not source_bonus:
        score += 3


    # ========================================================
    # QUERY RELEVANCE
    # ========================================================

    normalized_query = normalize(
        query_name
    )

    if (
        normalized_query
        and normalized_query in text
    ):

        score += 15

        reasons.append(
            "query_match"
        )


    # ========================================================
    # FOOTBALL SIGNAL
    # ========================================================

    football_count = count_keywords(
        text,
        FOOTBALL_KEYWORDS
    )

    if football_count >= 3:

        score += 15

        reasons.append(
            "strong_football_signal"
        )

    elif football_count >= 1:

        score += 8

        reasons.append(
            "football_signal"
        )


    # ========================================================
    # EUROPEAN FOOTBALL
    # ========================================================

    european_count = count_keywords(
        text,
        EUROPEAN_FOOTBALL_KEYWORDS
    )

    if european_count >= 2:

        score += 10

        reasons.append(
            "european_football"
        )

    elif european_count == 1:

        score += 5


    # ========================================================
    # LEAGUE SIGNAL
    # ========================================================

    if league:

        aliases = (
            LEAGUE_ALIASES.get(
                league,
                []
            )
        )

        if any(
            normalize(alias) in text
            for alias in aliases
        ):

            score += 10

            reasons.append(
                "league_match"
            )


    # ========================================================
    # TEAM SIGNAL
    # ========================================================

    if found_teams:

        score += min(
            len(found_teams) * 5,
            15
        )

        reasons.append(
            "team_detected"
        )


    # ========================================================
    # ARTICLE HAS DESCRIPTION
    # ========================================================

    if len(description) >= 100:

        score += 5

        reasons.append(
            "good_description"
        )

    elif len(description) >= 40:

        score += 2


    # ========================================================
    # ARTICLE RELEVANCE SCORE FROM API
    # ========================================================

    api_score = article.get(
        "relevance_score"
    )

    try:

        api_score = float(
            api_score
        )

        if api_score >= 30:

            score += 5

            reasons.append(
                "api_relevance"
            )

        elif api_score >= 20:

            score += 3

    except Exception:
        pass


    # ========================================================
    # CLICKBAIT / LOW QUALITY PENALTIES
    # ========================================================

    low_quality_patterns = [
        "watch live",
        "how to watch",
        "where to watch",
        "live streaming",
        "dream11",
        "probable playing xi",
        "when and where to watch",
    ]

    low_quality_hits = 0

    for pattern in low_quality_patterns:

        if normalize(pattern) in text:
            low_quality_hits += 1

    if low_quality_hits >= 2:

        score -= 12

        reasons.append(
            "low_quality_watch_article"
        )

    elif low_quality_hits == 1:

        score -= 5


    # ========================================================
    # OLD HISTORICAL CONTENT SIGNAL
    # ========================================================

    historical_patterns = [
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
        "career stats",
        "how many",
        "all time",
        "history of",
        "greatest ever",
    ]

    historical_hits = 0

    for pattern in historical_patterns:

        if normalize(pattern) in text:
            historical_hits += 1

    if historical_hits >= 2:

        score -= 15

        reasons.append(
            "historical_content"
        )


    # ========================================================
    # CAP
    # ========================================================

    score = max(
        0,
        min(
            int(score),
            100
        )
    )

    return score, reasons


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

def get_image(article):

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
    # NON-SOCCER
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
    # LEAGUE
    # ========================================================

    league = determine_league(
        query_name,
        title,
        description,
        keywords,
        found_teams
    )

    # Transfers can be general football.
    if (
        query_name != "Transfers"
        and league is None
    ):
        return None, "wrong_league"


    # ========================================================
    # MAIN TEAM
    # ========================================================

    team = None

    if found_teams:

        # Prefer a team matching the league.
        if league:

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
    # SCORE
    # ========================================================

    score, score_reasons = score_article(
        article,
        query_name,
        league,
        found_teams
    )

    if score < MIN_SCORE:

        return None, "low_score"


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

        # ----------------------------------------------------
        # IMPORTANT:
        # match_id is intentionally omitted.
        #
        # General external news is not associated with a
        # specific match.
        #
        # The news.match_id column must therefore allow NULL.
        # ----------------------------------------------------

        "title":
            title,

        "content":
            content,

        "news_type":
            "EXTERNAL",

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

        # Score
        "relevance_score":
            score,
    }

    return {
        "record": record,
        "score": score,
        "reasons": score_reasons,
    }, "ok"


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_article(record):

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


    # ========================================================
    # FIRST PASS
    # ========================================================

    candidates = []

    old_articles = 0
    non_soccer = 0
    not_football = 0
    wrong_league = 0
    low_score = 0
    invalid = 0


    for article in articles:

        try:

            result, status = (
                prepare_article(
                    article,
                    query_name,
                    team_index
                )
            )


            if status == "old":

                old_articles += 1

                print(
                    "⏭️ Old article: "
                    f"{article.get('title', '')}"
                )

                continue


            if status == "non_soccer":

                non_soccer += 1

                print(
                    "⛔ Non-soccer: "
                    f"{article.get('title', '')}"
                )

                continue


            if status == "not_football":

                not_football += 1

                print(
                    "⛔ Not football: "
                    f"{article.get('title', '')}"
                )

                continue


            if status == "wrong_league":

                wrong_league += 1

                print(
                    "⛔ Wrong league: "
                    f"{article.get('title', '')}"
                )

                continue


            if status == "low_score":

                low_score += 1

                print(
                    "⛔ Low score: "
                    f"{article.get('title', '')}"
                )

                continue


            if status != "ok":

                invalid += 1

                print(
                    "⛔ Invalid: "
                    f"{status}"
                )

                continue


            candidates.append(
                result
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
    # SORT BY SCORE
    # ========================================================

    candidates.sort(
        key=lambda item: (
            item.get("score", 0)
        ),
        reverse=True
    )


    # ========================================================
    # SAVE
    # ========================================================

    saved = 0
    duplicates = 0


    for item in candidates:

        result = item["record"]
        score = item["score"]
        reasons = item["reasons"]


        # ----------------------------------------------------
        # Duplicate
        # ----------------------------------------------------

        if article_exists(
            result.get(
                "source_url"
            ),
            result.get(
                "source_article_id"
            )
        ):

            duplicates += 1

            print(
                "⏭️ Duplicate: "
                f"{result['title']}"
            )

            continue


        # ----------------------------------------------------
        # Save
        # ----------------------------------------------------

        if save_article(
            result
        ):

            saved += 1

            print("")
            print(
                "✅ SAVED"
            )

            print(
                f"   Score     : {score}/100"
            )

            print(
                f"   Title     : "
                f"{result['title']}"
            )

            print(
                f"   Source    : "
                f"{result['source']}"
            )

            print(
                f"   Published : "
                f"{result['published_at']}"
            )

            print(
                f"   Category  : "
                f"{result['category']}"
            )

            print(
                f"   League    : "
                f"{result['league'] or '-'}"
            )

            print(
                f"   Team      : "
                f"{result['team_name'] or '-'}"
            )

            if reasons:

                print(
                    "   Score why : "
                    + ", ".join(
                        reasons
                    )
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
        f"Low score      : {low_score}"
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

        "low_score":
            low_score,

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
        f"Minimum score: "
        f"{MIN_SCORE}"
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
    total_low_score = 0
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

        total_low_score += (
            result["low_score"]
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
        f"Low score         : "
        f"{total_low_score}"
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
