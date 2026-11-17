#!/bin/bash
pip install -q playwright >/dev/null 2>&1 && python3 -m playwright install --with-deps chromium >/dev/null 2>&1
mkdir -p status/shots
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 700}); pg.goto("https://forsmartlife.com/?v=2", wait_until="networkidle"); pg.screenshot(path="status/shots/v_home.png"); pg.close()
    pg = b.new_page(viewport={"width": 390, "height": 900}); pg.goto("https://forsmartlife.com/flu-weekly/?v=2", wait_until="networkidle")
    pg.locator(".cm").screenshot(path="status/shots/v_flu_m.png"); pg.close()
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.goto("https://forsmartlife.com/norovirus-symptoms-prevention-disinfection/?v=2", wait_until="networkidle")
    pg.locator(".sig-myth").screenshot(path="status/shots/v_myth.png"); pg.close()
    pg = b.new_page(viewport={"width": 1280, "height": 900}); pg.goto("https://sisibibinote.kr/posts/fabricated-indictment-special-counsel-cabinet-dead/?v=2", wait_until="networkidle")
    pg.locator(".sig-verdict").screenshot(path="status/shots/v_verdict.png")
    if pg.locator(".sig-bill").count(): pg.locator(".sig-bill").screenshot(path="status/shots/v_bill.png")
    pg.close(); b.close()
PY
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status && git commit -qm "확인 화면" && git pull -q --rebase && git push -q
