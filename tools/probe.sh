#!/bin/bash
# 점검용 — forsmartlife 합친 글 21개: 비공개 → 임시글(사이트맵에서 빠지게). 301 이동은 그대로인지 확인
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import GROUPS, by_slug, clear_cache, check_redirect, req, SITE
done = 0
for tgt, ss in GROUPS:
    for s in ss:
        p = by_slug(s, "private")
        if p:
            done += req("POST", f"/posts/{p['id']}", json={"status": "draft"}).status_code == 200
print("임시글로 바꿈:", done)
print("캐시 비우기:", clear_cache()); time.sleep(5)
srcs = [s for _, ss in GROUPS for s in ss]
t = requests.get(SITE + f"/post-sitemap.xml?nc={int(time.time())}", headers={"User-Agent": "Googlebot"}, timeout=30).text
locs = re.findall(r"<loc>([^<]+)</loc>", t)
print(f"post-sitemap {len(locs)}개, 합친 글 남음 {sum(u.rstrip('/').split('/')[-1] in srcs for u in locs)}개")
ok = 0
for tgt, ss in GROUPS:
    for s in ss:
        good, info = check_redirect(f"{SITE}/{s}/", f"{SITE}/{tgt}/")
        ok += good
        if not good: print("  이동 안 됨:", s, info)
print(f"301 이동 정상 {ok}/{len(srcs)}")
PY
