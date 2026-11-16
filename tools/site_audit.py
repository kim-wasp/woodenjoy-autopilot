"""사이트 전체 점검 (애드센스·검색 기준). 사이트맵의 모든 페이지를 읽어 문제를 찾아요.

  python3 tools/site_audit.py sisibibinote.kr myinfobay.com forsmartlife.com
결과: status/audit/site_audit.json (페이지별) + 화면에 요약
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (compatible; StudioAudit/1.0)"}
REQUIRED = {"소개": ["about", "소개"], "개인정보": ["privacy", "개인정보"], "문의": ["contact", "문의"]}


def get(url, **kw):
    try:
        return requests.get(url, headers=UA, timeout=25, allow_redirects=True, **kw)
    except Exception as e:  # noqa: BLE001
        class R:  # noqa: D401
            status_code, text, url, history, headers = 0, str(e), url, [], {}
        return R()


def sitemap_urls(host):
    urls, seen = [], set()
    todo = [f"https://{host}/sitemap.xml", f"https://{host}/sitemap_index.xml"]
    while todo and len(urls) < 400:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = get(sm)
        if r.status_code != 200:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        for u in locs:
            (todo if u.endswith(".xml") else urls).append(u)
    return list(dict.fromkeys(urls))


def page(url):
    r = get(url)
    out = {"url": url, "status": r.status_code, "final": r.url, "redirects": len(r.history)}
    if r.status_code != 200 or "html" not in r.headers.get("content-type", "html"):
        return out
    s = BeautifulSoup(r.text, "html.parser")
    meta = lambda n, a="name": (s.find("meta", {a: n}) or {}).get("content", "")  # noqa: E731
    for t in s(["script", "style", "noscript"]):
        t.decompose()
    main = s.find("article") or s.find("main") or s.body or s
    text = re.sub(r"\s+", " ", main.get_text(" ")).strip()
    links = [a.get("href", "") for a in main.find_all("a")]
    host = urlparse(url).netloc
    imgs = main.find_all("img")
    out.update({
        "title": (s.title.get_text().strip() if s.title else ""),
        "desc": meta("description"),
        "robots": meta("robots"),
        "canonical": (s.find("link", {"rel": "canonical"}) or {}).get("href", ""),
        "og_image": meta("og:image", "property"),
        "h1": len(s.find_all("h1")),
        "h2": len(main.find_all("h2")),
        "chars": len(re.sub(r"\s", "", text)),
        "imgs": len(imgs),
        "imgs_no_alt": sum(1 for i in imgs if not (i.get("alt") or "").strip()),
        "int_links": sum(1 for h in links if h.startswith("/") or host in h),
        "ext_links": sum(1 for h in links if h.startswith("http") and host not in h),
        "has_date": bool(s.find("time") or re.search(r"20\d\d[.-]\s?\d{1,2}[.-]\s?\d{1,2}", text)),
        "ai_label": bool(re.search(r"AI[로 ]?(생성|만든|이미지)|AI 이미지|인공지능으로 생성", text)),
        "adsense_code": "adsbygoogle" in r.text or "pagead2.googlesyndication" in r.text,
        "lorem": bool(re.search(r"lorem ipsum|준비 중이에요|Hello world|Sample Page|샘플 페이지", r.text, re.I)),
    })
    return out


def audit(host):
    rep = {"host": host}
    home = get(f"https://{host}/")
    rep["home_status"], rep["home_final"] = home.status_code, home.url
    for v in (f"http://{host}/", f"https://www.{host}/"):
        r = get(v)
        rep.setdefault("variants", {})[v] = r.url
    rep["robots_txt"] = get(f"https://{host}/robots.txt").text[:600]
    ads = get(f"https://{host}/ads.txt")
    rep["ads_txt"] = ads.text.strip()[:300] if ads.status_code == 200 else f"없음({ads.status_code})"
    urls = sitemap_urls(host)
    rep["sitemap_count"] = len(urls)
    pages = [page(u) for u in urls[:250]]
    rep["pages"] = pages
    ok = [p for p in pages if p.get("status") == 200 and "title" in p]
    tc = Counter(p["title"] for p in ok)
    dc = Counter(p["desc"] for p in ok if p["desc"])
    home_html = home.text if home.status_code == 200 else ""
    rep["summary"] = {
        "pages": len(pages),
        "not_200": [(p["url"], p["status"]) for p in pages if p.get("status") != 200],
        "redirected_in_sitemap": [p["url"] for p in pages if p.get("redirects")],
        "noindex": [p["url"] for p in ok if "noindex" in p["robots"].lower()],
        "dup_titles": [t for t, n in tc.items() if n > 1],
        "dup_desc": [d[:60] for d, n in dc.items() if n > 1],
        "no_desc": [p["url"] for p in ok if not p["desc"]],
        "thin_lt1500": [(p["url"], p["chars"]) for p in ok if p["chars"] < 1500],
        "h1_not_1": [(p["url"], p["h1"]) for p in ok if p["h1"] != 1],
        "imgs_no_alt": sum(p["imgs_no_alt"] for p in ok),
        "no_internal_links": [p["url"] for p in ok if p["int_links"] < 2 and p["chars"] > 1500],
        "no_og_image": len([p for p in ok if not p["og_image"]]),
        "placeholder_text": [p["url"] for p in ok if p["lorem"]],
        "required_pages": {k: any(any(w in p["url"] or w in p["title"] for w in ws) for p in ok) or any(w in home_html for w in ws) for k, ws in REQUIRED.items()},
        "avg_chars": int(sum(p["chars"] for p in ok) / max(1, len(ok))),
    }
    return rep


if __name__ == "__main__":
    reps = [audit(h) for h in sys.argv[1:]]
    out = ROOT / "status/audit/site_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(reps, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in reps:
        print("=" * 60, r["host"], r["home_status"], r["home_final"])
        print("variants", r["variants"])
        print("ads.txt", r["ads_txt"][:120])
        print("robots", r["robots_txt"][:200].replace("\n", " | "))
        print("sitemap", r["sitemap_count"])
        print(json.dumps(r["summary"], ensure_ascii=False, indent=1)[:4000])
