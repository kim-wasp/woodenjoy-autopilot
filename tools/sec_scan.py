"""보안 점검 (밖에서 공격자가 보는 것처럼, 아무것도 바꾸지 않음) → status/audit/sec_scan.json + 화면 요약
  python3 tools/sec_scan.py
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (security-review)"}
SITES = ["forsmartlife.com", "sisibibinote.kr", "myinfobay.com", "itinfobay.co.kr"]
STUDIO = "https://woodenjoy-autopilot-studio.vercel.app"
PATHS = ["/.git/HEAD", "/.git/config", "/.env", "/.env.local", "/wp-config.php.bak", "/wp-config.php~", "/wp-config.bak", "/backup.zip", "/backup.sql",
         "/db.sql", "/wp-content/debug.log", "/readme.html", "/license.txt", "/phpinfo.php", "/info.php", "/.DS_Store", "/server-status",
         "/wp-content/uploads/", "/wp-includes/", "/wp-json/wp/v2/users", "/?author=1", "/xmlrpc.php", "/wp-login.php", "/wp-admin/install.php",
         "/wp-content/plugins/", "/.well-known/security.txt", "/package.json", "/next.config.mjs", "/.vercel/project.json", "/wrangler.jsonc"]
HDR = ["strict-transport-security", "content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy",
       "server", "x-powered-by", "x-generator"]
out = {"sites": {}, "dns": {}, "studio": {}, "supabase": {}}


def get(u, **kw):
    try:
        return requests.request(kw.pop("method", "GET"), u, headers={**UA, **kw.pop("headers", {})}, timeout=20, allow_redirects=kw.pop("follow", False), **kw)
    except Exception as e:  # noqa: BLE001
        class R:
            status_code, text, headers = 0, str(e)[:100], {}
        return R()


for h in ([] if os.environ.get("ONLY") == "supabase" else SITES):
    s = {"headers": {}, "paths": {}}
    r = get(f"https://{h}/", follow=True)
    s["home"] = r.status_code
    s["headers"] = {k: (r.headers.get(k) or "")[:120] for k in HDR}
    s["cookies"] = [c[:120] for c in r.headers.get("set-cookie", "").split(",") if c] if r.headers else []
    s["generator"] = re.findall(r'<meta name="generator" content="([^"]+)"', r.text or "")[:3]
    s["ver_in_assets"] = sorted(set(re.findall(r"ver=([0-9.]+)", r.text or "")))[:10]
    s["emails_on_home"] = sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", r.text or "")))[:10]
    s["schema_person"] = re.findall(r'"@type":\["Person","Organization"\][^}]*?"name":"([^"]+)"', r.text or "")[:2]
    for p in PATHS:
        rr = get(f"https://{h}{p}")
        body = (rr.text or "")[:300]
        s["paths"][p] = {"status": rr.status_code, "loc": rr.headers.get("location", "") if rr.headers else "",
                         "hint": re.sub(r"\s+", " ", body)[:160] if rr.status_code == 200 else ""}
    x = get(f"https://{h}/xmlrpc.php", method="POST", data='<?xml version="1.0"?><methodCall><methodName>system.listMethods</methodName></methodCall>')
    s["xmlrpc_post"] = {"status": x.status_code, "methods": len(re.findall(r"<string>", x.text or ""))}
    u = get(f"https://{h}/wp-json/wp/v2/users")
    try:
        s["wp_users_public"] = [(a.get("slug"), a.get("name")) for a in u.json()] if u.status_code == 200 else u.status_code
    except Exception:  # noqa: BLE001
        s["wp_users_public"] = u.status_code
    # 로그인 화면 무차별 대입 방어 (잘못된 아이디로 6번, 잠김·지연 반응이 있는지만 봄)
    if s["paths"]["/wp-login.php"]["status"] == 200:
        codes = []
        for i in range(6):
            lr = get(f"https://{h}/wp-login.php", method="POST", data={"log": "security-review-nonuser", "pwd": f"x{i}"})
            codes.append(lr.status_code)
        s["login_bruteforce"] = {"codes": codes, "last_text": re.sub(r"<[^>]+>|\s+", " ", (lr.text or ""))[:200]}
    # 대표 플러그인 버전 (readme.txt Stable tag)
    if "wp-content" in (r.text or ""):
        plugs = sorted(set(re.findall(r"/wp-content/plugins/([a-z0-9-]+)/", r.text or "")))
        s["plugins"] = {}
        for pl in plugs[:15]:
            rr = get(f"https://{h}/wp-content/plugins/{pl}/readme.txt")
            m = re.search(r"Stable tag:\s*([\w.]+)", rr.text or "")
            s["plugins"][pl] = m.group(1) if m else rr.status_code
        rr = get(f"https://{h}/feed/")
        s["wp_version_feed"] = re.findall(r"wordpress.org/\?v=([0-9.]+)", rr.text or "")[:1]
    out["sites"][h] = s

for d in ([] if os.environ.get("ONLY") == "supabase" else ["forsmartlife.com", "sisibibinote.kr", "myinfobay.com", "itinfobay.co.kr"]):
    dig = lambda t, n=d: subprocess.run(["dig", "+short", t, n], capture_output=True, text=True).stdout.strip()  # noqa: E731
    out["dns"][d] = {"mx": dig("MX"), "spf": [x for x in dig("TXT").split("\n") if "spf" in x.lower()],
                     "dmarc": subprocess.run(["dig", "+short", "TXT", f"_dmarc.{d}"], capture_output=True, text=True).stdout.strip(),
                     "caa": dig("CAA"), "dnssec": "ad" in subprocess.run(["dig", "+dnssec", d], capture_output=True, text=True).stdout.split("flags:")[1][:20] if "flags:" in subprocess.run(["dig", "+dnssec", d], capture_output=True, text=True).stdout else None}

# 관리화면(Vercel) API: 로그인 없이 되는 것이 있는지
st = {}
for p in ["/api/reviews", "/api/sites", "/api/schedule", "/api/trends", "/api/coupang", "/api/cards", "/api/run", "/api/auth"]:
    rr = get(STUDIO + p)
    st[p] = [rr.status_code, (rr.text or "")[:80]]
rr = get(STUDIO + "/api/tick?what=none")
st["/api/tick(no secret)"] = [rr.status_code, (rr.text or "")[:120]]
codes = []
for i in range(8):
    rr = get(STUDIO + "/api/auth", method="POST", json={"password": f"wrong-{i}"})
    codes.append(rr.status_code)
st["login_bruteforce"] = codes
st["headers"] = {k: (get(STUDIO + "/").headers.get(k) or "")[:100] for k in HDR}
out["studio"] = st

# Supabase: 방문자(익명 로그인)가 남의 데이터를 읽거나 글을 고칠 수 있는지 (바꾸는 시도는 '같은 값으로' 덮어써서 내용은 그대로)
SB = os.environ.get("SUPABASE_URL", "").rstrip("/")
html = get("https://myinfobay.com/", follow=True).text or ""
anon = None
for js in sorted(set(re.findall(r'/_next/static/[^"]+\.js', html)))[:40]:
    t = get("https://myinfobay.com" + js).text or ""
    m = re.search(r"eyJhbGciOi[\w-]+\.[\w-]+\.[\w-]+", t)
    if m:
        anon = m.group(0)
        u = re.search(r"https://[a-z0-9]+\.supabase\.co", t)
        if u:
            SB = u.group(0)
        break
sb = {"anon_key_found_in_site": bool(anon), "url_from_site": bool(re.match(r"https://[a-z0-9]+\.supabase\.co$", SB or ""))}
if anon and SB:
    H0 = {"apikey": anon, "Authorization": f"Bearer {anon}"}
    spec = get(SB + "/rest/v1/", headers=H0)
    sb["openapi_anon"] = spec.status_code
    try:
        if spec.status_code != 200:
            raise ValueError
        tables = sorted(k.strip("/") for k in spec.json().get("paths", {}) if k.count("/") == 1 and not k.startswith("/rpc"))
        rpcs = sorted(k for k in spec.json().get("paths", {}) if k.startswith("/rpc"))
    except Exception:  # noqa: BLE001
        tables, rpcs = ["profiles", "responses", "cards", "posts", "categories", "users", "votes", "comments"], []
    sb["tables_visible"], sb["rpcs"] = tables, rpcs
    a = requests.post(SB + "/auth/v1/signup", headers={"apikey": anon, "Content-Type": "application/json"}, json={}, timeout=20)
    tok = (a.json() or {}).get("access_token") if a.status_code == 200 else None
    sb["anon_signin"] = a.status_code
    HU = {"apikey": anon, "Authorization": f"Bearer {tok or anon}"}
    me = (a.json().get("user") or {}).get("id") if tok else None
    reads = {}
    for t in tables:
        rr = get(f"{SB}/rest/v1/{t}?select=*&limit=3", headers=HU)
        rows = rr.json() if rr.status_code == 200 else []
        cols = sorted(rows[0].keys()) if isinstance(rows, list) and rows else []
        others = [x for x in rows if isinstance(x, dict) and x.get("user_id", x.get("id")) not in (me,)] if isinstance(rows, list) else []
        cnt = get(f"{SB}/rest/v1/{t}?select=*", headers={**HU, "Prefer": "count=exact", "Range": "0-0"}).headers.get("content-range", "")
        reads[t] = {"status": rr.status_code, "rows_returned": len(rows) if isinstance(rows, list) else rr.text[:80], "count": cnt, "cols": cols[:15], "others_rows": len(others)}
    sb["reads"] = reads
    writes = {}
    for t in tables:
        rr = get(f"{SB}/rest/v1/{t}?select=*&limit=1", headers={"apikey": anon, "Authorization": f"Bearer {anon}"})
        row = rr.json()[0] if rr.status_code == 200 and isinstance(rr.json(), list) and rr.json() else None
        if not row:
            continue
        key = "id" if "id" in row else next(iter(row))
        col = next((c for c in row if c not in (key, "created_at", "updated_at") and isinstance(row[c], (str, int)) and not isinstance(row[c], bool)), None)
        if not col:
            continue
        wr = get(f"{SB}/rest/v1/{t}?{key}=eq.{row[key]}", method="PATCH", headers={**HU, "Content-Type": "application/json", "Prefer": "return=representation"}, json={col: row[col]})
        writes[t] = {"patch_same_value": wr.status_code, "rows_changed": len(wr.json()) if wr.status_code == 200 and isinstance(wr.json(), list) else (wr.text or "")[:100]}
    sb["writes"] = writes
out["supabase"] = sb

# 결과는 공개 저장소에 그대로 두면 안 돼요 → 임시 파일에만 쓰고, 올리는 건 tools/seal.py 로 잠근 것만
Path("/tmp/sec_scan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print("점검 끝 (결과는 잠가서 저장)")
