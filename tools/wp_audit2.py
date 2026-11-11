"""forsmartlife 1단계 정리용 상세 점검 (관리자 연결로 읽기만, 아무것도 바꾸지 않음)"""
import base64, html, json, os, re, sys
import requests

base, user, out = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
tok = base64.b64encode(f"{user}:{os.environ['WP']}".encode()).decode()
S = requests.Session(); S.headers.update({"Authorization": f"Basic {tok}", "User-Agent": "Mozilla/5.0 (site-audit)"})

def get_all(path, params=None):
    items, page = [], 1
    while True:
        r = S.get(f"{base}/wp-json/wp/v2/{path}", params={**(params or {}), "per_page": 100, "page": page}, timeout=90)
        if r.status_code != 200: break
        d = r.json()
        if not d: break
        items += d
        if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
        page += 1
    return items

cats = {c["id"]: c["name"] for c in get_all("categories")}
FP = re.compile(r"[^.!?\n]*(?:저도|저는|제가|저희|제 경험|제 주변|직접 (?:해|써|먹|해봤|겪)|해보니|써보니|먹어보니|겪어보니|느꼈|경험상|우리 (?:아이|집|가족|엄마|아빠)|남편|아내|와이프|아들|딸이)[^.!?\n]*[.!?]?")
posts = []
for st in ("publish", "draft", "private", "future", "pending"):
    posts += get_all("posts", {"status": st, "context": "edit"})
res = []
for p in posts:
    raw = p["content"].get("raw") or p["content"]["rendered"]
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    imgs = [{"src": m.group(1).split("/")[-1][:80], "alt": (re.search(r'alt="([^"]*)"', m.group(0)) or [None, ""])[1][:60]}
            for m in re.finditer(r'<img[^>]*src="([^"]+)"[^>]*>', raw)]
    fp = [re.sub(r"\s+", " ", s).strip()[:120] for s in FP.findall(text)]
    res.append({
        "id": p["id"], "status": p["status"], "date": p["date"][:10], "slug": p["slug"], "link": p["link"],
        "title": html.unescape(p["title"]["raw"] if isinstance(p["title"], dict) and "raw" in p["title"] else p["title"]["rendered"]),
        "cats": [cats.get(i, i) for i in p["categories"]], "chars": len(re.sub(r"\s", "", text)),
        "imgs": imgs, "first_person": fp[:8], "first_person_n": len(fp),
        "placeholders": re.findall(r"\[(?:이미지|사진|IMAGE)[^\]]{0,40}\]", text)[:3],
        "raw_md": len(re.findall(r"(?m)^\s*(?:#{2,4} |\*\*[^*]+\*\*\s*$)", text)),
        "wiki": len(re.findall(r"wikipedia\.org", raw)),
        "lang": p.get("lang") or "", "translations": p.get("translations") or {},
        "meta_keys": sorted(k for k in (p.get("meta") or {}) if "rank" in k.lower())[:5],
        "intro": re.sub(r"\s+", " ", text).strip()[:200],
    })
# 공개 화면에서 noindex 여부, 표준 주소
for r in res:
    if r["status"] != "publish": continue
    try:
        h = requests.get(r["link"], timeout=40, headers={"User-Agent": "Mozilla/5.0"}).text
        r["robots"] = (re.search(r'<meta name="robots" content="([^"]+)"', h) or [None, ""])[1]
        r["canonical"] = (re.search(r'<link rel="canonical" href="([^"]+)"', h) or [None, ""])[1]
        r["hreflang"] = re.findall(r'hreflang="([^"]+)"', h)[:4]
    except Exception as e:
        r["robots"] = f"err {e}"
users = S.get(f"{base}/wp-json/wp/v2/users", params={"context": "edit"}, timeout=60).json()
langs = S.get(f"{base}/wp-json/pll/v1/languages", timeout=60)
sm = requests.get(f"{base}/sitemap_index.xml", timeout=60).text
json.dump({"categories": cats, "posts": sorted(res, key=lambda r: r["date"]),
           "users": [{"id": u["id"], "name": u.get("name"), "slug": u.get("slug")} for u in users] if isinstance(users, list) else users,
           "pll_languages": langs.json() if langs.ok else langs.status_code,
           "sitemaps": re.findall(r"<loc>([^<]+)</loc>", sm)}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("posts", len(res), "statuses", {s: sum(r["status"] == s for r in res) for s in {r["status"] for r in res}})
