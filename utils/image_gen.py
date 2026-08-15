"""
توليد صورة احترافية من HTML/CSS عبر hcti.io - لجداول المباريات والأحداث
"""
import requests

CSS_TEMPLATE = """
body { margin: 0; font-family: 'Tahoma', sans-serif; direction: rtl; }
.wrapper { background: linear-gradient(135deg, #1e3c72, #2a5298); padding: 30px; width: 700px; }
h1 { color: #fff; text-align: center; margin-bottom: 20px; font-size: 22px; }
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; }
th { background: #0d1b2a; color: #fff; padding: 10px 8px; font-size: 14px; }
td { padding: 9px 8px; text-align: center; border-bottom: 1px solid #eee; font-size: 13px; }
tr:nth-child(even) { background: #f5f7fa; }
"""


def generate_table_image(hcti_user_id, hcti_api_key, title, headers, rows):
    """
    title: عنوان الصورة
    headers: قائمة أسماء الأعمدة
    rows: قائمة صفوف (كل صف قائمة قيم)
    """
    headers_html = "".join(f"<th>{h}</th>" for h in headers)
    rows_html = ""
    for row in rows:
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        rows_html += f"<tr>{cells}</tr>"

    html = f"""
    <div class="wrapper">
      <h1>{title}</h1>
      <table>
        <thead><tr>{headers_html}</tr></thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>"""

    resp = requests.post(
        "https://hcti.io/v1/image",
        data={"html": html, "css": CSS_TEMPLATE},
        auth=(hcti_user_id, hcti_api_key),
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("url")
    print(f"  خطأ في توليد الصورة: {resp.status_code} - {resp.text[:200]}")
    return None
