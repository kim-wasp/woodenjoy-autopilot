"""forsmartlife 약한 글 비공개로 돌리기 + 그 글로 가는 내부 링크 풀기 (글자는 남김). 되돌리기: --restore"""
import base64, json, os, re, sys, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
ids = [int(x) for x in os.environ["IDS"].split(",")]
if "--restore" in sys.argv:
    for i in ids:
        print("공개로", i, requests.post(f"{B}/posts/{i}", headers=A, json={"status": "publish"}, timeout=60).status_code)
    sys.exit()
links = {}
for i in ids:
    p = requests.get(f"{B}/posts/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    links[i] = p["link"]
log = {"private": [], "unlinked": []}
for i in ids:
    r = requests.post(f"{B}/posts/{i}", headers=A, json={"status": "private"}, timeout=60)
    log["private"].append([i, r.status_code]); print("비공개", i, r.status_code)
slugs = [re.sub(r"^https?://[^/]+", "", u).strip("/") for u in links.values()]
page = 1
while True:
    r = requests.get(B + "/posts", headers=A, params={"per_page": 25, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json(): break
    for p in r.json():
        raw = new = p["content"]["raw"]
        for s in slugs:
            new = re.sub(r'<a [^>]*href="https?://(?:www\.)?forsmartlife\.com/' + re.escape(s) + r'/?"[^>]*>(.*?)</a>', r"\1", new, flags=re.S)
        if new != raw:
            rr = requests.post(f"{B}/posts/{p['id']}", headers=A, json={"content": new}, timeout=60)
            log["unlinked"].append([p["id"], rr.status_code]); print("링크 풀기", p["id"], rr.status_code)
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
json.dump({"links": links, **log}, open("status/audit/prune.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
