"""forsmartlife C/F 작업: 지어낸 1인칭 경험담 문장을 일반 설명으로 바꾸고, 위키백과 출처를 공식 기관 출처로 바꿔요.
  python3 tools/wp_rewrite_fp.py --ids 9,27,110          미리보기 (전후를 status/audit/rewrite-preview.json 으로)
  python3 tools/wp_rewrite_fp.py --all --apply            전체 반영 (3~5월 글)
바뀌는 건 경험담이 든 문단과 위키백과 링크뿐이에요. 워드프레스 리비전으로 되돌릴 수 있어요."""
import base64, json, os, re, sys
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
import llm  # noqa: E402

BASE, USER = "https://forsmartlife.com", "gracelyun28"
API = BASE + "/wp-json/wp/v2"
tok = base64.b64encode(f"{USER}:{os.environ['WP']}".encode()).decode()
S = requests.Session(); S.headers.update({"Authorization": f"Basic {tok}", "User-Agent": "Mozilla/5.0 (content-studio)"})
APPLY = "--apply" in sys.argv
FP = re.compile(r"(?<![가-힣])(저도|저는|제가|저희|제 경험|제 주변|내가|나도)|(해보니|써보니|먹어보니|겪어보니|마셔보니)")
BLOCK = re.compile(r"<(p|li|blockquote|td)\b[^>]*>(?:(?!</\1>).)*?</\1>", re.S)
SYSTEM = "당신은 건강 정보 블로그의 사실 확인 편집자예요. 출력은 JSON 한 덩어리."
RULE = """아래 HTML 조각들은 건강 블로그 글의 일부예요. 운영자가 실제로 겪지 않은 '1인칭 경험담'(저도, 저는, 제가, 해보니 등)과 위키백과 링크를 고쳐야 해요.
규칙:
1) 1인칭 경험담은 지어낸 것으로 보고 없애요. 정보가 담긴 부분은 '이런 경우가 많아요', '~하는 사람이 많아요'처럼 일반 설명으로 바꾸고, 정보 없이 경험만 있는 문장은 지워요.
2) 사실, 숫자, 권고 내용은 바꾸지 말아요. 새 정보를 지어내지 말아요.
3) HTML 태그 구조(<p>, <strong>, <a> 등)는 유지해요. 조각이 통째로 지워져야 하면 빈 문자열.
4) 위키백과 링크(<a href=...wikipedia...>)는 같은 내용의 공식 기관 페이지(질병관리청 health.kdca.go.kr, 국가건강정보포털, 식약처 mfds.go.kr, WHO, NIH 등) 주소를 확실히 알 때만 바꾸고, 확실하지 않으면 링크만 없애고 글자는 남겨요. 존재가 불확실한 주소를 만들지 말아요.
5) 말투(해요체)는 원문과 맞춰요.
출력: {"edits": [{"i": 조각 번호, "html": "고친 HTML 조각"}]}  (고칠 필요 없는 조각은 빼요)"""

def targets(raw):
    out = []
    for m in BLOCK.finditer(raw):
        b = m.group(0)
        txt = re.sub(r"<[^>]+>", "", b)
        if FP.search(txt) or "wikipedia.org" in b:
            out.append(b)
    return out

def rewrite(p):
    raw = p["content"]["raw"]
    blocks = targets(raw)
    if not blocks:
        return raw, []
    prompt = RULE + "\n\n[글 제목] " + p["title"]["raw"] + "\n\n" + "\n\n".join(f"[{i}]\n{b}" for i, b in enumerate(blocks))
    res = llm.ask_json(SYSTEM, prompt, model="claude-sonnet-5-5", web_search=False, max_tokens=8000)
    new, changes = raw, []
    for e in res.get("edits", []):
        i = e.get("i")
        if not isinstance(i, int) or i >= len(blocks): continue
        before, after = blocks[i], e.get("html", "")
        if before in new and before != after:
            new = new.replace(before, after, 1)
            changes.append({"before": re.sub(r"<[^>]+>", "", before)[:300], "after": re.sub(r"<[^>]+>", "", after)[:300]})
    return new, changes

ids = []
for a in sys.argv:
    if a.startswith("--ids"): pass
if "--ids" in sys.argv:
    ids = [int(x) for x in sys.argv[sys.argv.index("--ids") + 1].split(",")]
posts = []
if ids:
    posts = [S.get(f"{API}/posts/{i}", params={"context": "edit"}, timeout=60).json() for i in ids]
else:
    page = 1
    while True:
        r = S.get(API + "/posts", params={"per_page": 50, "page": page, "context": "edit", "before": "2026-10-01T00:00:00"}, timeout=90)
        if r.status_code != 200 or not r.json(): break
        posts += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
        page += 1
report = []
for p in posts:
    try:
        new, ch = rewrite(p)
    except Exception as e:  # noqa: BLE001
        report.append({"id": p["id"], "error": str(e)[:200]}); print("오류", p["id"], e); continue
    left = len([1 for b in targets(new) if FP.search(re.sub(r"<[^>]+>", "", b))])
    report.append({"id": p["id"], "title": p["title"]["raw"], "link": p["link"], "changes": ch, "first_person_left": left, "wiki_left": new.count("wikipedia.org")})
    print(p["id"], p["title"]["raw"][:40], "바꾼 문단", len(ch), "남은 경험담", left, "남은 위키", new.count("wikipedia.org"))
    if APPLY and ch:
        r = S.post(f"{API}/posts/{p['id']}", json={"content": new}, timeout=90)
        if r.status_code >= 400: print("  반영 실패", r.status_code, r.text[:200])
os.makedirs("status/audit", exist_ok=True)
json.dump({"apply": APPLY, "usage": llm.USAGE, "report": report}, open(f"status/audit/rewrite-{'apply' if APPLY else 'preview'}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("비용(토큰)", llm.USAGE)
