"""forsmartlife 글 전체 등급: 애드센스 '가치 없는 콘텐츠' 관점에서 남김/보강/검색 제외 추천 (읽기만, 반영 안 함)"""
import base64, json, os, re, sys, html
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
import llm  # noqa: E402
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
cats = {1: "계절 건강", 3: "건강 루틴", 4: "증상 관리"}
posts, page = [], 1
while True:
    r = requests.get(B + "/posts", headers=A, params={"per_page": 25, "page": page, "context": "edit", "status": "publish"}, timeout=90)
    if r.status_code != 200 or not r.json(): break
    for p in r.json():
        raw = p["content"]["raw"]
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()
        links = re.findall(r'href="(https?://[^"]+)"', raw)
        off = [l for l in links if "forsmartlife.com" not in l]
        posts.append({"id": p["id"], "date": p["date"][:10], "title": p["title"]["raw"], "link": p["link"], "cat": cats.get((p["categories"] or [0])[0], ""),
                      "chars": len(t), "ext_links": len(off), "gov_links": len([l for l in off if re.search(r"\.go\.kr|who\.int|nih\.gov|kdca|mfds|nhis|\.or\.kr", l)]),
                      "robots": (p.get("meta") or {}).get("rank_math_robots"), "text": t})
    if page >= int(r.headers.get("X-WP-TotalPages", 1)): break
    page += 1
print("글", len(posts))
SYS = "당신은 구글 애드센스 정책과 건강 정보(YMYL) 품질을 잘 아는 편집 심사자예요. 출력은 JSON 한 덩어리."
RULE = """아래 건강 블로그 글들을 애드센스 '가치가 별로 없는 콘텐츠' 거절을 벗어나는 관점에서 평가해요. 사이트 평균 품질을 올리려고, 약한 글은 검색에서 빼거나(noindex) 보강할 거예요.
점수(1~5): 5=독자에게 분명한 고유 가치(구체적 기준·수치·판단표, 공식 출처), 충분한 깊이 / 4=좋음 / 3=평범하지만 정확, 흔한 내용 / 2=얇거나 뻔함, 일반론 반복, 출처 약함 / 1=거의 가치 없음, 근거 약한 효능 주장, 상품·식품 홍보성, 의학적으로 위험할 수 있음.
action: keep(그대로) / improve(주제는 좋은데 보강하면 좋음) / noindex(검색 제외 추천).
판단 기준: 같은 주제를 다른 글이 더 잘 다루면 noindex 쪽으로. 특정 식품·영양제 효능을 부풀린 글, 근거가 약한 '~에 좋은 음식 N가지'류, 날짜가 지나 쓸모가 없어진 시사성 글은 낮게. 질병관리청 등 공식 기준을 정리한 실용 글은 높게.
각 글: {"id":번호,"score":1~5,"action":"keep|improve|noindex","topic":"주제 묶음 이름(2~4단어, 비슷한 글끼리 같은 이름)","reason":"한 줄 이유(30자 안팎)"}
출력: {"items":[...]}"""
out = []
for i in range(0, len(posts), 6):
    batch = posts[i:i + 6]
    prompt = RULE + "\n\n" + "\n\n".join(f"[id {p['id']}] {p['date']} / {p['cat']} / {p['chars']}자 / 외부링크 {p['ext_links']}(공공기관 {p['gov_links']})\n제목: {p['title']}\n본문: {p['text'][:2800]}" for p in batch)
    try:
        res = llm.ask_json(SYS, prompt, model="claude-sonnet-5-5", max_tokens=2500)
        out += res.get("items", [])
    except Exception as e:  # noqa: BLE001
        print("오류", e); break
by = {x["id"]: x for x in out}
rows = [{**{k: v for k, v in p.items() if k != "text"}, **{k: by.get(p["id"], {}).get(k) for k in ("score", "action", "topic", "reason")}} for p in posts]
json.dump({"usage": llm.USAGE, "rows": rows}, open("status/audit/grade.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(r["action"] for r in rows), llm.USAGE)
