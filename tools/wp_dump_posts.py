import base64, json, os, re, html, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
out, page = [], 1
while True:
    r = requests.get(B + "/posts", headers=A, params={"per_page": 25, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json(): break
    for p in r.json():
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p["content"]["raw"])))
        out.append({"id": p["id"], "date": p["date"], "modified": p["modified"], "title": p["title"]["raw"], "slug": p["slug"], "link": p["link"], "cats": p["categories"],
                    "excerpt": p["excerpt"]["raw"], "robots": (p.get("meta") or {}).get("rank_math_robots"), "text": t})
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
# 레디렉션 모듈 쓸 수 있는지
rr = requests.get("https://forsmartlife.com/wp-json/rankmath/v1/redirections", headers=A, timeout=30)
json.dump({"posts": out, "redir_probe": [rr.status_code, rr.text[:200]]}, open("status/audit/posts-dump.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(out))
