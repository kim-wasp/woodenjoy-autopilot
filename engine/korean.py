"""한국어 AI 티 점검·교정 (블로그·스레드·인스타 공통)

- scan(text): tools/korean/count_patterns.py (airoasting/korean, MIT) 로 AI 티 패턴을 세고 + 흔한 맞춤법 오류를 찾아요. 돈 안 들어요.
- fix(texts, ...): 걸린 자리만 Claude 에게 고치게 해요 (걸린 게 없으면 부르지 않아요).
- polish_sns(site, post): 스레드 글·인스타 캡션을 점검하고 걸리면 고쳐요.
규칙: skills/korean-natural/SKILL.md (공개 스킬 4개를 묶어 줄인 것)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, log  # noqa: E402
import llm  # noqa: E402
import skills  # noqa: E402

COUNTER = ROOT / "tools" / "korean" / "count_patterns.py"
SPELL = [  # (틀린 꼴, 바른 꼴)
    (r"(?<![가-힣])되요", "돼요"), (r"됬", "됐"), (r"안되요", "안 돼요"), (r"몇일", "며칠"), (r"어떻해", "어떡해"),
    (r"왠일", "웬일"), (r"왠만하면", "웬만하면"), (r"할수 ?있", "할 수 있"), (r"할수 ?없", "할 수 없"),
    (r"(?<![가-힣])않 ?(?:해|가|돼|되)", "안 해/안 가"), (r"금새", "금세"), (r"역활", "역할"), (r"설겆이", "설거지"),
    (r"(?<![가-힣])뵈요", "봬요"), (r"오랫만", "오랜만"), (r"희안", "희한"), (r"어의없", "어이없"), (r"일일히", "일일이"),
]


def rules(limit=9000):
    return skills.text("korean-natural", limit)


def scan(text, choppy=True):
    """{'grade','score','fatal','spots':[...]} — spots 는 고칠 자리 설명"""
    if not text or not text.strip():
        return {"grade": "A", "score": 10, "fatal": 0, "spots": []}
    try:
        r = subprocess.run([sys.executable, "-I", str(COUNTER), "--json"], input=text, capture_output=True, text=True, timeout=60)
        j = json.loads(r.stdout)
    except Exception as e:  # noqa: BLE001
        log(f"  AI 티 측정기 오류: {e}")
        return {"grade": "?", "score": None, "fatal": 0, "spots": []}
    spots = []
    for p in (j.get("patterns") or {}).values():
        for m in (p.get("matches") or [])[:3]:
            spots.append(f"{p.get('name')}: '{m[:80]}'")
    for s in j.get("ai_signature") or []:
        spots.append(f"AI 상투: {s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)[:80]}")
    if j.get("emdash"):
        spots.append(f"줄표(—, –) {j['emdash']}개 → 마침표·쉼표·쌍점으로")
    for bad, good in SPELL:
        for m in re.finditer(bad, text):
            spots.append(f"맞춤법: '{text[max(0, m.start() - 8):m.end() + 6]}' ({m.group(0)} → {good})")
    for run in (choppy_runs(text) if choppy else []):
        spots.append(f"끊기는 문장 {len(run)}개 연달아 → 이어지는 생각은 ~고/~는데/~라서로 묶기: '{' '.join(run)[:90]}'")
    spell = sum(1 for s in spots if s.startswith("맞춤법") or s.startswith("끊기는"))
    return {"grade": j.get("grade", "?"), "score": j.get("score"), "fatal": (j.get("L3") or 0) + (j.get("emdash") or 0) + spell,
            "warn": j.get("L2") or 0, "spots": spots[:20]}


def choppy_runs(text, short=32, n=4):
    """문단 안에서 짧은 문장(공백 빼고 short자 미만)이 n개 넘게 연달아 나오는 곳. 목록·표·제목·HTML 줄은 빼요"""
    out = []
    for para in re.split(r"\n\s*\n", text or ""):
        lines = [l for l in para.split("\n") if l.strip() and not re.match(r"\s*([-*#>|<]|\d+[.)]|\[\[)", l)]
        sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", " ".join(lines)) if x.strip()]
        run = []
        for x in sents + [""]:
            if x and len(re.sub(r"\s", "", x)) < short:
                run.append(x)
                continue
            if len(run) >= n:
                out.append(run)
            run = []
    return out[:3]


def needs_fix(s):
    return s["fatal"] > 0 or str(s.get("grade", "A"))[:1] in ("C", "D")


def _keep_marks(text):
    return set(re.findall(r"\[\[[^\]]+\]\]|\{LINK\}|https?://[^\s)]+|\d[\d,.]*", text or ""))


def fix(texts, tone, model, spots_by_key):
    """texts: {키: 글}. 걸린 자리만 문장 단위로 고쳐서 돌려줘요. 사실·숫자·링크가 빠지면 그 글은 원래대로."""
    prompt = "\n\n".join([
        "아래 글들에서 [걸린 자리]만 고쳐 주세요. 걸리지 않은 문장, 사실, 숫자, 날짜, 고유명사, 링크, [[...]] 표시, {LINK} 는 그대로.",
        f"말투: {tone} (바꾸지 마세요). 후킹(첫 줄의 센 말)은 살려요. 고치면서 새 AI 티(대구, 결산 공식, 줄표)를 만들지 마세요.",
        "[규칙]\n" + rules(),
        "\n\n".join(f"[{k}]\n{t}\n[{k} 걸린 자리]\n- " + "\n- ".join(spots_by_key.get(k) or ["(없음)"]) for k, t in texts.items()),
        '출력 JSON: {"edits": [{"key": "글 이름", "from": "원문 문장 그대로", "to": "고친 문장"}]} (최대 20개)'])
    res = llm.ask_json("당신은 한국어 윤문가예요. 걸린 자리만 고치고 JSON만 답해요.", prompt, model=model, web_search=False, max_tokens=4000, mock_name="korean_fix")
    out = dict(texts)
    for e in (res.get("edits") or [])[:20]:
        k, f, t = e.get("key"), (e.get("from") or "").strip(), (e.get("to") or "").strip()
        if k in out and f and t and out[k].count(f) == 1:
            out[k] = out[k].replace(f, t)
    for k in out:
        if _keep_marks(texts[k]) - _keep_marks(out[k]):
            log(f"  [{k}] 고치다 숫자·링크가 빠져서 원래대로 둬요")
            out[k] = texts[k]
    return out


def polish_md(md, model):
    """블로그 본문: 측정 → 걸리면 한 번 고치기 → 다시 측정. (새 글, 결과) 를 돌려줘요"""
    s = scan(md)
    if not needs_fix(s):
        return md, s
    log(f"  AI 티 측정 {s['grade']} {s['score']} → 걸린 자리 {len(s['spots'])}곳 고치기")
    new = fix({"본문": md}, "원문 그대로", model, {"본문": s["spots"]})["본문"]
    s2 = scan(new)
    if (s2.get("score") or 0) >= (s.get("score") or 0) and s2["fatal"] <= s["fatal"]:
        log(f"  AI 티 측정 {s['grade']} → {s2['grade']}")
        return new, s2
    return md, s


def polish_sns(site, post, model, check=None):
    """스레드 posts, 인스타 caption 을 점검·교정해서 post 를 고쳐요. check(posts, tag)->문제 목록 으로 반말 등 기존 점검도 지켜요"""
    texts, spots, report = {}, {}, {}
    th = post.get("threads") or {}
    for i, t in enumerate(th.get("posts") or []):
        s = scan(t.replace("{LINK}", ""), choppy=False)
        report[f"스레드{i + 1}"] = s["grade"]
        if needs_fix(s):
            texts[f"스레드{i + 1}"], spots[f"스레드{i + 1}"] = t, s["spots"]
    cap = (post.get("instagram") or {}).get("caption")
    if cap:
        body = "\n".join(l for l in cap.split("\n") if not l.strip().startswith("#"))
        s = scan(body, choppy=False)
        report["인스타"] = s["grade"]
        if needs_fix(s):
            texts["인스타"], spots["인스타"] = cap, s["spots"]
    if not texts:
        return report
    log(f"  SNS AI 티 걸림: {', '.join(texts)} → 고치기")
    tone = "스레드는 친근한 반말, 인스타 캡션은 원문 말투 그대로"
    new = fix(texts, tone, model, spots)
    posts = list(th.get("posts") or [])
    for k, v in new.items():
        if k.startswith("스레드"):
            posts[int(k[3:]) - 1] = v
    if posts and check and check(posts, th.get("topic_tag")) and not check(th.get("posts") or [], th.get("topic_tag")):
        log("  고친 스레드 글이 기존 점검에 걸려서 원래대로 둬요")
    elif posts:
        th["posts"] = posts
    if "인스타" in new:
        post["instagram"]["caption"] = new["인스타"]
    for k in texts:
        report[k] = scan(new[k].replace("{LINK}", ""))["grade"] if k.startswith("스레드") else report.get(k)
    return report
