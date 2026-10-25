"""플랫폼별 업로드 시간 계산.

  python3 tools/schedule.py due            # 지금 올릴 차례인 (글폴더 플랫폼) 목록 출력. 처음 본 승인 글엔 approved_at 기록
  python3 tools/schedule.py show <글폴더>  # 그 글이 언제 어디에 올라갈지 보기
  python3 tools/schedule.py close          # 전부 올라간 글을 published 로 정리
  옵션 --now 2026-10-19T12:40  (시험용, 한국 시간)

시간표는 config/settings.json 의 slots (한국 시간).
- 네이버: uplika + 자동 모드일 때만 여기서 올려요. 승인 모드에선 사장님이 직접 공개로 바꿔요
- 스레드: 네이버 공개 주소가 생긴 뒤에 올려요(링크 연결). 네이버가 자동이 아니면 기다리지 않아요
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ORDER = ["naver", "threads", "instagram"]


def settings():
    return json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))


def next_slot(slot, after):
    """after 이후(같은 시각 포함) 첫 업로드 시각."""
    hh, mm = map(int, slot["time"].split(":"))
    for i in range(0, 15):
        d = (after + timedelta(days=i)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if DAYS[d.weekday()] in slot["days"] and d >= after:
            return d
    raise ValueError("slots 요일 설정을 확인하세요")


def due_time(slot, approved, now, grace):
    t = next_slot(slot, approved)
    while now - t > grace:          # 너무 늦었으면 다음 시간으로
        t = next_slot(slot, t + timedelta(minutes=1))
    return t


def naver_auto(s):
    return s["naver"].get("via") == "uplika" and s.get("auto_publish") is True


def done(post, platform):
    if platform == "naver":
        return bool(post.get("naver_url"))
    return bool((post.get("published") or {}).get(platform))


def plan(post, s, now):
    slots, grace = s["slots"], timedelta(hours=s["slots"].get("grace_hours", 3))
    approved = datetime.fromisoformat(post["approved_at"]).astimezone(KST)
    out = {}
    for p in ORDER:
        if p not in post.get("platforms", []) or p not in slots:
            continue
        nv = post.get("naver") or {}
        if p == "naver" and not naver_auto(s) and not (s["naver"].get("via") == "uplika" and nv.get("uplika_post_id")):
            out[p] = None   # 붙여넣기 방식: 사장님이 직접
            continue
        out[p] = due_time(slots[p], approved, now, grace)
    return out


def ready_posts():
    for f in sorted((ROOT / "posts").glob("*/post.json")):
        post = json.loads(f.read_text(encoding="utf-8"))
        if post.get("status") == "ready":
            yield f, post


def parse_now():
    if "--now" in sys.argv:
        return datetime.fromisoformat(sys.argv[sys.argv.index("--now") + 1]).replace(tzinfo=KST)
    return datetime.now(KST)


def recently_posted(platform, now, hours=20):
    """같은 플랫폼에 하루 한 편만: 최근 20시간 안에 올린 글이 있으면 다음 차례로 미뤄요"""
    for f in (ROOT / "posts").glob("*/post.json"):
        post = json.loads(f.read_text(encoding="utf-8"))
        pub = post.get("published") or {}
        at = (post.get("naver") or {}).get("public_at") if platform == "naver" else pub.get(f"{platform}_at")
        if at and now - datetime.fromisoformat(at).astimezone(KST) < timedelta(hours=hours):
            return True
    return False


def cmd_due():
    s, now = settings(), parse_now()
    taken = set()
    for f, post in sorted(ready_posts(), key=lambda fp: fp[1].get("approved_at") or "9999"):
        if not post.get("approved_at"):
            post["approved_at"] = now.isoformat(timespec="minutes")
            f.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        times = plan(post, s, now)
        for p, t in times.items():
            if t is None or done(post, p) or now < t:
                continue
            nv = post.get("naver") or {}
            if p == "naver" and (nv.get("status") == "failed" or (nv.get("open") == "public" and not nv.get("url"))):
                continue    # 실패는 자동 재시도 안 함 / 이미 보냈고 크롬 대기 중
            if p == "threads" and times.get("naver") is not None and not done(post, "naver") and nv.get("status") != "failed":
                continue    # 네이버 공개 주소를 기다려요 (실패했으면 블로그 홈 링크로 진행)
            if p in taken or recently_posted(p, now):
                continue    # 이번 차례엔 이미 다른 글이 올라가요
            taken.add(p)
            print(f.parent.relative_to(ROOT).as_posix(), p)


def cmd_show(d):
    s, now = settings(), parse_now()
    f = ROOT / d / "post.json" if not Path(d).is_absolute() else Path(d) / "post.json"
    post = json.loads(f.read_text(encoding="utf-8"))
    post.setdefault("approved_at", now.isoformat(timespec="minutes"))
    names = {"naver": "네이버", "threads": "스레드", "instagram": "인스타"}
    wd = "월화수목금토일"
    for p, t in plan(post, s, now).items():
        if done(post, p):
            print(f"{names[p]}: 이미 올라감")
        elif t is None:
            nt = next_slot(s["slots"]["naver"], now)
            print(f"{names[p]}: 직접 공개 전환 (추천 {nt:%m/%d}({wd[nt.weekday()]}) {nt:%H:%M})")
        else:
            print(f"{names[p]}: {t:%m/%d}({wd[t.weekday()]}) {t:%H:%M}")


def cmd_close():
    """모든 플랫폼이 올라간 글을 published 로 바꾸고 used.json 에 기록."""
    s = settings()
    used_file = ROOT / "topics/used.json"
    used = json.loads(used_file.read_text(encoding="utf-8"))
    for f, post in ready_posts():
        if not post.get("approved_at"):
            continue
        need = [p for p in post.get("platforms", []) if p != "naver" or naver_auto(s) or (post.get("naver") or {}).get("uplika_post_id")]
        if (post.get("naver") or {}).get("status") == "failed":
            need = [p for p in need if p != "naver"]
        if all(done(post, p) for p in need):
            post["status"] = "published"
            post.setdefault("published", {})["at"] = datetime.now(KST).isoformat(timespec="minutes")
            f.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
            if not any(u["id"] == post["id"] for u in used):
                used.append({"id": post["id"], "title": post["title"], "keyword": post.get("keywords", {}).get("main", "")})
            print("전부 올라감:", f.parent.name)
    used_file.write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "due":
        cmd_due()
    elif len(sys.argv) > 1 and sys.argv[1] == "close":
        cmd_close()
    elif len(sys.argv) > 2 and sys.argv[1] == "show":
        cmd_show(sys.argv[2])
    else:
        print(__doc__)
