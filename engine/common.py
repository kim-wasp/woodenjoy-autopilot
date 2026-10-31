"""공통: 경로, 사이트 설정, 비밀키, 시간.

사이트 설정: sites/<사이트id>/site.json
글 폴더:     content/<사이트id>/<날짜>-<영문슬러그>/
비밀키:      GitHub Actions 가 ALL_SECRETS(JSON) 로 넘겨줘요. 사이트 설정에는 '비밀키 이름'만 적어요.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ROOT / "sites"
CONTENT = ROOT / "content"
KST = timezone(timedelta(hours=9))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def now_kst():
    if os.environ.get("NOW_KST"):          # 시험용
        return datetime.fromisoformat(os.environ["NOW_KST"]).replace(tzinfo=KST)
    return datetime.now(KST)


def load_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def site_ids():
    return sorted(p.parent.name for p in SITES.glob("*/site.json") if not p.parent.name.startswith("_"))


def load_site(site_id):
    s = load_json(SITES / site_id / "site.json")
    if not s:
        raise SystemExit(f"사이트 설정이 없어요: sites/{site_id}/site.json")
    s.setdefault("id", site_id)
    return s


_SECRETS = None


def secret(name, required=True):
    """비밀키 이름으로 값을 꺼내요. (Actions: ALL_SECRETS, 로컬: 환경변수)"""
    global _SECRETS
    if _SECRETS is None:
        try:
            _SECRETS = json.loads(os.environ.get("ALL_SECRETS") or "{}")
        except json.JSONDecodeError:
            _SECRETS = {}
    v = _SECRETS.get(name) or os.environ.get(name)
    if not v and required:
        raise SystemExit(f"비밀키 {name} 가 없어요. GitHub → Settings → Secrets 에 넣어 주세요.")
    return v


def slugify(text, fallback="post"):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:50] or fallback


def post_dirs(site_id=None):
    base = CONTENT / site_id if site_id else CONTENT
    pattern = "*/post.json" if site_id else "*/*/post.json"
    return sorted(p.parent for p in base.glob(pattern))


def log(*a):
    print(*a, flush=True)
