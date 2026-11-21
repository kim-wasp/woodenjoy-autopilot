#!/bin/bash
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import SITE, GROUPS, req
srcs = [s for _, ss in GROUPS for s in ss]
t = requests.get(SITE + "/post-sitemap.xml", headers={"User-Agent": "Googlebot"}, timeout=30).text
locs = re.findall(r"<loc>([^<]+)</loc>", t); lm = re.findall(r"<lastmod>([^<]+)</lastmod>", t)
pub = {p["link"] for pg in (1,) for p in req("GET", f"/posts?status=publish&per_page=100&page={pg}&_fields=link").json() if isinstance(p, dict)}
print("빠진 글:", sorted(pub - set(locs)))
print("post-sitemap", len(locs), "첫 lastmod", lm[:1], "합친 글", sum(u.rstrip('/').split('/')[-1] in srcs for u in locs), "공개 글", len(pub), "빠진 공개 글", len(pub - set(locs)))
idx = requests.get(SITE + "/sitemap_index.xml", headers={"User-Agent": "Googlebot"}, timeout=30).text
print("index:", re.findall(r"<loc>([^<]+)</loc>", idx))
PY
