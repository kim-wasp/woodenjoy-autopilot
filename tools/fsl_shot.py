import sys, time
from playwright.sync_api import sync_playwright
url = "https://forsmartlife.com/flu-vaccine-november-2026-free-eligibility-timing/"
css = open("tools/fsl_post.css").read() if len(sys.argv) > 1 else ""
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w in (("pc", 1280), ("m", 390)):
        pg = b.new_page(viewport={"width": w, "height": 900}, device_scale_factor=1)
        pg.goto(url + f"?v={int(time.time())}", wait_until="networkidle", timeout=90000)
        if css: pg.add_style_tag(content=css)
        t = pg.query_selector("table")
        y = max(0, t.bounding_box()["y"] - 900) if t else 600
        pg.screenshot(path=f"status/audit/fsl/{name}{'-after' if css else ''}.png", clip={"x": 0, "y": y, "width": w, "height": 1800 if w > 400 else 1600}, full_page=True)
        pg.close()
    b.close()
