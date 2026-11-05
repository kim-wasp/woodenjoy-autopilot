"""커먼센스 스레드 매일 투표: 앱의 상황 카드를 스레드 투표(2지선다)로 올리고, 대댓글로 세대별 결과 링크를 달아요.

사용:
  python3 engine/threads_poll.py due            예약 시간이 지났고 오늘 아직 안 올렸으면 1개 올림 (대기열이 비면 7개 새로 만듦)
  python3 engine/threads_poll.py make [N]       대기열 N개 만들기 (미리보기용, 올리지 않음)
  python3 engine/threads_poll.py due --dry-run  올리지 않고 무엇을 올릴지만 보기
설정: sites/<사이트>/site.json 의 "threads_poll": {"enabled": true, "time": "20:00", "link": "https://myinfobay.com/vote/{id}"}
기록: status/threads_polls.json (대기열, 올린 기록)
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from common import ROOT, load_json, load_site, log, now_kst, save_json, secret, site_ids  # noqa: E402
import llm  # noqa: E402
import skills  # noqa: E402

TH = "https://graph.threads.net/v1.0"
STATE = ROOT / "status" / "threads_polls.json"

GUIDE = """스레드 투표 글 규칙 (사장님 지시):
- 말투: 친구한테 말하듯 친근한 반말. 모든 문장을 반말로 끝내요. '~요', '~습니다' 금지.
- 본문(text): 2~4줄, 150자 이내. 첫 줄에서 멈추게 하는 후킹(상황 한 장면, 도발 질문, '이거 나만 그래?'). 마지막 줄은 투표를 부르는 질문.
- 초반 성장 단계라 자극적으로: 도발하는 첫 줄, 편 가르는 질문, '이거 인정 못 하면 손절각' 같은 센 반말 OK. 연애·데이트 비용·결혼·시댁/처가·돈·직장 갑질처럼 피 튀기는 소재 우선.
- 넘으면 안 되는 선(애드센스·메타 정책): 욕설, 성적 묘사, 혐오 표현(한남·김치녀·틀딱 등), 성별·세대·지역 전체를 깎아내리는 일반화, 정치·종교, 실존 인물·특정 회사 저격.
- 사실처럼 단정하는 숫자·통계 금지(투표 전이니까).
- 선택지 2개(option_a, option_b): 스레드 제한이 25바이트라 한글로 띄어쓰기 포함 8자 이내. 앱과 맞춰 '인정 (…)' / '아닌데 (…)' 형식, 괄호 안은 한글 3~4자 이유. 예: '인정 (예의지)', '아닌데 (오바임)', '인정 (내 권리지)'.
- 대댓글(reply): 반말 1~2줄 + {LINK}. 예: '20대랑 50대가 완전 갈렸던데 세대별 결과는 여기 👉 {LINK}'
- 링크는 대댓글에만. 본문·선택지에 링크 금지. 이모지는 글마다 2개 이하."""


def poll_sites():
    out = []
    for sid in site_ids():
        s = load_site(sid)
        if s.get("enabled") and (s.get("threads_poll") or {}).get("enabled") and (s.get("threads") or {}).get("enabled"):
            out.append(s)
    return out


def state():
    return load_json(STATE, {}) or {}


def candidate_cards(site, used):
    import commonsense
    db = commonsense.DB(site.get("app") or {})
    rows = db.get((site.get("app") or {}).get("table", "cards"), {"select": "id,statement,category,track", "limit": "1000"})
    rows = [r for r in rows if str(r.get("id")) not in used and r.get("statement")]
    hot = {c["name"] for c in commonsense.SPICY_CATS}
    return [r for r in rows if r.get("category") in hot] + [r for r in rows if r.get("category") not in hot]


def make_queue(site, n=7):
    st = state().get(site["id"], {})
    used = {str(x.get("card_id")) for x in st.get("posted", []) + st.get("queue", [])}
    cards = candidate_cards(site, used)
    if not cards:
        log("  투표로 쓸 새 카드가 없어요")
        return []
    sample = "\n".join(f"- [{c['id']}] ({c.get('category', '')}) {c['statement']}" for c in cards[:250])
    prompt = (f"{GUIDE}\n\n{skills.block('threads-kr')}\n\n[앱 카드 목록 — id, 분류, 상황 문장]\n{sample}\n\n"
              f"위 카드 중에서 스레드에서 의견이 가장 팽팽하게 갈리고 댓글이 붙을 만한 것 {n}개를 골라(연애·돈 분류가 있으면 절반 이상은 거기서, 나머지는 분류가 겹치지 않게), 규칙대로 써 주세요. "
              '출력 JSON: {"polls": [{"card_id": "카드 id 그대로", "text": "본문", "option_a": "인정 (…)", "option_b": "아닌데 (…)", "reply": "대댓글 + {LINK}"}]}')
    res = llm.ask_json("당신은 한국 스레드에서 반응을 잘 끌어내는 카피라이터예요. 사실만, 규칙을 지켜요. 출력은 JSON 한 덩어리.",
                       prompt, model=(site.get("llm") or {}).get("model"), web_search=False, max_tokens=4000, mock_name="threads_polls")
    ids = {str(c["id"]) for c in cards}
    polls = []
    for p in res.get("polls") or []:
        if str(p.get("card_id")) not in ids:
            continue
        p["option_a"], p["option_b"] = fit(p.get("option_a", ""), "인정"), fit(p.get("option_b", ""), "아닌데")
        if not p.get("text"):
            continue
        p["card_id"] = str(p["card_id"])
        polls.append(p)
    all_st = state()
    s = all_st.setdefault(site["id"], {"queue": [], "posted": []})
    s["queue"] = s.get("queue", []) + polls
    save_json(STATE, all_st)
    log(f"  [{site['name']}] 스레드 투표 대기열 +{len(polls)}개 (모두 {len(s['queue'])}개)")
    return polls


def fit(opt, fallback):
    """스레드 투표 선택지는 UTF-8 25바이트까지 (한글 약 8자). 넘으면 괄호 이유를 빼요."""
    opt = (opt or "").strip()
    if 0 < len(opt.encode()) <= 25:
        return opt
    head = opt.split("(")[0].strip()
    return head if 0 < len(head.encode()) <= 25 else fallback


def _post(url, data):
    r = requests.post(url, data=data, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"스레드 오류 {r.status_code}: {r.text[:300]}")
    return r.json()


def _publish(tok, data):
    c = _post(f"{TH}/me/threads", {**data, "access_token": tok})
    for _ in range(20):
        st = requests.get(f"{TH}/{c['id']}", params={"fields": "status", "access_token": tok}, timeout=30).json().get("status")
        if st == "FINISHED":
            break
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"스레드 처리 실패: {st}")
        time.sleep(3)
    return _post(f"{TH}/me/threads_publish", {"creation_id": c["id"], "access_token": tok})["id"]


def due(dry=False):
    now = now_kst()
    for site in poll_sites():
        cfg = site["threads_poll"]
        hh, mm = map(int, cfg.get("time", "20:00").split(":"))
        s = state().get(site["id"], {})
        posted_today = any(str(x.get("at", ""))[:10] == now.strftime("%Y-%m-%d") for x in s.get("posted", []))
        if posted_today or (now.hour, now.minute) < (hh, mm):
            continue
        if not s.get("queue"):
            if dry:
                log(f"  [{site['name']}] 대기열이 비어 있어 새로 만들 차례예요 (미리보기라 만들지 않음)")
                continue
            make_queue(site)
            s = state().get(site["id"], {})
            if not s.get("queue"):
                continue
        p = s["queue"][0]
        link = cfg.get("link", "https://myinfobay.com/vote/{id}").replace("{id}", p["card_id"])
        reply = p.get("reply", "세대별 결과는 여기 👉 {LINK}").replace("{LINK}", link)
        log(f"[{site['name']}] 스레드 투표 올리기: {p['text'][:40]}… / {p['option_a']} vs {p['option_b']}")
        if dry:
            log(f"  [미리보기] 대댓글: {reply}")
            continue
        tok = secret(site["threads"]["token_secret"])
        pid = _publish(tok, {"media_type": "TEXT", "text": p["text"],
                             "poll_attachment": json.dumps({"option_a": fit(p["option_a"], "인정"), "option_b": fit(p["option_b"], "아닌데")}, ensure_ascii=False)})
        rec = {**p, "id": pid, "at": now.isoformat(timespec="minutes"), "link": link}
        try:
            rec["reply_id"] = _publish(tok, {"media_type": "TEXT", "text": reply, "reply_to_id": pid})
        except Exception as e:  # noqa: BLE001
            rec["reply_error"] = str(e)[:200]
            log(f"  대댓글 실패(본문은 올라감): {e}")
        all_st = state()
        st2 = all_st.setdefault(site["id"], {"queue": [], "posted": []})
        st2["queue"] = [q for q in st2.get("queue", []) if q.get("card_id") != p["card_id"]]
        st2.setdefault("posted", []).append(rec)
        save_json(STATE, all_st)
        log(f"  완료: 스레드 {pid}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "due"
    if cmd == "make":
        n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 7
        for s in poll_sites():
            make_queue(s, n)
    else:
        due("--dry-run" in sys.argv)
