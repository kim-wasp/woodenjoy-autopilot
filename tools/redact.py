"""공개 기록(studio-logs 가지)에 올리기 전에 로그에서 비밀값을 지워요.
GitHub 화면 로그는 비밀값을 자동으로 가리지만, 파일로 저장한 로그는 가려지지 않아요.
  python3 tools/redact.py <로그 파일>   (그 자리에서 고침)
"""
import json
import os
import re
import sys
from pathlib import Path

vals = set()
for k, v in os.environ.items():
    if re.search(r"TOKEN|KEY|SECRET|PASS|PAT\b", k) and v and len(v) >= 8:
        vals.add(v)
try:
    for v in json.loads(os.environ.get("ALL_SECRETS") or "{}").values():
        if isinstance(v, str) and len(v) >= 8:
            vals.add(v)
except json.JSONDecodeError:
    pass
for f in sys.argv[1:]:
    p = Path(f)
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    for v in sorted(vals, key=len, reverse=True):
        t = t.replace(v, "***")
    t = re.sub(r"(access_token|client_secret|apikey|api_key|code)=([^&\s\"']{8,})", r"\1=***", t)
    t = re.sub(r"(Bearer|Basic)\s+[A-Za-z0-9._\-+/=]{12,}", r"\1 ***", t)
    p.write_text(t, encoding="utf-8")
