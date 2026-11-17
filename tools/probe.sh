#!/bin/bash
python3 - <<'PY'
import sys, re, requests
sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
import fsl_fix as f
for pid in (1031, 968):
    r=f.req("GET", f"/posts/{pid}?context=edit&_fields=content").json()["content"]["raw"]
    print(pid, len(r), r.count("<img"), re.findall(r"<(?:img|figure|!-- wp:image)[^>]{0,120}", r)[:3], "AI로" in r)
PY
