import base64, json, os, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
out = {}
for i in (18, 807, 3, 717, 811, 16, 11):
    p = requests.get(f"{B}/pages/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    out[i] = {"raw": p["content"]["raw"], "meta": p.get("meta"), "modified": p.get("modified")}
out["me"] = requests.get(f"{B}/users/me", headers=A, params={"context": "edit"}, timeout=60).json().get("description")
out["plugins"] = [(x["plugin"], x["name"]) for x in requests.get(f"{B}/plugins", headers=A, timeout=60).json()]
json.dump(out, open("status/audit/pages-raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok")
