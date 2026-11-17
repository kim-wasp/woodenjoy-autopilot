#!/bin/bash
python3 - <<'PY'
import sys, requests
sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
from fsl_fix import req, H
revs = req("GET", "/posts/97/revisions?context=edit&_fields=id,date,content&per_page=5").json()
for r in revs: print(r["id"], r["date"], len(r["content"]["raw"]), r["content"]["raw"][-200:].replace("\n"," "))
PY
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" "https://forsmartlife.com/fine-dust-cleansing-routine/"
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" "https://forsmartlife.com/fine-dust-cleansing-routine"
