#!/bin/bash
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import SITE, req
t = requests.get(SITE + f"/post-sitemap.xml?nc={int(time.time())}", headers={"User-Agent": "Googlebot"}, timeout=30).text
for m in re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", t)[:3] + re.findall(r"<url>\s*<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", t)[-3:]:
    print(m)
print(re.findall(r"<!--.*?-->", t, re.S)[-2:])
p = req("GET", "/posts?status=publish&per_page=1&_fields=id,link,modified").json()[0]; print("최근 저장 글:", p)
x = req("GET", "/posts?status=draft&per_page=3&_fields=id,slug,status").json(); print("임시글:", x)
for path in ["/wp-content/uploads/rank-math/", "/wp-json/rankmath/v1/sitemap"]:
    print(path, requests.get(SITE + path, timeout=20).status_code)
PY
