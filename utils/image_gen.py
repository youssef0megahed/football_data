"""
توليد صورة مجاناً عبر Pollinations.ai بناءً على وصف نصي
"""
from urllib.parse import quote


def generate_image_url(prompt_text):
    """يرجع رابط صورة جاهز (Pollinations بيولدها عند فتح الرابط)"""
    encoded = quote(prompt_text)
    return f"https://image.pollinations.ai/prompt/{encoded}"
