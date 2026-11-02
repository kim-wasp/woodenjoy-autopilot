"""일정 계산 (모든 사이트).

  python3 engine/scheduler.py due        # 지금 올릴 차례: "글폴더 플랫폼" 줄 목록 (처음 본 승인 글엔 approved_at 기록)
  python3 engine/scheduler.py generate   # 지금 글을 만들 차례인 사이트 id 목록
  python3 engine/scheduler.py board      # 관리화면용 일정표 → status/schedule.json

규칙
- 승인(병합)된 글(status ready)만 올려요. 승인 뒤 다가오는 그 플랫폼의 첫 시간에 올라가요
- 같은 사이트·같은 플랫폼에는 하루 한 편. 먼저 승인한 글부터
- 블로그가 있는 사이트는 블로그가 올라간 뒤에 SNS (링크 연결)
- 시간을 grace_hours 넘게 놓치면 다음 차례로 미뤄요
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DAYS, KST, ROOT, load_json, load_site, now_kst, post_dirs, save_json, site_ids  # noqa: E402

ORDER = ["blog", "threads", "instagram"]


def next_slot(slot, after):
    hh, mm = map(int, slot["time"].split(":"))
    for i in range(15):
        d = (after + timedelta(days=i)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if DAYS[d.weekday()] in slot["days"] and d >= after:
            return d
    raise ValueError("요일 설정을 확인하세요")


def due_time(slot, approved, now, grace):
    t = next_slot(slot, approved)
    while now - t > grace:
        t = next_slot(slot, t + timedelta(minutes=1))
    return t


def recently(site_id, platform, now, hours=20):
    ats = []
    for d in post_dirs(site_id):
        ats.append((load_json(d / "post.json", {}).get("published") or {}).get(f"{platform}_at"))
    # 예전 방식(posts/)으로 같은 계정에 올린 것도 같이 봐요 (하루 한 편 지키기)
    legacy_dir = (load_site(site_id).get("legacy_posts_dir") or "")
    if legacy_dir:
        for f in (ROOT / legacy_dir).glob("*/post.json"):
            lp = load_json(f, {})
            ats.append((lp.get("published") or {}).get(f"{platform}_at"))
            if platform == "blog":
                ats.append((lp.get("naver") or {}).get("public_at"))
    for at in ats:
        if at and now - datetime.fromisoformat(at).astimezone(KST) < timedelta(hours=hours):
            return True
    return False


def ready_posts(site_id):
    out = []
    for d in post_dirs(site_id):
        p = load_json(d / "post.json", {})
        if p.get("status") == "ready":
            out.append((d, p))
    return sorted(out, key=lambda x: x[1].get("approved_at") or "9999")


def plan(site, post, now):
    sch = site.get("schedule", {})
    slots, grace = sch.get("slots", {}), timedelta(hours=sch.get("grace_hours", 3))
    approved = datetime.fromisoformat(post["approved_at"]).astimezone(KST)
    return {p: due_time(slots[p], approved, now, grace) for p in ORDER if p in post.get("platforms", []) and p in slots}


def cmd_due():
    now = now_kst()
    for sid in site_ids():
        site = load_site(sid)
        if not site.get("enabled") or site.get("legacy"):
            continue
        taken = set()
        for d, post in ready_posts(sid):
            if not post.get("approved_at"):
                post["approved_at"] = now.isoformat(timespec="minutes")
                save_json(d / "post.json", post)
            pub = post.get("published") or {}
            start = (site.get("schedule") or {}).get("start_from")
            for p, t in plan(site, post, now).items():
                if start and now.strftime("%Y-%m-%d") < start:
                    continue
                if pub.get(p) or now < t or p in taken or recently(sid, p, now):
                    continue
                if p != "blog" and "blog" in post["platforms"] and not pub.get("blog"):
                    continue
                taken.add(p)
                print(d.relative_to(ROOT).as_posix(), p)


GEN_STATE = ROOT / "status" / "generated.json"


def last_slot(g, now):
    """지금 이전의 가장 최근 '글 만들기' 시각"""
    t = next_slot(g, now - timedelta(days=8))
    last = None
    while t <= now:
        last = t
        t = next_slot(g, t + timedelta(minutes=1))
    return last


def cmd_generate():
    """'글 만들기' 시각이 지났는데 아직 그 회차를 안 만든 사이트 (GitHub 예약이 늦거나 건너뛰어도 20시간 안이면 따라잡아요)"""
    now = now_kst()
    state = load_json(GEN_STATE, {})
    for sid in site_ids():
        site = load_site(sid)
        g = (site.get("schedule") or {}).get("generate")
        if not site.get("enabled") or site.get("legacy") or not g:
            continue
        t = last_slot(g, now)
        if not t or now - t > timedelta(hours=20):
            continue
        done = state.get(sid)
        if done and datetime.fromisoformat(done) >= t:
            continue
        print(sid)


def cmd_mark_generated(sid):
    state = load_json(GEN_STATE, {})
    state[sid] = now_kst().isoformat(timespec="minutes")
    save_json(GEN_STATE, state)


def cmd_board():
    """일정표: 실제 올리는 규칙(하루 한 편, 블로그 먼저, 시작일)을 그대로 따라 예상 시각을 계산해요"""
    now = now_kst()
    items = []
    for sid in site_ids():
        site = load_site(sid)
        sch = site.get("schedule") or {}
        slots = sch.get("slots", {})
        start = sch.get("start_from")
        start_dt = datetime.fromisoformat(start + "T00:00").replace(tzinfo=KST) if start else None
        used = {}  # 플랫폼별로 이미 차 있는 날짜
        for d in post_dirs(sid):
            pub = load_json(d / "post.json", {}).get("published") or {}
            for p in ORDER:
                if pub.get(f"{p}_at"):
                    used.setdefault(p, set()).add(datetime.fromisoformat(pub[f"{p}_at"]).astimezone(KST).date())
        for d in post_dirs(sid):
            post = load_json(d / "post.json", {})
            pub = post.get("published") or {}
            base = {"site": sid, "site_name": site.get("name"), "dir": d.relative_to(ROOT).as_posix(), "title": post.get("title")}
            for p in post.get("platforms", []):
                if pub.get(f"{p}_at"):
                    items.append({**base, "platform": p, "at": pub[f"{p}_at"], "state": "done",
                                  "url": pub.get("blog_url") if p == "blog" else None})
        for d, post in ready_posts(sid):
            if not post.get("approved_at"):
                continue
            pub = post.get("published") or {}
            base = {"site": sid, "site_name": site.get("name"), "dir": d.relative_to(ROOT).as_posix(), "title": post.get("title")}
            blog_t = None
            for p, t in plan(site, post, now).items():
                if pub.get(p):
                    continue
                floor = max([x for x in (now, start_dt, blog_t) if x is not None])
                if t < floor:
                    t = next_slot(slots[p], floor)
                for _ in range(60):
                    if t.date() not in used.get(p, set()):
                        break
                    t = next_slot(slots[p], t + timedelta(minutes=1))
                used.setdefault(p, set()).add(t.date())
                if p == "blog":
                    blog_t = t
                items.append({**base, "platform": p, "at": t.isoformat(timespec="minutes"), "state": "planned"})
    items.sort(key=lambda x: x["at"])
    save_json(ROOT / "status/schedule.json", {"updated": now.isoformat(timespec="minutes"), "items": items[-200:]})
    print(f"일정 {len(items)}건 → status/schedule.json")


if __name__ == "__main__":
    if sys.argv[1] == "mark-generated":
        cmd_mark_generated(sys.argv[2])
    else:
        {"due": cmd_due, "generate": cmd_generate, "board": cmd_board}[sys.argv[1]]()
