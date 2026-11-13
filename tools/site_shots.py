import re, time, json
from playwright.sync_api import sync_playwright
B = "https://forsmartlife.com"
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, path, w, h in [("home-pc", "/", 1280, 1500), ("home-mobile", "/", 390, 1700), ("about", "/about/", 1280, 2200), ("post-pc", "/flu-vaccine-november-2026-free-eligibility-timing/", 1280, 4200), ("post-mobile", "/flu-vaccine-november-2026-free-eligibility-timing/", 390, 5000), ("wf-pc", "/pneumococcal-vaccine-history-check/", 1280, 4200)]:
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto(B + path + f"?v={int(time.time())}", wait_until="networkidle", timeout=90000)
        pg.screenshot(path=f"status/audit/shots/{name}.png")
        out[name] = {"title": pg.title(), "desc": pg.eval_on_selector('meta[name="description"]', "e => e.content") if pg.query_selector('meta[name="description"]') else None,
                     "h1": [x.inner_text() for x in pg.query_selector_all("h1")]}
        pg.close()
    b.close()
json.dump(out, open("status/audit/shots/info.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(out)
