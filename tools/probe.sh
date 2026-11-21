#!/bin/bash
# 점검용 — forsmartlife 사이트맵: 모듈 껐다 켜서 캐시 비우기 → 그래도 남으면 합친 글 ID 확인
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import GROUPS, clear_cache, SITE, req
from fsl_fix import H
srcs = [s for _, ss in GROUPS for s in ss]
def mod(state):
    x = requests.post(SITE + "/wp-json/rankmath/v1/saveModule", headers=H, json={"module": "sitemap", "state": state}, timeout=60)
    print("sitemap 모듈", state, x.status_code, x.text[:80])
mod("off"); time.sleep(3); mod("on"); time.sleep(3)
print("캐시 비우기:", clear_cache())
t = requests.get(SITE + f"/post-sitemap.xml?nc={int(time.time())}", headers={"User-Agent": "Googlebot"}, timeout=30).text
locs = re.findall(r"<loc>([^<]+)</loc>", t)
left = [u for u in locs if u.rstrip('/').split('/')[-1] in srcs]
print(f"post-sitemap {len(locs)}개, 합친 글 남음 {len(left)}개")
if left:
    s = left[0].rstrip('/').split('/')[-1]
    for stt in ("publish", "private", "draft", "future", "pending"):
        j = req("GET", f"/posts?slug={s}&status={stt}&_fields=id,status,slug").json()
        print(" ", stt, j)
    j = req("GET", f"/pages?slug={s}&status=publish,private&_fields=id,status").json()
    print("  page:", j)
PY
