#!/bin/bash
cd tools && python3 - <<'PY'
from fsl_merge import req
r = req("GET", "/plugins?_fields=plugin,name,status,version")
print(r.status_code)
for p in (r.json() if r.status_code == 200 else []): print(p)
r = req("GET", "/posts?status=publish&per_page=100&_fields=id&orderby=modified")
print("공개 글 수:", r.headers.get("X-WP-Total"))
PY
