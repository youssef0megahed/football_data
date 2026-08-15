"""
استدعاء Gemini بنظام احتياطي مبسّط: Flash أولاً، لو فشل يجرب Lite.
مفيش Pro ولا GLM هنا، عشان نركّز على تدريب/تحسين الموديلين دول تحديداً.
"""
import time
import requests

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


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


def call_gemini(prompt, api_key):
    """يجرب Flash الأول، لو فشل يجرب Lite"""
    print("  -> تجربة Gemini Flash...")
    result = _call_gemini_model("gemini-3.6-flash", prompt, api_key)
    if result is not None:
        print("  -> نجح مع Flash")
        return result

    print("  -> Flash فشل، تجربة Lite...")
    result = _call_gemini_model("gemini-3.5-flash-lite", prompt, api_key)
    if result is not None:
        print("  -> نجح مع Lite")
        return result

    print("  -> فشل الاتنين")
    return None
