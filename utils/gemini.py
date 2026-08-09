"""
استدعاء نماذج AI بنظام احتياطي عبر شركتين مختلفتين:
1) Gemini (Pro ثم Flash) - جوجل
2) Groq (Llama 3.3 70B) - شركة مختلفة تماماً، شبكة أمان لو Google وقعت أو اتضغطت
"""
import time
import requests

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_gemini_model(model, prompt, api_key, max_tries=2, wait_seconds=15):
    url = GEMINI_URL_TEMPLATE.format(model=model)
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(1, max_tries + 1):
        try:
            resp = requests.post(url, params={"key": api_key}, json=body, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"    [{model}] محاولة {attempt}: فشل بكود {resp.status_code} - {resp.text[:150]}")
        except Exception as e:
            print(f"    [{model}] محاولة {attempt}: استثناء - {e}")

        if attempt < max_tries:
            time.sleep(wait_seconds)

    return None


def _call_groq(prompt, api_key, max_tries=2, wait_seconds=15):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(1, max_tries + 1):
        try:
            resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"    [Groq] محاولة {attempt}: فشل بكود {resp.status_code} - {resp.text[:150]}")
        except Exception as e:
            print(f"    [Groq] محاولة {attempt}: استثناء - {e}")

        if attempt < max_tries:
            time.sleep(wait_seconds)

    return None


def call_gemini(prompt, api_key, models, groq_api_key=None):
    """
    يجرب موديلات Gemini بالترتيب (Pro ثم Flash عادةً)، ولو فشلت كل الموديلات
    والمفتاح البديل (Groq) متاح، يجرب Groq كملاذ أخير.
    """
    for model in models:
        print(f"  -> تجربة موديل {model}...")
        result = _call_gemini_model(model, prompt, api_key)
        if result is not None:
            print(f"  -> نجح مع {model}")
            return result
        print(f"  -> {model} فشل، ننتقل للتالي")

    if groq_api_key:
        print("  -> كل نماذج Gemini فشلت، تجربة Groq (شبكة أمان)...")
        result = _call_groq(prompt, groq_api_key)
        if result is not None:
            print("  -> نجح مع Groq")
            return result
        print("  -> Groq فشل كمان")

    print("  -> فشلت كل النماذج المتاحة")
    return None
