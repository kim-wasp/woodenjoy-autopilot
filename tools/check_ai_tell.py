"""한글 AI 티 점검 (im-not-ai 점수기 사용).

  python3 tools/check_ai_tell.py posts/<글폴더>

네이버 본문·인스타 캡션·스레드를 각각 점수 매겨 <글폴더>/ai_tell.json 에 저장해요.
- risk_band 가 high 면 실패(종료 코드 1) → AUTOPILOT의 'AI 티 다듬기'를 다시 해요
- 그 밖에 눈여겨볼 신호(연결어미 뒤 쉼표, 같은 종결어미 반복, AI 관용구)는 목록으로 알려줘요
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/humanize"))
import metrics_v2  # noqa: E402
from naver_markdown import card_captions, convert  # noqa: E402

# quick-rules 의 D(관용구) 중 블로그에서 자주 보이는 것
PHRASES = ["결론적으로", "요약하면", "정리하자면", "시사하는 바", "주목할 만", "매우 중요", "다음과 같", "크게 세 가지",
           "할 때입니다", "시점입니다", "이를 통해", "에 있어서", "에 의해", "되어진", "단순한", "더 이상"]
CONNECTIVE_COMMA = re.compile(r"(?:고|며|지만|면서|아서|어서|는데|니까),")


def plain_naver(post_dir):
    t, _ = convert((post_dir / "naver.md").read_text(encoding="utf-8"), captions=card_captions(post_dir))
    t = re.sub(r"!\[.*?\]\(.*?\)(\{\.ai\})?", "", t)
    t = re.sub(r"^\|.*\|$", "", t, flags=re.M)          # 표는 문장이 아니라 제외
    return re.sub(r"^[#>\-\s]+", "", t, flags=re.M)


def endings_streak(text):
    ends = [m.group(1) for m in re.finditer(r"([가-힣]{1,2})[.?!]\s", text + " ")]
    best = cur = 1
    for a, b in zip(ends, ends[1:]):
        cur = cur + 1 if a[-2:] == b[-2:] else 1   # 해요체는 끝 두 글자(예요·어요·거든요·죠)로 비교
        best = max(best, cur)
    return best


def score(text, genre="blog"):
    r = metrics_v2.compute_all_v2(text, genre=genre)
    hints = []
    n = len(CONNECTIVE_COMMA.findall(text))
    if n >= 4:
        hints.append(f"연결어미 뒤 쉼표 {n}곳 (예: '~고,' '~지만,') → 쉼표 빼기 (C-11)")
    s = endings_streak(text)
    if s >= 5:
        hints.append(f"같은 종결어미가 {s}문장 연속 → 몇 문장은 끝맺음을 바꾸기 (E-2)")
    found = [p for p in PHRASES if p in text]
    if found:
        hints.append("AI 관용구: " + ", ".join(found) + " → 빼거나 구체적으로 (D·A)")
    return {"risk_band": r["risk_band"], "risk_score": r["risk_score"], "hints": hints}


def main():
    post_dir = Path(sys.argv[1]).resolve()
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    out = {}
    if (post_dir / "naver.md").exists():
        out["naver"] = score(plain_naver(post_dir))
    if post.get("instagram"):
        out["instagram"] = score(re.sub(r"#\S+", "", post["instagram"]["caption"]))
    if post.get("threads"):
        out["threads"] = score("\n".join(post["threads"]["posts"]))
    (post_dir / "ai_tell.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [k for k, v in out.items() if v["risk_band"] == "high"]
    for k, v in out.items():
        print(f"{k}: AI 티 {v['risk_band']} ({v['risk_score']})" + "".join(f"\n  - {h}" for h in v["hints"]))
    if bad:
        print("AI 티가 강해요 → quick-rules 로 다듬은 뒤 다시 점검:", ", ".join(bad))
        sys.exit(1)


if __name__ == "__main__":
    main()
