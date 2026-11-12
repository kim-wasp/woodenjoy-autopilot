"""forsmartlife: 근거 없이 단정하는 문장(효과·빈도·기간·후기성 일반화, 상품 권유)만 찾아 안내형 문장으로 고쳐요.
  python3 tools/wp_rewrite_claims.py --ids 663,608        미리보기 (status/audit/claims-preview.json)
  python3 tools/wp_rewrite_claims.py --all --apply         전체 반영 (원문은 status/audit/claims-backup.json)"""
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
SYSTEM = "당신은 건강 정보 블로그의 사실 확인 편집자예요. 고칠 곳이 적으면 적게 고치는 게 좋은 편집이에요. 출력은 JSON 한 덩어리."
RULE = """아래는 건강 블로그 글의 문단·목록·표 칸을 번호 붙여 나열한 거예요. 근거 없이 단정하는 문장만 골라 고쳐 주세요. 대부분의 조각은 고칠 필요가 없어요.
고칠 것 (이런 문장만):
a) 출처 없이 효과·결과를 장담: '확실히 도움이 돼요', '먹으면 확실히 줄어요', '큰 손해예요', '효과를 본 케이스가 많아요', '임상 사례가 많아요', '대부분 좋아져요'
b) 근거 없는 기간·빈도 약속: '2주면 좋아져요', '바로 효과가 나타나요'
c) 후기·입소문처럼 들리는 일반화: '먹어본 분들은 다 만족해요', '주변에서 효과 봤다는 분이 많아요'
d) 특정 상품·브랜드 구매 권유
e) 글쓴이가 겪은 일처럼 들리는 경험 말투: '~더라고요', '~했었어요', '꺼려지더라고요' → 경험 표현을 빼고 일반 설명('~할 수 있어요')으로
고치는 법: 장담을 빼고 '~에 도움이 될 수 있어요', '~해 보세요', '개인차가 있어요'처럼 안내하는 말로. 정보 없이 장담만 있는 문장은 지워요.
하지 말 것: 사실·숫자·기관 권고·출처 링크는 바꾸지 않아요. 새 정보를 지어내지 않아요. '무조건 ~하지는 않아요'처럼 이미 단정을 부정하는 문장, FAQ 질문 문장, 위험 신호·병원 안내는 그대로 둬요. HTML 태그 구조와 해요체/합니다체 말투는 원문 그대로.
출력: {"edits": [{"i": 조각 번호, "html": "고친 HTML 조각", "why": "a/b/c/d 중 무엇"}]} (고칠 게 없으면 빈 목록)"""

def targets(raw):
    out = []
    for m in BLOCK.finditer(raw):
        b = m.group(0)
        txt = re.sub(r"<[^>]+>", "", b)
        if len(txt.strip()) >= 15:
            out.append(b)
    return out

def rewrite(p):
    raw = p["content"]["raw"]
    blocks = targets(raw)
    if not blocks:
        return raw, []
    prompt = RULE + "\n\n[글 제목] " + p["title"]["raw"] + "\n\n" + "\n\n".join(f"[{i}]\n{b}" for i, b in enumerate(blocks))
    res = llm.ask_json(SYSTEM, prompt, model="claude-sonnet-5-5", web_search=False, max_tokens=6000)
    new, changes = raw, []
    for e in res.get("edits", []):
        i = e.get("i")
        if not isinstance(i, int) or i >= len(blocks): continue
        before, after = blocks[i], e.get("html", "")
        if before in new and before != after:
            new = new.replace(before, after, 1)
            changes.append({"why": e.get("why", ""), "before": re.sub(r"<[^>]+>", "", before)[:300], "after": re.sub(r"<[^>]+>", "", after)[:300]})
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
        r = S.get(API + "/posts", params={"per_page": 25, "page": page, "context": "edit", "status": "publish"}, timeout=90)
        if r.status_code != 200 or not r.json(): break
        posts += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
        page += 1
report = []
backup = {}
for p in posts:
    try:
        new, ch = rewrite(p)
    except Exception as e:  # noqa: BLE001
        report.append({"id": p["id"], "error": str(e)[:200]}); print("오류", p["id"], e); continue
    left = 0
    report.append({"id": p["id"], "title": p["title"]["raw"], "link": p["link"], "changes": ch, "first_person_left": left, "wiki_left": new.count("wikipedia.org")})
    print(p["id"], p["title"]["raw"][:40], "바꾼 문단", len(ch), "남은 경험담", left, "남은 위키", new.count("wikipedia.org"))
    if APPLY and ch:
        backup[p["id"]] = p["content"]["raw"]
        r = S.post(f"{API}/posts/{p['id']}", json={"content": new}, timeout=90)
        report[-1]["applied"] = r.status_code < 400
        if r.status_code >= 400: print("  반영 실패", r.status_code, r.text[:200])
os.makedirs("status/audit", exist_ok=True)
json.dump({"apply": APPLY, "usage": llm.USAGE, "report": report}, open(f"status/audit/claims-{'apply' if APPLY else 'preview'}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if backup:
    json.dump(backup, open("status/audit/claims-backup.json", "w", encoding="utf-8"), ensure_ascii=False)
print("비용(토큰)", llm.USAGE)
