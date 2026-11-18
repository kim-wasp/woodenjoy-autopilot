#!/bin/bash
python3 - <<'PY'
import re, requests
h = requests.get("https://myinfobay.com/", timeout=20).text
anon = sb = None
for js in sorted(set(re.findall(r'/_next/static/[^"]+\.js', h)))[:40]:
    t = requests.get("https://myinfobay.com" + js, timeout=20).text
    m = re.search(r"eyJhbGciOi[\w-]+\.[\w-]+\.[\w-]+", t); u = re.search(r"https://[a-z0-9]+\.supabase\.co", t)
    if m and u: anon, sb = m.group(0), u.group(0); break
H = {"apikey": anon, "Authorization": f"Bearer {anon}"}
for st in ("published", "draft", "hidden"):
    r = requests.get(f"{sb}/rest/v1/posts?select=id&status=neq.published", headers={**H, "Prefer": "count=exact", "Range": "0-0"}, timeout=20)
    print("미공개 글을 방문자가 볼 수 있나:", r.headers.get("content-range")); break
r = requests.get(f"{sb}/rest/v1/cards?select=id&status=neq.approved", headers={**H, "Prefer": "count=exact", "Range": "0-0"}, timeout=20)
print("승인 안 된 카드 노출:", r.headers.get("content-range"), r.status_code)
r = requests.get(f"{sb}/rest/v1/cards?select=status", headers=H, timeout=20)
print("카드 상태 종류:", sorted({x.get("status") for x in r.json()}) if r.status_code == 200 else r.status_code)
PY
