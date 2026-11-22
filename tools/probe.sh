#!/bin/bash
# 점검용 — 새 Claude API 키 확인 (아주 짧은 호출 1번)
python3 - <<'PY'
import os, requests
r = requests.post("https://api.anthropic.com/v1/models", headers={"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01"}, timeout=30)
r = requests.get("https://api.anthropic.com/v1/models?limit=1", headers={"x-api-key": os.environ.get("ANTHROPIC_API_KEY", ""), "anthropic-version": "2023-06-01"}, timeout=30)
print("키 있음:", bool(os.environ.get("ANTHROPIC_API_KEY")), "/ 응답:", r.status_code, (r.json().get("error") or {}).get("type", "정상") if r.headers.get("content-type", "").startswith("application/json") else "")
PY
