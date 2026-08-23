import os
import json
import time
import requests

from lib.config import validate_environment
from lib.log import log, retry_call
from lib.supabase_client import supabase_request, select


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]

GEMINI_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

BATCH_SIZE = 40


def validate_gemini_env():

    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY")


# ============================================================
# GEMINI TRANSLATION (batched)
# ============================================================

def call_gemini(model, payload):

    url = GEMINI_URL_TEMPLATE.format(model=model)

    def request():

        response = requests.post(
            url,
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code in {408, 429, 500, 502, 503, 504}:
            raise RuntimeError(
                f"Gemini ({model}) transient HTTP "
                f"{response.status_code}: {response.text[:300]}"
            )

        raise RuntimeError(
            f"Gemini ({model}) HTTP {response.status_code}: "
            f"{response.text[:500]}"
        )

    return retry_call(request, f"Gemini ({model})")


def translate_batch(names, kind):
    """names: list of strings. kind: 'لاعب كرة قدم' أو 'نادي كرة قدم'.
    بيرجع dict {original_name: arabic_name}."""

    numbered = "\n".join(
        f"{i+1}. {name}" for i, name in enumerate(names)
    )

    prompt = (
        f"ترجم أسماء {kind} التالية للعربية بالصياغة المستخدمة في "
        "الإعلام الرياضي العربي (الأسماء الشائعة المعروفة، مش "
        "ترجمة صوتية حرفية لو فيه اسم متعارف عليه بشكل مختلف). "
        "أرجع فقط مصفوفة JSON صحيحة بنفس الترتيب والعدد بالضبط "
        "(اسم عربي واحد لكل سطر بالترتيب)، بدون أي نص أو "
        "markdown إضافي، بالشكل: [\"اسم1\", \"اسم2\", ...]\n\n"
        f"{numbered}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4000},
    }

    last_error = None

    for model in GEMINI_MODELS:

        try:

            data = call_gemini(model, payload)

            text = (
                data["candidates"][0]["content"]["parts"][0]["text"]
            ).strip()

            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]

            translated = json.loads(text.strip())

            if len(translated) != len(names):
                raise RuntimeError(
                    f"Count mismatch: sent {len(names)}, "
                    f"got {len(translated)}"
                )

            return dict(zip(names, translated))

        except Exception as error:

            last_error = error

            log(f"Gemini model '{model}' failed: {error}")

            continue

    raise RuntimeError(f"Both Gemini models failed: {last_error}")


# ============================================================
# GENERIC: translate + save for a table
# ============================================================

def translate_table(table, kind_label):

    rows = select(
        table,
        {"select": "id,name", "name_ar": "is.null"},
    )

    log(f"{table}: {len(rows)} rows without name_ar")

    total_updated = 0

    for start in range(0, len(rows), BATCH_SIZE):

        batch = rows[start:start + BATCH_SIZE]
        names = [r["name"] for r in batch]

        try:
            translations = translate_batch(names, kind_label)
        except Exception as error:
            log(f"ERROR translating batch: {error}")
            continue

        for row in batch:

            arabic_name = translations.get(row["name"])

            if not arabic_name:
                continue

            try:

                supabase_request(
                    "PATCH",
                    table,
                    params={"id": f"eq.{row['id']}"},
                    json_body={"name_ar": arabic_name},
                    extra_headers={"Prefer": "return=minimal"},
                )

                total_updated += 1

            except Exception as error:
                log(f"ERROR saving id={row['id']}: {error}")
                continue

        log(
            f"{table}: batch {start // BATCH_SIZE + 1} done "
            f"({total_updated} total so far)"
        )

        time.sleep(1)

    return total_updated


# ============================================================
# MAIN
# ============================================================

def main():

    validate_environment()
    validate_gemini_env()

    log("==================================================")
    log("TRANSLATE NAMES START")
    log("==================================================")

    teams_updated = translate_table("teams", "نادي كرة قدم")
    log(f"Teams translated: {teams_updated}")

    players_updated = translate_table("players", "لاعب كرة قدم")
    log(f"Players translated: {players_updated}")

    log("==================================================")
    log("TRANSLATE NAMES END")
    log("==================================================")


if __name__ == "__main__":
    main()
          
