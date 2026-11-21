#!/bin/bash
python3 - <<'PY'
import re, requests
for s in ["dongchungcho-med-interaction-check", "red-ginseng-sugar-label", "san-yang-sam-purchase-history-quality"]:
    h = requests.get(f"https://forsmartlife.com/{s}/", headers={"User-Agent": "Googlebot"}, timeout=30).text
    rob = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)', h)
    t = re.search(r"<title>([^<]+)", h)
    print(s, "|", rob.group(1) if rob else "-", "|", t.group(1)[:50] if t else "")
PY
