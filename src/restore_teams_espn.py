import os
import requests

# ============================================================
# CONFIG
# ============================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

REQUEST_TIMEOUT = 30

TEAMS_TABLE = "teams"

SUPABASE_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ============================================================
# ESPN LEAGUES
# ============================================================

LEAGUES = {
    "Premier League": "eng.1",
    "La Liga": "esp.1",
    "Serie A": "ita.1",
    "Bundesliga": "ger.1",
    "Ligue 1": "fra.1",
}

# ============================================================
# ARABIC TEAM NAMES
# ============================================================

TEAM_AR = {
    # --------------------------------------------------------
    # ENGLAND
    # --------------------------------------------------------
    "Arsenal": "أرسنال",
    "Aston Villa": "أستون فيلا",
    "Bournemouth": "بورنموث",
    "Brentford": "برينتفورد",
    "Brighton & Hove Albion": "برايتون",
    "Burnley": "بيرنلي",
    "Chelsea": "تشيلسي",
    "Crystal Palace": "كريستال بالاس",
    "Everton": "إيفرتون",
    "Fulham": "فولهام",
    "Leeds United": "ليدز يونايتد",
    "Liverpool": "ليفربول",
    "Manchester City": "مانشستر سيتي",
    "Manchester United": "مانشستر يونايتد",
    "Newcastle United": "نيوكاسل يونايتد",
    "Nottingham Forest": "نوتنغهام فورست",
    "Sunderland": "سندرلاند",
    "Tottenham Hotspur": "توتنهام",
    "West Ham United": "وست هام يونايتد",
    "Wolverhampton Wanderers": "وولفرهامبتون",
    "Coventry City": "كوفنتري سيتي",
    "Ipswich Town": "إيبسويتش تاون",
    "Hull City": "هال سيتي",

    # --------------------------------------------------------
    # SPAIN
    # --------------------------------------------------------
    "Athletic Club": "أتلتيك بيلباو",
    "Atlético Madrid": "أتلتيكو مدريد",
    "Barcelona": "برشلونة",
    "Celta Vigo": "سيلتا فيغو",
    "Deportivo Alavés": "ديبورتيفو ألافيس",
    "Elche": "إلتشي",
    "Espanyol": "إسبانيول",
    "Getafe": "خيتافي",
    "Girona": "جيرونا",
    "Las Palmas": "لاس بالماس",
    "Leganés": "ليغانيس",
    "Mallorca": "ريال مايوركا",
    "Osasuna": "أوساسونا",
    "Rayo Vallecano": "رايو فايكانو",
    "Real Betis": "ريال بيتيس",
    "Real Madrid": "ريال مدريد",
    "Real Oviedo": "ريال أوفييدو",
    "Real Sociedad": "ريال سوسيداد",
    "Sevilla": "إشبيلية",
    "Valencia": "فالنسيا",
    "Villarreal": "فياريال",
    "Racing Santander": "راسينغ سانتاندير",
    "Deportivo La Coruña": "ديبورتيفو لاكورونيا",
    "Deportivo": "ديبورتيفو لاكورونيا",
    "Levante": "ليفانتي",
    "Málaga": "مالاغا",

    # --------------------------------------------------------
    # ITALY
    # --------------------------------------------------------
    "Atalanta": "أتالانتا",
    "Bologna": "بولونيا",
    "Cagliari": "كالياري",
    "Como": "كومو",
    "Cremonese": "كريمونيزي",
    "Empoli": "إمبولي",
    "Fiorentina": "فيورنتينا",
    "Genoa": "جنوى",
    "Hellas Verona": "هيلاس فيرونا",
    "Inter Milan": "إنتر ميلان",
    "Juventus": "يوفنتوس",
    "Lazio": "لاتسيو",
    "Lecce": "ليتشي",
    "Milan": "ميلان",
    "Monza": "مونزا",
    "Napoli": "نابولي",
    "Parma": "بارما",
    "Pisa": "بيزا",
    "Roma": "روما",
    "Sassuolo": "ساسولو",
    "Torino": "تورينو",
    "Udinese": "أودينيزي",
    "Venezia": "فينيزيا",
    "Frosinone": "فروزينوني",

    # --------------------------------------------------------
    # GERMANY
    # --------------------------------------------------------
    "Augsburg": "أوغسبورغ",
    "Bayer Leverkusen": "باير ليفركوزن",
    "Bayern Munich": "بايرن ميونخ",
    "Borussia Dortmund": "بوروسيا دورتموند",
    "Borussia Mönchengladbach": "بوروسيا مونشنغلادباخ",
    "Eintracht Frankfurt": "آينتراخت فرانكفورت",
    "FC Heidenheim": "هايدنهايم",
    "Freiburg": "فرايبورغ",
    "Hamburg SV": "هامبورغ",
    "Hoffenheim": "هوفنهايم",
    "Mainz": "ماينتس",
    "RB Leipzig": "لايبزيغ",
    "Schalke 04": "شالكه",
    "St. Pauli": "سانت باولي",
    "Union Berlin": "يونيون برلين",
    "VfB Stuttgart": "شتوتغارت",
    "Werder Bremen": "فيردر بريمن",
    "Wolfsburg": "فولفسبورغ",
    "FC Köln": "كولن",
    "1. FC Köln": "كولن",
    "Paderborn": "بادربورن",
    "Elversberg": "إلفرسبرغ",

    # --------------------------------------------------------
    # FRANCE
    # --------------------------------------------------------
    "Angers": "أنجيه",
    "Auxerre": "أوكسير",
    "Brest": "بريست",
    "Le Havre AC": "لوهافر",
    "Le Mans": "لو مان",
    "Lens": "لانس",
    "Lorient": "لوريان",
    "Lille": "ليل",
    "Lyon": "ليون",
    "Marseille": "مارسيليا",
    "Monaco": "موناكو",
    "Montpellier": "مونبلييه",
    "Nantes": "نانت",
    "Nice": "نيس",
    "Paris FC": "باريس إف سي",
    "Paris Saint-Germain": "باريس سان جيرمان",
    "Rennes": "رين",
    "Strasbourg": "ستراسبورغ",
    "Toulouse": "تولوز",
    "Troyes": "تروا",
}

# ============================================================
# VALIDATION
# ============================================================

def validate_environment():
    missing = []

    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")

    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )


# ============================================================
# SUPABASE GET
# ============================================================

def supabase_get(params):
    url = f"{SUPABASE_URL}/rest/v1/{TEAMS_TABLE}"

    response = requests.get(
        url,
        headers=SUPABASE_HEADERS,
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Supabase GET failed "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


# ============================================================
# SUPABASE INSERT
# ============================================================

def supabase_insert(payload):
    url = f"{SUPABASE_URL}/rest/v1/{TEAMS_TABLE}"

    headers = {
        **SUPABASE_HEADERS,
        "Prefer": "return=minimal",
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Supabase INSERT failed "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# SUPABASE UPDATE
# ============================================================

def supabase_update(team_id, payload):
    url = f"{SUPABASE_URL}/rest/v1/{TEAMS_TABLE}"

    params = {
        "id": f"eq.{team_id}"
    }

    headers = {
        **SUPABASE_HEADERS,
        "Prefer": "return=minimal",
    }

    response = requests.patch(
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"Supabase UPDATE failed "
            f"{response.status_code}: "
            f"{response.text}"
        )


# ============================================================
# GET EXISTING ESPN TEAMS
# ============================================================

def get_existing_teams():
    rows = supabase_get({
        "select": "id,source,source_team_id,name,name_ar",
        "source": "eq.espn",
    })

    result = {}

    for row in rows:
        source_team_id = row.get("source_team_id")

        if source_team_id is None:
            continue

        result[str(source_team_id)] = row

    return result


# ============================================================
# ESPN TEAMS
# ============================================================

def get_espn_teams(league_code):
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/"
        f"soccer/{league_code}/teams"
    )

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"ESPN request failed "
            f"{response.status_code}: "
            f"{response.text[:500]}"
        )

    data = response.json()

    teams = []

    sports = data.get("sports", [])

    for sport in sports:
        leagues = sport.get("leagues", [])

        for league in leagues:
            for team_wrapper in league.get("teams", []):
                team = team_wrapper.get("team", {})

                team_id = team.get("id")
                team_name = (
                    team.get("displayName")
                    or team.get("name")
                    or team.get("shortDisplayName")
                )

                if not team_id or not team_name:
                    continue

                teams.append({
                    "source_team_id": str(team_id),
                    "name": team_name.strip(),
                })

    return teams


# ============================================================
# ARABIC NAME
# ============================================================

def arabic_name(name):
    if not name:
        return None

    value = name.strip()

    if value in TEAM_AR:
        return TEAM_AR[value]

    # ESPN sometimes changes display names.
    normalized = value.lower()

    aliases = {
        "manchester city fc": "مانشستر سيتي",
        "manchester united fc": "مانشستر يونايتد",
        "liverpool fc": "ليفربول",
        "arsenal fc": "أرسنال",
        "chelsea fc": "تشيلسي",
        "tottenham hotspur fc": "توتنهام",
        "real madrid cf": "ريال مدريد",
        "fc barcelona": "برشلونة",
        "atletico madrid": "أتلتيكو مدريد",
        "fc bayern munich": "بايرن ميونخ",
        "borussia dortmund": "بوروسيا دورتموند",
        "paris saint-germain fc": "باريس سان جيرمان",
    }

    if normalized in aliases:
        return aliases[normalized]

    return None


# ============================================================
# PROCESS
# ============================================================

def main():

    validate_environment()

    print("=" * 70)
    print("RESTORE ESPN TEAMS")
    print("=" * 70)
    print("SAFE MODE: NO DELETE")
    print("Existing teams are preserved.")
    print("=" * 70)

    existing = get_existing_teams()

    print(
        f"Existing ESPN teams: {len(existing)}"
    )

    inserted = 0
    updated = 0
    skipped = 0
    untranslated = 0

    all_espn_teams = {}

    # --------------------------------------------------------
    # FETCH ALL FIVE LEAGUES
    # --------------------------------------------------------

    for competition, league_code in LEAGUES.items():

        print("")
        print("=" * 70)
        print(competition)
        print("=" * 70)

        teams = get_espn_teams(
            league_code
        )

        print(
            f"ESPN teams found: {len(teams)}"
        )

        for team in teams:

            team_id = team["source_team_id"]
            name = team["name"]

            # Same ESPN team may appear only once.
            all_espn_teams[team_id] = {
                "name": name,
                "competition": competition,
            }

    print("")
    print("=" * 70)
    print(
        f"Unique ESPN teams found: "
        f"{len(all_espn_teams)}"
    )
    print("=" * 70)

    # --------------------------------------------------------
    # RESTORE / UPDATE
    # --------------------------------------------------------

    for source_team_id, team in all_espn_teams.items():

        name = team["name"]
        competition = team["competition"]

        name_ar = arabic_name(name)

        existing_row = existing.get(
            source_team_id
        )

        # ----------------------------------------------------
        # UNKNOWN ARABIC NAME
        # ----------------------------------------------------

        if not name_ar:
            untranslated += 1

            print(
                f"⚠️ Arabic translation missing: "
                f"{name} | {competition}"
            )

        # ----------------------------------------------------
        # EXISTING TEAM
        # ----------------------------------------------------

        if existing_row:

            # Only update Arabic name if we have one.
            if name_ar:

                old_ar = existing_row.get(
                    "name_ar"
                )

                if old_ar != name_ar:

                    supabase_update(
                        existing_row["id"],
                        {
                            "name": name,
                            "name_ar": name_ar,
                        },
                    )

                    updated += 1

                    print(
                        f"🔄 Updated: "
                        f"{name} → {name_ar}"
                    )

                else:

                    skipped += 1

            else:

                skipped += 1

            continue

        # ----------------------------------------------------
        # MISSING TEAM
        # ----------------------------------------------------

        payload = {
            "source": "espn",
            "source_team_id": source_team_id,
            "name": name,
            "name_ar": name_ar,
        }

        supabase_insert(
            payload
        )

        inserted += 1

        print(
            f"➕ Restored: "
            f"{name} → "
            f"{name_ar or 'غير مترجم'}"
        )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("RESTORE SUMMARY")
    print("=" * 70)

    print(
        f"ESPN teams found : "
        f"{len(all_espn_teams)}"
    )

    print(
        f"Inserted          : "
        f"{inserted}"
    )

    print(
        f"Updated Arabic    : "
        f"{updated}"
    )

    print(
        f"Already correct   : "
        f"{skipped}"
    )

    print(
        f"Untranslated      : "
        f"{untranslated}"
    )

    print("=" * 70)

    if untranslated:
        print(
            "⚠️ Some ESPN names were not found "
            "in TEAM_AR and were NOT deleted."
        )

    print(
        "✅ RESTORE FINISHED - NO DELETE OPERATION"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
