#!/bin/bash
python3 - <<'PY'
import sys, requests
sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
from fsl_fix import req, H
old = 'font-size:13px;color:#5b6b70;font-weight:600">'
new = 'font-size:13px;color:#5b6b70;font-weight:600;background:#fff;border:0">'
page, n = 1, 0
while True:
    r = req("GET", f"/posts?status=publish&per_page=20&page={page}&context=edit&_fields=id,content")
    for p in r.json():
        raw = p["content"]["raw"]
        if "sig-myth" in raw and old in raw:
            req("POST", f"/posts/{p['id']}", json={"content": raw.replace(old, new)}); n += 1
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
print("표 머리 고침", n)
for slug, title, seo in (("health-calculators", "건강 계산기", "건강 계산기: BMI·허리둘레, 독감 무료접종 대상 확인 %sep% %sitename%"),
                         ("flu-weekly", "이번 주 독감 수치", "이번 주 독감 수치: 질병관리청 의사환자분율 주별 그래프 %sep% %sitename%")):
    pid = req("GET", f"/pages?slug={slug}&_fields=id").json()[0]["id"]
    req("POST", f"/pages/{pid}", json={"title": title})
    print(slug, requests.post("https://forsmartlife.com/wp-json/rankmath/v1/updateMeta", headers=H, json={"objectType": "post", "objectID": pid, "meta": {"rank_math_title": seo}}).status_code)
import fsl_merge as m; print("캐시", m.clear_cache())
PY
