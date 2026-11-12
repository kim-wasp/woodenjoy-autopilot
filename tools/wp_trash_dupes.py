"""중복 글을 휴지통으로 (영구 삭제 아님) + 다른 글의 내부 링크를 남기는 글로 바꾸기"""
import base64, json, os, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
MAP = {125: 127, 31: 74, 29: 39}  # 지울 글 → 남길 글
url = {i: requests.get(f"{B}/posts/{i}", headers=A, timeout=60).json()["link"] for i in list(MAP) + list(MAP.values())}
log = {"map": MAP, "urls": url, "relinked": [], "trashed": []}
page = 1
while True:
    r = requests.get(B + "/posts", headers=A, params={"per_page": 25, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json(): break
    for p in r.json():
        if p["id"] in MAP: continue
        raw, new = p["content"]["raw"], p["content"]["raw"]
        for old, keep in MAP.items():
            for u in {url[old], url[old].rstrip("/")}:
                new = new.replace(f'href="{u}"', f'href="{url[keep]}"').replace(f'href="{u}/"', f'href="{url[keep]}"')
        if new != raw:
            rr = requests.post(f"{B}/posts/{p['id']}", headers=A, json={"content": new}, timeout=90)
            log["relinked"].append([p["id"], rr.status_code]); print("링크 바꿈", p["id"], rr.status_code)
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
for i in MAP:
    rr = requests.delete(f"{B}/posts/{i}", headers=A, timeout=60)  # force 없음 = 휴지통
    log["trashed"].append([i, rr.status_code, rr.json().get("status")]); print("휴지통", i, rr.status_code, rr.json().get("status"))
json.dump(log, open("status/audit/dupes-trash.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
