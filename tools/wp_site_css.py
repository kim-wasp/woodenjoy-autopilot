"""사이트 전체 CSS를 워드프레스 footer-bar 위젯(<style>)으로 넣거나 바꿔요. 원래대로: --remove
  python3 tools/wp_site_css.py forsmartlife"""
import base64, json, os, re, sys
import requests
site = sys.argv[1]
cfg = json.load(open(f"sites/{site}/site.json"))
B = cfg["blog"]["url"].rstrip("/") + "/wp-json/wp/v2"
user = cfg["blog"]["wordpress"]["user"]
A = {"Authorization": "Basic " + base64.b64encode(f"{user}:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
css = open(f"sites/{site}/theme.css", encoding="utf-8").read()
content = f'<!-- wp:html -->\n<style id="wn-site-style">\n{css}\n</style>\n<!-- /wp:html -->'
ws = requests.get(f"{B}/widgets", headers=A, params={"per_page": 100, "context": "edit"}, timeout=60).json()
mine = [w for w in ws if "wn-site-style" in json.dumps(w.get("instance") or {}, ensure_ascii=False)]
if "--remove" in sys.argv:
    for w in mine:
        print("지우기", w["id"], requests.delete(f"{B}/widgets/{w['id']}", headers=A, params={"force": "true"}, timeout=60).status_code)
    sys.exit()
body = {"id_base": "block", "sidebar": "footer-bar", "instance": {"raw": {"content": content}}}
if mine:
    r = requests.put(f"{B}/widgets/{mine[0]['id']}", headers=A, json=body, timeout=60); print("바꾸기", mine[0]["id"], r.status_code, r.text[:200] if r.status_code >= 300 else "")
else:
    r = requests.post(f"{B}/widgets", headers=A, json=body, timeout=60); print("새로 넣기", r.status_code, r.json().get("id") if r.ok else r.text[:300])
# 대표 이미지가 숨겨진 사이트라, 본문에 대표 사진이 없는 스튜디오 글에 넣어요
for i in [int(x) for x in os.environ.get("HERO_FIX", "").split(",") if x]:
    p = requests.get(f"{B}/posts/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    raw = p["content"]["raw"]
    if "wn-hero" in raw or not p.get("featured_media"):
        continue
    m = requests.get(f"{B}/media/{p['featured_media']}", headers=A, timeout=60).json()
    fig = f'<figure class="wp-block-image size-large wn-hero"><img src="{m["source_url"]}" alt="{p["title"]["raw"]}"/></figure>'
    new = re.sub(r"(</blockquote>)", r"\1\n" + fig.replace("\\", "\\\\"), raw, count=1) if "</blockquote>" in raw else fig + "\n" + raw
    print("대표 사진 본문에", i, requests.post(f"{B}/posts/{i}", headers=A, json={"content": new}, timeout=60).status_code)
