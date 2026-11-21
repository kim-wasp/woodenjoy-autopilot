#!/bin/bash
# 점검용 — forsmartlife 사이트맵 캐시: 응답 헤더 보기 → Rank Math 임시 데이터 비우기 → 다시 확인
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import GROUPS, clear_cache, SITE
from fsl_fix import H
srcs = [s for _, ss in GROUPS for s in ss]
r = requests.get(SITE + "/post-sitemap.xml", headers={"User-Agent": "Googlebot"}, timeout=30)
print("헤더:", {k: v for k, v in r.headers.items() if k.lower() in ("cache-control", "age", "x-cache", "cf-cache-status", "last-modified", "x-litespeed-cache", "x-proxy-cache", "server")})
print("생성 표시:", re.findall(r"<!--.*?-->", r.text)[:3])
for act in ("clear_transients", "clear_sitemap_cache"):
    x = requests.post(SITE + "/wp-json/rankmath/v1/toolsAction", headers=H, json={"action": act}, timeout=60)
    print(act, x.status_code, x.text[:120])
print("캐시 비우기:", clear_cache())
time.sleep(5)
t = requests.get(SITE + f"/post-sitemap.xml?nc={int(time.time())}", headers={"User-Agent": "Googlebot"}, timeout=30).text
locs = re.findall(r"<loc>([^<]+)</loc>", t)
print(f"post-sitemap {len(locs)}개, 합친 글 남음 {sum(u.rstrip('/').split('/')[-1] in srcs for u in locs)}개")
PY
