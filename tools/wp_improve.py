"""forsmartlife 글 보강: 공식 자료를 웹 검색으로 찾아 같은 주제로 다시 써요 (원문은 status/audit/improve-backup.json)"""
import base64, json, os, re, sys, html
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
import llm, sources  # noqa: E402
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
site = json.load(open("sites/forsmartlife/site.json", encoding="utf-8"))
SYS = "당신은 질병관리청·국가건강정보포털 자료로 글을 쓰는 건강 정보 블로그 편집자예요. 출력은 JSON 한 덩어리."
RULE = """아래 글을 같은 주제로 더 쓸모 있게 다시 써 주세요. 웹 검색으로 질병관리청, 국가건강정보포털(health.kdca.go.kr), 예방접종도우미(nip.kdca.go.kr), 건강보험공단, 관련 학회 같은 공식 자료를 확인하고, 숫자·기준은 그 자료에 있는 것만 써요.
사이트 규칙: """ + site["writing_guide"] + """
형식(워드프레스 HTML, 인라인 style 금지, 이모지 금지):
- 첫 줄 <blockquote><p><strong>한 줄 결론:</strong> …</p></blockquote>
- <h2> 질문형 소제목 4~6개, 각 짧은 문단 또는 <ul> 목록
- 표 1개 이상(<table><thead>…</thead><tbody>…</tbody></table>, 기준·비교를 한눈에)
- 확인 목록 1개(<ul>)
- '바로 진료받아야 하는 경우'를 따로 한 칸
- <h2>자주 묻는 질문</h2> Q 2~3개
- 마지막 <h2>참고 자료</h2> <ul><li><a href="공식 자료 주소">자료 이름</a></li></ul> 3~6개 (실제로 열어 본 주소만)
- 2,500~3,500자, 체험담·근거 없는 장담 금지, 기존 글의 좋은 정보는 살리되 틀린 건 고쳐요
JSON: {"title": "제목(핵심 검색어 앞쪽, 40자 안팎, 과장 없이)", "excerpt": "검색 설명 80~140자", "html": "본문 HTML", "notes": "원문에서 고친 사실 한두 줄"}"""
backup, out = {}, []
for i in [int(x) for x in os.environ["IDS"].split(",")]:
    p = requests.get(f"{B}/posts/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    raw = p["content"]["raw"]
    backup[i] = {"title": p["title"]["raw"], "content": raw, "excerpt": p["excerpt"]["raw"]}
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    res = llm.ask_json(SYS, RULE + f"\n\n[원래 제목] {p['title']['raw']}\n[원문]\n{t[:7000]}", model="claude-opus-5-5", web_search=True, max_tokens=12000, max_searches=8)
    h = res.get("html", "")
    dead = [u for u in set(re.findall(r'href="(https?://[^"]+)"', h)) if not sources.alive(u)]
    for u in dead:  # 열리지 않는 링크는 글자만 남겨요
        h = re.sub(r'<a [^>]*href="' + re.escape(u) + r'"[^>]*>(.*?)</a>', r"\1", h, flags=re.S)
    n = len(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)))
    body = {"content": h, "title": res.get("title") or p["title"]["raw"], "excerpt": res.get("excerpt", "")}
    r = requests.post(f"{B}/posts/{i}", headers=A, json=body, timeout=60)
    out.append({"id": i, "status": r.status_code, "old_title": p["title"]["raw"], "new_title": body["title"], "chars": n, "dead_removed": dead, "notes": res.get("notes")})
    print(i, r.status_code, n, "자", body["title"], "| 뺀 링크", len(dead))
json.dump(backup, open("status/audit/improve-backup.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"usage": llm.USAGE, "items": out}, open("status/audit/improve.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(llm.USAGE)
