#!/bin/bash
# 점검용 — 서치콘솔 색인 안 됨 원인 찾기 (공개 페이지만 읽어요)
python3 - <<'PY'
import re, requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}
def urls(sm):
    r = requests.get(sm, headers=UA, timeout=20); out = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", r.text):
        out += urls(loc) if loc.endswith(".xml") else [loc]
    return out
def check(u):
    r = requests.get(u, headers=UA, timeout=20, allow_redirects=False)
    h = r.text[:200000]
    can = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', h) or re.search(r'href=["\']([^"\']+)["\'][^>]*rel=["\']canonical', h)
    rob = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)', h)
    txt = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", h, flags=re.S)
    n = len(re.sub(r"\s+", "", txt))
    return r.status_code, r.headers.get("location", ""), (can.group(1) if can else "-"), (rob.group(1) if rob else "-"), r.headers.get("x-robots-tag", "-"), n
for site, sm in [("myinfobay", "https://myinfobay.com/sitemap.xml"), ("forsmartlife", "https://forsmartlife.com/sitemap_index.xml")]:
    us = urls(sm); print(f"\n=== {site}: 사이트맵 {len(us)}개")
    bad = 0
    for u in us:
        try:
            s, loc, can, rob, xr, n = check(u)
        except Exception as e:
            print("ERR", u, e); continue
        flag = s != 200 or (can not in ("-", u)) or "noindex" in rob + xr or n < 1500
        if site == "myinfobay" or flag:
            print(f"{'!!' if flag else '  '} {s} len={n} can={'SAME' if can == u else can} robots={rob} xr={xr} {loc} {u}")
        bad += flag
    print(f"문제 의심 {bad}개")
for u in ["https://myinfobay.com/robots.txt", "https://forsmartlife.com/robots.txt"]:
    print("\n---", u); print(requests.get(u, headers=UA, timeout=20).text[:600])
PY
