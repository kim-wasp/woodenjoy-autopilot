"""사용량 장부: Claude 호출 한 번, 사진 한 장마다 한 줄씩 기록해요.

- 기록 위치: usage/YYYY-MM/<시각>-<실행번호>-<프로세스>.json (실행마다 다른 파일 → 동시에 돌아도 충돌 없음)
- 저장: 각 워크플로 마지막 단계의 tools/save_usage.sh 가 main 에 올리고 status/usage_summary.json 을 다시 만들어요
- 비용은 engine/prices.json 단가로 계산한 추정치예요. 실제 청구액은 Claude Console·Google AI Studio 기준
"""
import atexit
import inspect
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
SITE = None          # 지금 작업 중인 사이트 (호출하는 쪽에서 바꿔요)
ENTRIES = []
_PRICES = None

# 호출한 함수 이름 → 사람이 읽는 작업 이름
PURPOSE = {
    "generate": "글 쓰기(본문·SNS)", "fix_issues": "점검 걸린 곳 고치기", "keyword_pool": "검색어 후보 뽑기",
    "ideas": "글감 추천", "threads_only": "스레드 문구 다시 쓰기", "opinion": "편집자 생각 넣기",
    "card_review": "카드 검수", "review_cards": "카드 검수", "humanize": "AI 티 다듬기", "fix": "AI 티 다듬기(문장 고치기)",
    "polish_md": "AI 티 다듬기", "polish_sns": "SNS 문장 다듬기", "pick": "속보 고르기", "write": "속보 글 쓰기",
    "check_orientation": "사진 방향 검수", "orientation": "사진 방향 검수", "make_cards": "커먼센스 카드 만들기",
    "polls": "스레드 투표 만들기",
}


def _prices():
    global _PRICES
    if _PRICES is None:
        try:
            _PRICES = json.loads((ROOT / "engine/prices.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            _PRICES = {}
    return _PRICES


def _site():
    if SITE:
        return SITE
    try:
        ids = {p.name for p in (ROOT / "sites").iterdir() if p.is_dir() and not p.name.startswith("_")}
    except Exception:  # noqa: BLE001
        ids = set()
    return next((a for a in sys.argv[1:] if a in ids), "공통")


def _task():
    """프로세스 단위 작업: 실행한 파일 + 모드"""
    script = Path(sys.argv[0]).stem if sys.argv else "?"
    flags = [a for a in sys.argv[1:] if a.startswith("--") and a not in ("--topic", "--notes", "--view", "--out", "--photos")]
    names = {"generate": "글 만들기", "issue": "속보 감지", "publish": "업로드", "commonsense": "커먼센스 카드",
             "fsl_pages": "forsmartlife 페이지", "scheduler": "일정"}
    base = names.get(script, script)
    mode = {"--threads": "스레드 다시 쓰기", "--thumb": "대표사진 다시", "--opinion": "편집자 생각", "--ideas": "글감 추천",
            "--polls": "스레드 투표"}
    for f in flags:
        if f in mode:
            return mode[f]
    if script == "issue" and len(sys.argv) > 1:
        return "속보 감지" if sys.argv[1] == "watch" else "속보 " + sys.argv[1]
    return base


def _caller():
    """ask_json 을 부른 함수 이름 (llm.py, usage.py 밖에서 처음 만나는 것)"""
    for fr in inspect.stack()[2:8]:
        if Path(fr.filename).name not in ("llm.py", "usage.py"):
            return PURPOSE.get(fr.function, fr.function), f"{Path(fr.filename).stem}.{fr.function}"
    return "기타", "?"


def claude(model, inp, cache_write, cache_read, out, searches, seconds):
    p = (_prices().get("claude") or {})
    p = p.get(model) or p.get("default") or {}
    ip, op = p.get("input_per_m", 0), p.get("output_per_m", 0)
    usd = (inp * ip + cache_write * ip * 1.25 + cache_read * ip * 0.1 + out * op) / 1e6 \
        + searches / 1000 * _prices().get("web_search_per_1000", 0)
    purpose, where = _caller()
    ENTRIES.append({"t": datetime.now(KST).isoformat(timespec="seconds"), "kind": "claude", "site": _site(), "task": _task(),
                    "purpose": purpose, "where": where, "model": model, "input": inp, "cache_write": cache_write,
                    "cache_read": cache_read, "output": out, "web_searches": searches, "sec": round(seconds, 1),
                    "usd": round(usd, 5)})


def image(model, provider):
    each = _prices().get("image_per_each") or {}
    purpose, where = _caller()
    ENTRIES.append({"t": datetime.now(KST).isoformat(timespec="seconds"), "kind": "image", "site": _site(), "task": _task(),
                    "purpose": "사진 만들기", "where": where, "model": model, "provider": provider, "count": 1,
                    "usd": round(each.get(model, each.get("default", 0)), 5)})


@atexit.register
def _flush():
    if not ENTRIES or os.environ.get("MOCK_LLM") or not (os.environ.get("GITHUB_ACTIONS") or os.environ.get("USAGE_LOG")):
        return
    now = datetime.now(KST)
    d = ROOT / "usage" / now.strftime("%Y-%m")
    d.mkdir(parents=True, exist_ok=True)
    run = os.environ.get("GITHUB_RUN_ID", "local")
    f = d / f"{now:%Y%m%d-%H%M%S}-{run}-{os.getpid()}.json"
    f.write_text(json.dumps({"workflow": os.environ.get("GITHUB_WORKFLOW", ""), "event": os.environ.get("GITHUB_EVENT_NAME", ""),
                             "run_id": run, "argv": [a[:60] for a in sys.argv[:4]], "entries": ENTRIES},
                            ensure_ascii=False, indent=0), encoding="utf-8")
