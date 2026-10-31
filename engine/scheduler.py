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
    for d in post_dirs(site_id):
        at = (load_json(d / "post.json", {}).get("published") or {}).get(f"{platform}_at")
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
            for p, t in plan(site, post, now).items():
                if pub.get(p) or now < t or p in taken or recently(sid, p, now):
                    continue
                if p != "blog" and "blog" in post["platforms"] and not pub.get("blog"):
                    continue
                taken.add(p)
                print(d.relative_to(ROOT).as_posix(), p)


def cmd_generate():
    """사이트별 '글 만들기' 시간이 지금(같은 시각의 30분 안)인지"""
    now = now_kst()
    for sid in site_ids():
        site = load_site(sid)
        g = (site.get("schedule") or {}).get("generate")
        if not site.get("enabled") or site.get("legacy") or not g:
            continue
        t = next_slot(g, now - timedelta(minutes=30))
        if t <= now:
            print(sid)


def cmd_board():
    now = now_kst()
    items = []
    for sid in site_ids():
        site = load_site(sid)
        for d in post_dirs(sid):
            post = load_json(d / "post.json", {})
            pub = post.get("published") or {}
            base = {"site": sid, "site_name": site.get("name"), "dir": d.relative_to(ROOT).as_posix(), "title": post.get("title")}
            for p in post.get("platforms", []):
                if pub.get(f"{p}_at"):
                    items.append({**base, "platform": p, "at": pub[f"{p}_at"], "state": "done",
                                  "url": pub.get("blog_url") if p == "blog" else None})
            if post.get("status") == "ready" and post.get("approved_at"):
                for p, t in plan(site, post, now).items():
                    if not pub.get(p):
                        items.append({**base, "platform": p, "at": t.isoformat(timespec="minutes"), "state": "planned"})
    items.sort(key=lambda x: x["at"])
    save_json(ROOT / "status/schedule.json", {"updated": now.isoformat(timespec="minutes"), "items": items[-200:]})
    print(f"일정 {len(items)}건 → status/schedule.json")


if __name__ == "__main__":
    {"due": cmd_due, "generate": cmd_generate, "board": cmd_board}[sys.argv[1]]()
