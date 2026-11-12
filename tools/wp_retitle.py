"""wpflow로 올라온 10월 이후 글 제목 다듬기. 기본은 미리보기(status/audit/retitle-preview.json), --apply 는 미리보기 파일의 제목을 그대로 반영. 주소(slug)는 그대로."""
import base64, json, os, re, sys, html
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
import llm  # noqa: E402
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
F = "status/audit/retitle-preview.json"
if "--apply" in sys.argv:
    prev = json.load(open(F, encoding="utf-8"))
    for x in prev["items"]:
        if not x.get("new") or x["new"] == x["old"]: continue
        r = requests.post(f"{B}/posts/{x['id']}", headers=A, json={"title": x["new"]}, timeout=60)
        x["applied"] = r.status_code < 400
        print(x["id"], r.status_code, x["new"])
    json.dump(prev, open("status/audit/retitle-apply.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit()
P = [p for p in json.load(open("status/audit/posts-dump.json", encoding="utf-8"))["posts"] if p["date"] >= "2026-10-01"]
lst = "\n\n".join(f"[{p['id']}] 제목: {p['title']}\n요약: {p['excerpt'][:200]}\n본문 앞부분: {p['text'][:700]}" for p in P)
res = llm.ask_json("당신은 한국어 건강 블로그 편집자예요. 출력은 JSON 한 덩어리.",
    "아래 글들의 제목을 다듬어 주세요. 지금 제목은 기계 번역처럼 어색해요(예: '~헛걸음을 줄인다', '~알아둘 것', '~지점은 ~다').\n"
    "규칙: 1) 사람들이 네이버·구글에 실제로 치는 핵심 키워드를 앞쪽에. 2) 25~40자, 자연스러운 말투, 질문형이나 '~정리' '~확인할 것' 등 자연스럽게. "
    "3) 본문에 없는 내용·숫자를 지어내지 말고, 과장·낚시 금지(충격, 꼭, 무조건 등). 4) 의미는 원래 제목과 같게. 5) 원래 제목이 이미 자연스러우면 그대로 둬요.\n"
    'JSON: {"items": [{"id": 번호, "new": "새 제목"}]}\n\n' + lst, model="claude-sonnet-5-5", max_tokens=4000)
new = {x["id"]: x["new"] for x in res.get("items", [])}
out = {"usage": llm.USAGE, "items": [{"id": p["id"], "link": p["link"], "old": p["title"], "new": new.get(p["id"], p["title"])} for p in P]}
json.dump(out, open(F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for x in out["items"]: print(x["id"], x["old"], "→", x["new"])
