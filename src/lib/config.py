import os
from zoneinfo import ZoneInfo

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

TIMEZONE = ZoneInfo("Africa/Cairo")

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4

ESPN_BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/soccer"

# البطولات المتابعة حاليًا. المفتاح = اسم البطولة (بيتخزن زيه)،
# القيمة = كود ESPN للدوري.
COMPETITIONS = {
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
}

COMPETITION_COUNTRY = {
    "Premier League": "England",
    "La Liga": "Spain",
    "Serie A": "Italy",
    "Bundesliga": "Germany",
    "Ligue 1": "France",
}


def validate_environment():

    required = {
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }

    missing = [key for key, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing)
        )
