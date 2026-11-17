"""속보 트랙: 지금 뜨는 이슈를 잡아 스레드 글을 바로 만들고, 사장님 휴대폰으로 승인 알림을 보내요.

  python3 engine/issue.py watch [사이트id]   이슈 찾기 → 글 만들기 (만든 폴더는 ::issue-dir::<폴더> 로 출력)
  python3 engine/issue.py notify <폴더> <PR번호>   휴대폰 알림 (ntfy)

설정: sites/<id>/site.json
  "issue_track": {"enabled": true, "queries": ["검색어", ...], "max_per_day": 2, "min_score": 7, "stance": "both"}
  stance: "both" = 양쪽 입장을 세게 보여주고 질문 (정치), "mine" = 한쪽 편을 가볍게 들어도 됨 (생활)
기록: status/issue_seen.json (이미 본 이슈, 오늘 만든 수)

승인하면 다음 업로드 실행 때 바로 올라가요 (post.json 의 rush: true → 스레드 시간표·하루 한 편 규칙을 건너뜀).
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import KST, ROOT, load_json, load_site, log, now_kst, post_dirs, save_json, secret, site_ids  # noqa: E402
import llm  # noqa: E402
import skills  # noqa: E402
import trends  # noqa: E402

STATE = ROOT / "status" / "issue_seen.json"
PICK_MODEL = "claude-haiku-5-5"
WRITE_MODEL = "claude-sonnet-5-5"
QUIET = (0, 7)  # 한국 0시~7시는 만들지 않아요 (승인할 사람이 자고 있어요)
STUDIO = os.environ.get("STUDIO_URL", "https://woodenjoy-studio.vercel.app")


def _key(s):
    return hashlib.md5(re.sub(r"\W", "", s or "").lower().encode()).hexdigest()[:12]


def _state():
    return load_json(STATE, {}) or {}


def candidates(site, trend_list):
    """구글 트렌드 급상승 + 사이트 검색어로 찾은 최근 6시간 기사"""
    cfg = site.get("issue_track") or {}
    rows = []
    for t in trend_list[:25]:
        heads = " / ".join(n["title"] for n in t.get("news", [])[:2])
        rows.append({"id": f"t{len(rows)}", "kind": "급상승 검색어", "text": f"{t['keyword']} (검색 {t.get('traffic_label') or t.get('traffic')}) {heads}",
                     "key": t["keyword"], "traffic": t.get("traffic", 0), "links": [n["url"] for n in t.get("news", [])[:3]]})
    for q in cfg.get("queries", [])[:8]:
        time.sleep(2)  # 구글 뉴스가 연달아 부르면 429로 막아요
        try:
            items = trends._gnews(q, "6h")[:12]
        except requests.RequestException as e:
            log(f"  기사 검색 실패 '{q}': {e}")
            continue
        for i in items:
            title = trends._txt(i.get("title"))
            rows.append({"id": f"n{len(rows)}", "kind": f"기사({q}, 6시간 안 {len(items)}건+)", "text": title, "key": title,
                         "traffic": 0, "links": [i.get("link")]})
    return rows


def recent_titles(site_id, n=20):
    out = []
    for d in post_dirs(site_id)[-n:]:
        p = load_json(d / "post.json", {})
        out.append(p.get("title", ""))
    return [t for t in out if t]


def published_links(site_id, n=25):
    out = []
    for d in post_dirs(site_id)[-n:]:
        p = load_json(d / "post.json", {})
        u = (p.get("published") or {}).get("blog_url")
        if u:
            out.append({"title": p.get("title", ""), "url": u})
    return out


def pick(site, rows, seen):
    rows = [r for r in rows if _key(r["key"]) not in seen]
    if not rows:
        return None
    from generate import site_profile
    prompt = "\n\n".join([
        f"[사이트]\n{site_profile(site)}",
        f"[지금] {now_kst():%Y-%m-%d %H:%M}",
        "[최근에 쓴 글 제목 (같은 이슈는 다시 고르지 않아요)]\n" + "\n".join(recent_titles(site["id"])),
        "[지금 뜨는 것들]\n" + "\n".join(f"{r['id']} [{r['kind']}] {r['text']}" for r in rows[:80]),
        "이 사이트의 스레드 계정이 지금 바로 올리면 사람들이 멈춰서 한마디 하고 싶어질 이슈 하나를 골라요.\n"
        "고르는 기준: 1) 이 사이트 독자가 관심 가질 주제 2) 오늘 실제로 터진 일(기사 여러 개, 검색 급증) 3) 사람들 의견이 갈리거나 '나도 겪었어' 할 거리 "
        "4) 사실 확인이 되는 일. 연예인 사생활, 사고 피해자, 범죄 수법, 혐오를 부르는 주제, 선거 여론조사 수치 단독 보도는 고르지 않아요.\n"
        "점수(0~10): 7 이상이면 지금 올릴 가치가 있음. 마땅한 게 없으면 pick 을 null 로.\n"
        'JSON: {"pick": {"id": "t3", "keyword": "사람들이 실제로 치는 말 2~4단어", "score": 8, "why": "왜 지금 반응이 올지 한 줄", "angle": "어떤 장면·질문으로 갈지 한 줄"} 또는 null, '
        '"seen": ["이번에 보고 버린 것 중 다시 볼 필요 없는 id들"]}'])
    x = llm.ask_json("당신은 한국 SNS 이슈를 고르는 편집자예요. JSON만 답해요.", prompt, model=PICK_MODEL, max_tokens=1500, mock_name="issue_pick")
    return x, rows


STANCE = {
    "both": "편은 들지 않아요. 양쪽이 실제로 하는 말 중 가장 센 한 줄씩을 보여주고, 읽는 사람이 자기 편을 고르고 싶게 만들어요. 정당·정치인을 비꼬거나 조롱하지 않아요.",
    "mine": "운영자 입장에서 한쪽 편을 가볍게 들어도 돼요(\"솔직히 이건 ~ 쪽이 맞지 않아?\"). 단 근거는 확인된 사실만, 반대쪽을 깎아내리지 않아요.",
}


def write(site, chosen, rows):
    from generate import THREADS_GUIDE, THREADS_REACT, site_profile, th_problems
    src = next((r for r in rows if r["id"] == chosen["id"]), None) or {}
    cfg = site.get("issue_track") or {}
    links = published_links(site["id"])
    prompt = "\n\n".join([
        f"[사이트]\n{site_profile(site)}",
        f"[지금] {now_kst():%Y-%m-%d %H:%M} (오늘 뜬 이슈를 몇 시간 안에 올리는 속보 글이에요)",
        f"[이슈]\n{src.get('text', '')}\n검색어: {chosen.get('keyword')}\n왜 지금: {chosen.get('why')}\n방향: {chosen.get('angle')}\n참고 기사: " + " ".join(l for l in src.get("links", []) if l),
        THREADS_GUIDE, THREADS_REACT, skills.block("threads-kr"),
        f"[입장]\n{STANCE.get(cfg.get('stance', 'both'), STANCE['both'])}",
        "[링크 고르기]\n대댓글의 {LINK} 에 들어갈 우리 글: 아래 목록에서 이 이슈와 가장 가까운 글의 url 하나를 link 에. 맞는 글이 없으면 빈칸(홈으로 가요).\n"
        + "\n".join(f"- {l['title']} {l['url']}" for l in links),
        "웹 검색으로 이 이슈의 최신 보도를 2~3개 확인하고, 확인된 사실만 써요. 날짜·숫자·누가 무엇을 했는지 틀리면 안 돼요. "
        "기사마다 다르면 '~에 따르면'으로. 확인이 안 되면 ok 를 false 로.\n"
        'JSON: {"ok": true, "title": "관리화면에 보일 한 줄 제목", "keyword": "...", "hooks": ["첫 줄 후보 3개, 서로 다른 패턴"], '
        '"posts": ["본문", "첫 댓글(핵심 사실 2~4줄, 언제·어디 보도인지)", "대댓글 1~2줄 + {LINK}"], "topic_tag": "넓은 주제 태그 1개", '
        '"link": "https://... 또는 빈칸", "sources": [{"title": "매체명 기사 제목", "url": "https://..."}]}'])
    x = llm.ask_json("당신은 한국어 스레드 계정 운영자예요. 사실만 쓰고 JSON만 답해요.", prompt, model=WRITE_MODEL,
                     web_search=True, max_searches=4, max_tokens=4000, mock_name="issue_write")
    posts = [t for t in (x.get("posts") or []) if isinstance(t, str) and len(t.strip()) > 15][:3]
    if posts and "{LINK}" not in posts[-1]:
        posts[-1] = posts[-1].rstrip() + " {LINK}"
    x["posts"] = posts
    x["problems"] = th_problems(x.get("posts") or [], x.get("topic_tag")) if x.get("posts") else ["글이 비었어요"]
    return x


def watch(only=None):
    now = now_kst()
    if QUIET[0] <= now.hour < QUIET[1]:
        log("새벽이라 쉬어요")
        return
    st = _state()
    tl = None
    for sid in ([only] if only else site_ids()):
        site = load_site(sid)
        cfg = site.get("issue_track") or {}
        if not cfg.get("enabled") or not (site.get("threads") or {}).get("enabled"):
            continue
        s = st.setdefault(sid, {"seen": {}, "made": []})
        cut = (now - timedelta(days=3)).isoformat()
        s["seen"] = {k: v for k, v in s["seen"].items() if v > cut}
        today = [m for m in s["made"] if m[:10] == now.strftime("%Y-%m-%d")]
        if len(today) >= cfg.get("max_per_day", 2):
            log(f"[{sid}] 오늘 속보 {len(today)}개 다 만들었어요")
            continue
        if s["made"] and now - datetime.fromisoformat(s["made"][-1]) < timedelta(hours=cfg.get("gap_hours", 3)):
            log(f"[{sid}] 마지막 속보 뒤 {cfg.get('gap_hours', 3)}시간이 안 지났어요")
            continue
        if tl is None:
            tl = trends.google_trends()
        rows = candidates(site, tl)
        res = pick(site, rows, s["seen"])
        if not res:
            log(f"[{sid}] 새 이슈 없음")
            continue
        x, rows = res
        for i in (x.get("seen") or []):
            r = next((r for r in rows if r["id"] == i), None)
            if r:
                s["seen"][_key(r["key"])] = now.isoformat()
        p = x.get("pick")
        if not p or (p.get("score") or 0) < cfg.get("min_score", 7):
            log(f"[{sid}] 올릴 만한 이슈 없음 ({(p or {}).get('keyword', '-')} {(p or {}).get('score', '-')}점)")
            save_json(STATE, st)
            continue
        r = next((r for r in rows if r["id"] == p["id"]), {})
        s["seen"][_key(r.get("key", p.get("keyword")))] = now.isoformat()
        log(f"[{sid}] 고른 이슈: {p.get('keyword')} ({p.get('score')}점) {p.get('why')}")
        w = write(site, p, rows)
        if not w.get("ok") or not w.get("posts"):
            log(f"[{sid}] 사실 확인이 안 돼서 버려요: {w.get('title')}")
            save_json(STATE, st)
            continue
        d = ROOT / "content" / sid / f"{now:%Y-%m-%d}-issue-{now:%H%M}"
        d.mkdir(parents=True, exist_ok=True)
        post = {"site": sid, "title": "⚡ " + (w.get("title") or p.get("keyword")), "status": "draft", "rush": True,
                "platforms": ["threads"], "created_at": now.isoformat(timespec="minutes"),
                "keyword": w.get("keyword") or p.get("keyword"), "link": w.get("link") or "",
                "issue": {"keyword": p.get("keyword"), "score": p.get("score"), "why": p.get("why"), "traffic": r.get("traffic")},
                "threads": {"posts": w["posts"], "hooks": w.get("hooks", []), "topic_tag": w.get("topic_tag", ""), "style": "속보"},
                "sources": w.get("sources", []),
                "checks": {"ok": not w["problems"], "issues": ["스레드: " + i for i in w["problems"]]}}
        save_json(d / "post.json", post)
        s["made"] = (s["made"] + [now.isoformat(timespec="minutes")])[-20:]
        save_json(STATE, st)
        print(f"::issue-dir::{d.relative_to(ROOT).as_posix()}")
    save_json(STATE, st)


def notify(dir_, pr):
    """ntfy 앱으로 알림 (비밀키 NTFY_TOPIC). 알림을 누르면 관리화면 승인 대기로 가요."""
    topic = (secret("NTFY_TOPIC", required=False) or "").strip()
    if not topic:
        log("NTFY_TOPIC 비밀키가 없어서 알림을 못 보내요")
        return
    post = load_json(ROOT / dir_ / "post.json", {})
    body = (post.get("threads") or {}).get("posts", [""])[0][:200]
    why = (post.get("issue") or {}).get("why", "")
    url = f"{STUDIO}/#/review/{pr}"
    r = requests.post("https://ntfy.sh/", timeout=20, data=json.dumps({
        "topic": topic, "title": post.get("title", "속보 승인 대기")[:80], "message": f"{body}\n\n{why}",
        "click": url, "tags": ["zap"], "priority": 4,
        "actions": [{"action": "view", "label": "열어서 승인", "url": url}]}, ensure_ascii=False).encode("utf-8"))
    log(f"알림 {r.status_code}")


if __name__ == "__main__":
    if sys.argv[1] == "watch":
        watch(sys.argv[2] if len(sys.argv) > 2 else None)
    elif sys.argv[1] == "notify":
        notify(sys.argv[2], sys.argv[3])
