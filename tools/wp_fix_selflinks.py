import base64, os, re, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
for i in (74, 39, 127):
    p = requests.get(f"{B}/posts/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    raw, link = p["content"]["raw"], p["link"]
    new = re.sub(r'<a [^>]*href="' + re.escape(link) + r'/?"[^>]*>(.*?)</a>', r"\1", raw, flags=re.S)
    n = raw.count(f'href="{link}')
    if new != raw:
        r = requests.post(f"{B}/posts/{i}", headers=A, json={"content": new}, timeout=60); print(i, "자기 링크", n, "개 제거", r.status_code)
    else:
        print(i, "자기 링크 없음")
