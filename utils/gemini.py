"""
استدعاء نماذج AI بترتيب محدد:
1) Gemini Flash (أساسي)
2) GLM (glm-4.7-flash) - شركة مختلفة تماماً، خط دفاع تاني
3) Gemini Flash-Lite - ملاذ أخير
"""
import time
import requests

GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
GLM_URL = "https://api.z.ai/api/paas/v4/chat/completions"


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


def _call_glm(prompt, api_key, max_tries=2, wait_seconds=15):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": "glm-4.7-flash",
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(1, max_tries + 1):
        try:
            resp = requests.post(GLM_URL, headers=headers, json=body, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            else:
                print(f"    [GLM] محاولة {attempt}: فشل بكود {resp.status_code} - {resp.text[:150]}")
        except Exception as e:
            print(f"    [GLM] محاولة {attempt}: استثناء - {e}")

        if attempt < max_tries:
            time.sleep(wait_seconds)

    return None


def call_gemini(prompt, gemini_api_key, glm_api_key=None):
    """
    الترتيب: Gemini Flash -> GLM -> Gemini Flash-Lite
    """
    print("  -> تجربة Gemini Flash...")
    result = _call_gemini_model("gemini-3.6-flash", prompt, gemini_api_key)
    if result is not None:
        print("  -> نجح مع Gemini Flash")
        return result
    print("  -> Gemini Flash فشل، ننتقل لـ GLM")

    if glm_api_key:
        result = _call_glm(prompt, glm_api_key)
        if result is not None:
            print("  -> نجح مع GLM")
            return result
        print("  -> GLM فشل، ننتقل لملاذ أخير")

    print("  -> تجربة Gemini Flash-Lite (ملاذ أخير)...")
    result = _call_gemini_model("gemini-3.5-flash-lite", prompt, gemini_api_key)
    if result is not None:
        print("  -> نجح مع Gemini Flash-Lite")
        return result

    print("  -> فشلت كل النماذج المتاحة")
    return None
