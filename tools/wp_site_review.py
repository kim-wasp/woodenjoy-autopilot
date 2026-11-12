"""forsmartlife 애드센스 점검용 자료 모으기 (읽기만)."""
import base64, json, os, re, html
import requests
B = "https://forsmartlife.com"
tok = base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode()
S = requests.Session(); S.headers.update({"User-Agent": "Mozilla/5.0 (site-review)"})
A = {"Authorization": f"Basic {tok}"}
out = {}
def g(path, auth=True, **p):
    r = S.get(B + path, headers=A if auth else {}, params=p, timeout=90)
    return r.status_code, (r.json() if "json" in r.headers.get("content-type", "") else r.text)
out["me"] = g("/wp-json/wp/v2/users/me", context="edit")
out["settings"] = g("/wp-json/wp/v2/settings")
out["plugins"] = g("/wp-json/wp/v2/plugins")
out["themes"] = g("/wp-json/wp/v2/themes", status="active")
out["menus"] = g("/wp-json/wp/v2/menus")
out["menu_items"] = g("/wp-json/wp/v2/menu-items", per_page=100)
out["sidebars"] = g("/wp-json/wp/v2/sidebars")
out["widgets"] = g("/wp-json/wp/v2/widgets", per_page=100)
code, pages = g("/wp-json/wp/v2/pages", per_page=100, context="edit", status="publish,draft,private")
out["pages"] = [{"id": p["id"], "status": p["status"], "slug": p["slug"], "link": p["link"], "title": p["title"]["raw"],
                 "text": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p["content"]["raw"])))[:6000]} for p in pages] if code == 200 else pages
cats = g("/wp-json/wp/v2/categories", per_page=100)[1]
out["categories"] = [{"id": c["id"], "name": c["name"], "count": c["count"], "slug": c["slug"], "desc": c["description"]} for c in cats] if isinstance(cats, list) else cats
out["tags_count"] = len(g("/wp-json/wp/v2/tags", per_page=100)[1] or [])
for p in ["/", "/robots.txt", "/ads.txt", "/sitemap_index.xml", "/feed/"]:
    r = S.get(B + p, timeout=60)
    out["public" + p] = {"status": r.status_code, "len": len(r.text), "head": r.text[:3000] if p != "/" else ""}
    if p == "/":
        open("status/audit/home.html", "w").write(r.text)
# 글 목록: 날짜/카테고리/글자수/noindex
posts, page = [], 1
while True:
    r = S.get(B + "/wp-json/wp/v2/posts", headers=A, params={"per_page": 100, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json():
        out["posts_err"] = [r.status_code, r.text[:300]]; break
    for p in r.json():
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", p["content"]["raw"])))
        posts.append({"id": p["id"], "status": p["status"], "date": p["date"], "title": p["title"]["raw"], "link": p["link"], "cats": p["categories"],
                      "chars": len(t), "imgs": p["content"]["raw"].count("<img"), "featured": p["featured_media"], "comment": p["comment_status"],
                      "robots": (p.get("meta") or {}).get("rank_math_robots"),
                      "fp": re.findall(r"[^.!?]{0,50}(?<![가-힣])(?:저는|제가|저도|저희|제 경험|제 주변)[^.!?]{0,50}|[^.!?]{0,50}(?:해보니|써보니|먹어보니)[^.!?]{0,30}", t)[:5],
                      "claims": re.findall(r"[^.!?]{0,60}(?:효과를 본|케이스가 많|사례가 많|확실히|무조건|반드시 낫|완치|100%|특효|기적)[^.!?]{0,40}", t)[:5]})
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
out["posts"] = posts
json.dump(out, open("status/audit/site-review.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("ok", len(posts))
