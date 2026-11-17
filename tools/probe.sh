#!/bin/bash
python3 tools/fsl_pages.py home
python3 tools/sig_backfill.py sisibibi --apply
python3 - <<'PY'
import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
import fsl_merge as m; print("캐시", m.clear_cache())
PY
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1
mkdir -p status/shots
python3 - <<'PY'
from playwright.sync_api import sync_playwright
urls = {"fsl_home": "https://forsmartlife.com/", "fsl_flu": "https://forsmartlife.com/flu-weekly/", "fsl_calc": "https://forsmartlife.com/health-calculators/",
        "fsl_post": "https://forsmartlife.com/daily-water-intake/"}
with sync_playwright() as p:
    b = p.chromium.launch()
    for n, u in urls.items():
        for tag, w in (("d", 1280), ("m", 390)):
            pg = b.new_page(viewport={"width": w, "height": 900}); pg.goto(u + "?v=1", wait_until="networkidle", timeout=60000)
            pg.screenshot(path=f"status/shots/{n}_{tag}.png", full_page=True); pg.close()
    b.close()
PY
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status && git commit -qm "확인 화면" && git pull -q --rebase && git push -q
