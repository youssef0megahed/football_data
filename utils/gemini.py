"""
استدعاء Gemini API بنظام احتياطي: يجرب Pro، لو فشل يجرب Flash.
كل موديل بياخد 5 محاولات، بفاصل دقيقة كاملة بين كل محاولة والتانية.
"""
import time
import requests

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _call_single_model(model, prompt, api_key, max_tries=3, wait_seconds=15):
    """يحاول موديل واحد بعدد محاولات محدد، يرجع النص أو None لو فشل"""
    url = GEMINI_URL_TEMPLATE.format(model=model)
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    for attempt in range(1, max_tries + 1):
        try:
            resp = requests.post(
                url,
                params={"key": api_key},
                json=body,
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                print(f"    [{model}] محاولة {attempt}: فشل بكود {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"    [{model}] محاولة {attempt}: استثناء - {e}")

        if attempt < max_tries:
            time.sleep(wait_seconds)

    return None


def call_gemini(prompt, api_key, models):
    """
    يجرب كل موديل في القائمة بالترتيب لحد ما واحد ينجح.
    models: قائمة أسماء الموديلات بترتيب الأولوية، من config.GEMINI_MODELS
    يرجع النص الناتج أو None لو فشلت كل المحاولات
    """
    for model in models:
        print(f"  -> تجربة موديل {model}...")
        result = _call_single_model(model, prompt, api_key)
        if result is not None:
            print(f"  -> نجح مع {model}")
            return result
        print(f"  -> {model} فشل بعد كل المحاولات، ننتقل للتالي")

    print("  -> فشلت كل النماذج لهذا الطلب")
    return None
