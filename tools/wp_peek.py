import base64, json, os, re, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
out = {}
for i in (1038, 1000, 9, 1447):
    p = requests.get(f"{B}/posts/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    raw = p["content"]["raw"]
    m = requests.get(f"{B}/media/{p['featured_media']}", headers=A, timeout=60).json() if p.get("featured_media") else {}
    out[i] = {"styles": re.findall(r'style="[^"]{0,120}"', raw)[:8], "classes": sorted(set(re.findall(r'class="([^"]{0,60})"', raw)))[:30],
              "head": raw[:1200], "featured": m.get("source_url"), "tables": re.findall(r"<table[^>]*>", raw)[:2]}
w = requests.get(f"{B}/widgets", headers=A, params={"per_page": 100}, timeout=60).json()
out["widgets"] = [(x["id"], x["sidebar"], (x.get("instance") or {}).get("raw", {}).get("content", "")[:200] if isinstance(x.get("instance"), dict) else "") for x in w]
h = requests.get("https://forsmartlife.com/?v=1", timeout=60).text
out["custom_css"] = re.findall(r'<style id="wp-custom-css">(.*?)</style>', h, re.S)
json.dump(out, open("status/audit/peek.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
