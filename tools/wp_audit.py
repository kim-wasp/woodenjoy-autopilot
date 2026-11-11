"""워드프레스 공개 정보로 사이트 점검 (로그인 없이 REST API로 읽기만): 글 목록, 분류, 글자 수, 이미지, 출처, 고정 페이지, robots"""
import json, re, sys, html
from collections import Counter
import requests

base = sys.argv[1].rstrip("/")
out = sys.argv[2]
UA = {"User-Agent": "Mozilla/5.0 (site-audit)"}
S = requests.Session(); S.headers.update(UA)

def get_all(path, params=None):
    items, page = [], 1
    while True:
        r = S.get(f"{base}/wp-json/wp/v2/{path}", params={**(params or {}), "per_page": 100, "page": page}, timeout=60)
        if r.status_code != 200: break
        data = r.json()
        if not data: break
        items += data
        if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
        page += 1
    return items

cats = {c["id"]: c["name"] for c in get_all("categories")}
posts = get_all("posts", {"_fields": "id,date,modified,slug,link,title,content,excerpt,categories,featured_media,yoast_head_json,rank_math_head"})
pages = get_all("pages", {"_fields": "id,slug,link,title,content"})
rows = []
for p in posts:
    c = p["content"]["rendered"]
    text = html.unescape(re.sub(r"<[^>]+>", " ", c))
    chars = len(re.sub(r"\s", "", text))
    links = re.findall(r'href="(https?://[^"]+)"', c)
    ext = [l for l in links if base.split("//")[1] not in l]
    rows.append({
        "date": p["date"][:10], "title": html.unescape(p["title"]["rendered"]), "slug": p["slug"], "link": p["link"],
        "cats": [cats.get(i, i) for i in p["categories"]], "chars": chars,
        "h2": len(re.findall(r"<h2", c)), "imgs": len(re.findall(r"<img", c)), "tables": len(re.findall(r"<table", c)),
        "ext_links": len(ext), "ext_domains": sorted({re.sub(r"https?://([^/]+).*", r"\1", l) for l in ext})[:8],
        "featured": bool(p.get("featured_media")), "faq": "FAQ" in c or "자주 묻는" in c,
        "disclaimer": bool(re.search(r"의학적|진료|전문의|의사와 상담|의료진", text)),
        "first": re.sub(r"\s+", " ", text)[:160],
    })
home = S.get(base, timeout=60).text
robots_meta = re.findall(r'<meta name="robots"[^>]*>', home)
res = {"base": base, "categories": cats, "post_count": len(rows), "pages": [{"slug": p["slug"], "title": html.unescape(p["title"]["rendered"]),
       "chars": len(re.sub(r"\s", "", re.sub(r"<[^>]+>", " ", p["content"]["rendered"])))} for p in pages],
       "robots_txt": S.get(base + "/robots.txt", timeout=30).text[:1500], "home_robots_meta": robots_meta,
       "home_title": (re.search(r"<title>(.*?)</title>", home, re.S) or [None, ""])[1],
       "ads_txt": S.get(base + "/ads.txt", timeout=30).status_code, "posts": sorted(rows, key=lambda r: r["date"])}
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("posts", len(rows), "pages", len(pages), "cats", cats)
print("by cat", Counter(c for r in rows for c in r["cats"]))
print("by month", sorted(Counter(r["date"][:7] for r in rows).items()))
