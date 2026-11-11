"""forsmartlife 1단계 정리 (사장님 승인 2026-11-11). 기본은 미리보기, --apply 일 때만 바꿔요.
A 분류 옮기기 / B noindex(Rank Math) / D 본문 맨 위 정사각 썸네일 빼기 / E [이미지…] 자리표시 빼기 / H 작성자 이름, 페이지 제목
워드프레스는 글을 고칠 때마다 이전 버전(리비전)을 남겨서 되돌릴 수 있어요."""
import base64, json, os, re, sys
import requests

BASE, USER = "https://forsmartlife.com", "gracelyun28"
APPLY = "--apply" in sys.argv
tok = base64.b64encode(f"{USER}:{os.environ['WP']}".encode()).decode()
S = requests.Session(); S.headers.update({"Authorization": f"Basic {tok}", "User-Agent": "Mozilla/5.0 (content-studio)"})
API = BASE + "/wp-json/wp/v2"
log = []

def say(*a):
    m = " ".join(str(x) for x in a); print(m); log.append(m)

def post(path, body):
    if not APPLY:
        return {"dry": True}
    r = S.post(API + path, json=body, timeout=90)
    if r.status_code >= 400:
        raise RuntimeError(f"{path} {r.status_code} {r.text[:200]}")
    return r.json()

cats = {c["name"].replace(" ", ""): c["id"] for c in S.get(API + "/categories", params={"per_page": 100}).json()}
CAT = {971: "계절건강", 968: "계절건강", 963: "계절건강", 974: "계절건강", 1038: "계절건강",
       977: "증상관리", 980: "증상관리", 996: "증상관리", 1010: "증상관리", 1013: "증상관리", 1016: "증상관리", 1025: "증상관리",
       1028: "증상관리", 1031: "증상관리", 1035: "증상관리", 989: "건강루틴", 1019: "건강루틴", 1022: "건강루틴"}
NOINDEX = [983, 986, 992, 1000, 1003, 1006]

# A
for pid, c in CAT.items():
    post(f"/posts/{pid}", {"categories": [cats[c]]}); say("A 분류", pid, "→", c)

# B: Rank Math 메타 (REST 로 rank_math_robots 를 받는지 확인 후, 안 되면 Rank Math updateMeta)
for pid in NOINDEX:
    if not APPLY:
        say("B noindex 예정", pid); continue
    ok = False
    r = S.post(BASE + "/wp-json/rankmath/v1/updateMeta", json={"objectType": "post", "objectID": pid, "meta": {"rank_math_robots": ["noindex", "follow"]}}, timeout=60)
    if r.status_code < 400:
        ok = True
    else:
        r2 = S.post(API + f"/posts/{pid}", json={"meta": {"rank_math_robots": ["noindex", "follow"]}}, timeout=60)
        ok = r2.status_code < 400 and "noindex" in json.dumps(r2.json().get("meta", {}))
    h = requests.get(f"{BASE}/?p={pid}", timeout=60, headers={"User-Agent": "Mozilla/5.0"}).text
    robots = (re.search(r'<meta name="robots" content="([^"]+)"', h) or [None, ""])[1]
    say("B noindex", pid, "요청", "성공" if ok else f"실패 {r.status_code}", "| 공개 화면:", robots)

# D, E
THUMB = re.compile(r"_0?1-1024x1024\.(png|jpe?g|webp)", re.I)
def strip_thumb(raw):
    # 블록(<!-- wp:image -->) 통째로, 아니면 <figure>, 아니면 <img> 를 담은 문단
    for pat in [r"<!-- wp:image[^>]*-->\s*<figure[^>]*>(?:(?!</figure>).)*?{THUMB}(?:(?!</figure>).)*?</figure>\s*<!-- /wp:image -->",
                r"<figure[^>]*>(?:(?!</figure>).)*?{THUMB}(?:(?!</figure>).)*?</figure>",
                r"<p[^>]*>\s*(?:<a[^>]*>)?\s*<img[^>]*{THUMB}[^>]*>\s*(?:</a>)?\s*</p>",
                r"<img[^>]*{THUMB}[^>]*>"]:
        rx = re.compile(pat.replace("{THUMB}", THUMB.pattern), re.S | re.I)
        new, n = rx.subn("", raw, count=1)
        if n:
            return new, pat[:18]
    return raw, None
PH = re.compile(r"(<!-- wp:paragraph[^>]*-->\s*)?<p[^>]*>\s*\[(?:이미지|사진|IMAGE)[^\]]*\]\s*</p>(\s*<!-- /wp:paragraph -->)?|\[(?:이미지|사진|IMAGE)[^\]]{0,80}\]", re.I)
page = 1; nd = ne = 0
while True:
    r = S.get(API + "/posts", params={"per_page": 50, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json(): break
    for p in r.json():
        raw = p["content"]["raw"]; new = raw; ch = []
        if p["date"] < "2026-10":
            new, how = strip_thumb(new)
            if how: ch.append(f"D 썸네일({how})")
        new2, k = PH.subn("", new)
        if k: ch.append(f"E 자리표시 {k}개"); new = new2
        if new != raw:
            post(f"/posts/{p['id']}", {"content": new})
            nd += any(c.startswith("D") for c in ch); ne += any(c.startswith("E") for c in ch)
            say(p["id"], p["date"], " / ".join(ch))
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
say(f"D 썸네일 뺀 글 {nd}개, E 자리표시 뺀 글 {ne}개")

# H
post("/users/1", {"name": "WellnessNote 편집팀", "nickname": "WellnessNote 편집팀"}); say("H 작성자 이름 → WellnessNote 편집팀")
TITLES = {"about": "소개", "contact": "문의", "editorial-policy": "편집 원칙", "medical-disclaimer": "의료 정보 고지", "terms-of-service": "이용약관"}
for pg in S.get(API + "/pages", params={"per_page": 50, "context": "edit"}).json():
    if pg["slug"] in TITLES:
        post(f"/pages/{pg['id']}", {"title": TITLES[pg["slug"]]}); say("H 페이지", pg["slug"], "→", TITLES[pg["slug"]])
os.makedirs("status/audit", exist_ok=True)
json.dump(log, open(f"status/audit/forsmartlife-cleanup-{'apply' if APPLY else 'dry'}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
