#!/bin/bash
# 점검용 — forsmartlife 사이트맵에 남은 합친 글(301) 정리: 상태 확인 → 캐시 비우기 → 사이트맵 다시 확인
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import GROUPS, by_slug, clear_cache, req, SITE
srcs = [s for _, ss in GROUPS for s in ss]
st = {}
for s in srcs:
    p = by_slug(s, "publish,private,draft")
    st[s] = (p or {}).get("status", "없음")
print("합친 글 상태:", {v: list(st.values()).count(v) for v in set(st.values())})
for s, v in st.items():
    if v == "publish":
        print("  아직 공개:", s)
# 최근 공개 글 하나를 그대로 다시 저장 → Rank Math 사이트맵 캐시 무효화
p = req("GET", "/posts?status=publish&per_page=1&_fields=id").json()[0]
print("다시 저장:", req("POST", f"/posts/{p['id']}", json={}).status_code)
print("캐시 비우기:", clear_cache())
time.sleep(5)
UA = {"User-Agent": "Googlebot", "Cache-Control": "no-cache"}
def urls(sm):
    t = requests.get(sm + ("&" if "?" in sm else "?") + f"nc={int(time.time())}", headers=UA, timeout=30).text
    out = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", t):
        out += urls(loc) if loc.endswith(".xml") else [loc]
    return out
us = urls(SITE + "/sitemap_index.xml")
left = [u for u in us if u.rstrip("/").split("/")[-1] in srcs]
print(f"사이트맵 {len(us)}개, 합친 글 남음 {len(left)}개")
for u in left[:5]: print("  ", u)
PY
