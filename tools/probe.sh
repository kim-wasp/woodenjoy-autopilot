#!/bin/bash
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import SITE, GROUPS
srcs = [s for _, ss in GROUPS for s in ss]
r = requests.get(SITE + f"/wp-cron.php?doing_wp_cron={time.time():.4f}", timeout=60)
print("wp-cron", r.status_code, len(r.text))
time.sleep(10)
t = requests.get(SITE + "/post-sitemap.xml", headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
locs = re.findall(r"<loc>([^<]+)</loc>", t); lm = re.findall(r"<lastmod>([^<]+)</lastmod>", t)
print("post-sitemap", len(locs), "첫 lastmod", lm[:1], "합친 글", sum(u.rstrip('/').split('/')[-1] in srcs for u in locs))
PY
