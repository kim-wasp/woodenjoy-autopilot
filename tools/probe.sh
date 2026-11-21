#!/bin/bash
cd tools && python3 - <<'PY'
import re, requests, time
from fsl_merge import SITE, GROUPS
srcs = [s for _, ss in GROUPS for s in ss]
for path in ["/post-sitemap.xml", f"/index.php?sitemap=post&x={int(time.time())}", f"/?sitemap=post&sitemap_n=&y={int(time.time())}"]:
    r = requests.get(SITE + path, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    t = r.text
    locs = re.findall(r"<loc>([^<]+)</loc>", t); lm = re.findall(r"<lastmod>([^<]+)</lastmod>", t)
    print(path, r.status_code, len(locs), "첫 lastmod", lm[:1], "합친 글", sum(u.rstrip('/').split('/')[-1] in srcs for u in locs), {k: v for k, v in r.headers.items() if k.lower() in ("x-cache", "x-proxy-cache", "age", "x-fastcgi-cache", "x-cache-status")})
PY
