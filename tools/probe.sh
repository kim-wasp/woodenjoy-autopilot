#!/bin/bash
python3 - <<'PY'
import sys, json; sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
import fsl_merge as m
ok = 0
for t, srcs in m.GROUPS:
    tp = m.by_slug(t)
    for s in srcs:
        sp = m.by_slug(s)
        m.redirect(sp, tp["link"])
m.clear_cache()
for t, srcs in m.GROUPS:
    tp = m.by_slug(t)
    for s in srcs:
        r = m.check_redirect(f"{m.SITE}/{s}/", tp["link"]); ok += r[0]
        if not r[0]: print("실패", s, r[1])
print("301 정상", ok)
PY
