#!/bin/bash
# 점검용 — Claude WIF 인증 확인 (아주 짧은 호출 1번)
cd engine && python3 - <<'PY'
import os, requests, llm
print("이벤트:", os.environ.get("GITHUB_EVENT_NAME"))
h = llm.auth_headers()
print("방식:", "WIF" if "authorization" in h else "API 키")
r = requests.post("https://api.anthropic.com/v1/messages", timeout=60, headers={**h, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                  json={"model": "claude-haiku-5-5", "max_tokens": 5, "messages": [{"role": "user", "content": "hi"}]})
print("호출 결과:", r.status_code, (r.json().get("error") or {}).get("message", "정상")[:80])
PY
