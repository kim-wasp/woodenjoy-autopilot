"""커먼센스 카드 늘리기: 사회 이슈를 모아 새 투표 카드 후보를 만들고, 승인한 것만 Supabase 에 넣어요.

  python3 engine/commonsense.py <사이트id> collect   # 최근 이슈 → 카드 후보 → sites/<id>/cards/<날짜>.json
  python3 engine/commonsense.py <사이트id> insert    # 관리화면에서 승인(approved)한 후보를 앱 DB 에 추가

사이트 설정 app:
  {"kind": "commonsense", "supabase_url_secret": "SUPABASE_URL", "supabase_key_secret": "SUPABASE_SERVICE_KEY",
   "table": "cards", "category_table": "categories", "count": 10}
카드 칸(컬럼)은 앱 DB 의 기존 카드를 읽어서 그대로 맞춰요. 숫자 집계 칸·id·날짜 칸은 건드리지 않아요.
"""
import json
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SITES, supabase_base, load_json, load_site, log, now_kst, save_json, secret  # noqa: E402
import llm  # noqa: E402

SYSTEM_FIELDS = {"id", "created_at", "updated_at", "deleted_at"}


class DB:
    def __init__(self, cfg):
        self.url = supabase_base(secret(cfg.get("supabase_url_secret", "SUPABASE_URL"))) + "/rest/v1"
        key = secret(cfg.get("supabase_key_secret", "SUPABASE_SERVICE_KEY"))
        # 새 형식 키(sb_secret_…)는 apikey 머리말만, 예전 service_role 키는 Bearer 도 함께
        self.h = {"apikey": key, "Content-Type": "application/json", **({} if key.startswith("sb_") else {"Authorization": f"Bearer {key}"})}

    def get(self, table, params):
        r = requests.get(f"{self.url}/{table}", headers=self.h, params=params, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase 읽기 오류 {r.status_code}: {r.text[:300]}")
        return r.json()

    def insert(self, table, row):
        r = requests.post(f"{self.url}/{table}", headers={**self.h, "Prefer": "return=representation"}, json=row, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase 추가 오류 {r.status_code}: {r.text[:300]}")
        return r.json()[0] if isinstance(r.json(), list) and r.json() else {}


def editable_fields(sample):
    """사람이 쓰는 칸만: 글자·참거짓 칸 + 카테고리 칸"""
    keys = []
    for k in sample[0].keys():
        if k in SYSTEM_FIELDS or k.endswith("_count") or k.endswith("_at"):
            continue
        vals = [r.get(k) for r in sample]
        if all(isinstance(v, (str, bool)) or v is None for v in vals) or "categ" in k:
            keys.append(k)
    return keys


def texts_of(rows, fields):
    out = []
    for r in rows:
        t = " / ".join(str(r.get(f)) for f in fields if isinstance(r.get(f), str) and len(str(r.get(f))) > 6)
        if t:
            out.append(t[:120])
    return out


def collect(site_id):
    site = load_site(site_id)
    cfg = site.get("app") or {}
    table = cfg.get("table", "cards")
    if os.environ.get("MOCK_LLM"):
        sample = [{"id": 1, "category": "CER", "situation": "친구 결혼식에 축의금 5만 원 내고 둘이 가도 된다", "created_at": "x"}]
        cats, existing = [{"code": "CER", "name": "경조사"}], sample
    else:
        db = DB(cfg)
        sample = db.get(table, {"select": "*", "limit": 30})
        if not sample:
            raise SystemExit("앱 DB 에 기존 카드가 없어서 형식을 알 수 없어요")
        existing = db.get(table, {"select": "*", "limit": 2000})
        cats = db.get(cfg.get("category_table", "categories"), {"select": "*"}) if cfg.get("category_table", "categories") else []
    fields = editable_fields(sample)
    prompt = "\n\n".join([
        f"[앱] {site.get('name')} — {site.get('writing_guide', '')}",
        f"[오늘] {now_kst():%Y-%m-%d}",
        "[카드 형식 — 이 칸만 채우세요]\n" + json.dumps(fields, ensure_ascii=False),
        "[기존 카드 예시]\n" + json.dumps([{k: r.get(k) for k in fields} for r in sample[:12]], ensure_ascii=False, indent=0),
        "[카테고리]\n" + json.dumps(cats, ensure_ascii=False),
        "[이미 있는 카드 — 겹치지 않게]\n" + "\n".join(texts_of(existing, fields)[-400:]),
        f"웹 검색으로 최근 2주 한국에서 화제가 된 사회 이슈·논쟁(뉴스·커뮤니티)을 찾아, '이거 상식이야?' 하고 의견이 갈릴 만한 생활 상황 카드 {cfg.get('count', 10)}개를 만드세요.\n"
        "- 특정인 비방, 정치 편들기, 혐오 표현, 사건 피해자 이야기는 피하고, 누구나 겪는 생활 상황으로 바꿔서 쓰세요.\n"
        "- 기존 카드와 같은 말투·길이로. 카테고리는 위 목록에서만.\n"
        'JSON: {"items": [{"row": {칸: 값}, "issue": "바탕이 된 이슈 한 줄", "source": {"title": "기사 제목", "url": "https://..."}, "why": "의견이 갈리는 이유"}]}'])
    res = llm.ask_json("당신은 생활 상식 투표 앱의 카드 편집자입니다. 사실에 근거한 이슈만 쓰고, 출력은 JSON 한 덩어리입니다.",
                       prompt, model=(site.get("llm") or {}).get("model"), web_search=True, mock_name=f"{site_id}_cards")
    items = []
    for it in res.get("items", []):
        row = {k: v for k, v in (it.get("row") or {}).items() if k in fields}
        if row:
            items.append({"row": row, "issue": it.get("issue", ""), "source": it.get("source", {}), "why": it.get("why", ""), "status": "pending"})
    out = SITES / site_id / "cards" / f"{now_kst():%Y-%m-%d-%H%M}.json"
    save_json(out, {"created": now_kst().isoformat(timespec="minutes"), "table": table, "fields": fields, "items": items})
    log(f"카드 후보 {len(items)}개 → {out.relative_to(SITES.parent)}")


def insert(site_id):
    site = load_site(site_id)
    cfg = site.get("app") or {}
    db = None
    n = 0
    for f in sorted((SITES / site_id / "cards").glob("*.json")):
        data = load_json(f)
        changed = False
        for it in data.get("items", []):
            if it.get("status") != "approved":
                continue
            db = db or DB(cfg)
            try:
                got = db.insert(data.get("table", cfg.get("table", "cards")), it["row"])
                it.update({"status": "inserted", "inserted_id": got.get("id"), "inserted_at": now_kst().isoformat(timespec="minutes")})
                n += 1
            except Exception as e:  # noqa: BLE001
                it.update({"status": "error", "error": str(e)[:300]})
            changed = True
        if changed:
            save_json(f, data)
    log(f"앱에 카드 {n}개 추가")


def recent_inserted(site_id, n=10):
    """최근에 앱에 들어간 카드 문장 (SNS 글감으로 써요)"""
    out = []
    for f in sorted((SITES / site_id / "cards").glob("*.json"))[-6:]:
        data = load_json(f, {})
        for it in data.get("items", []):
            if it.get("status") == "inserted":
                out.append(" / ".join(str(v) for v in it["row"].values() if isinstance(v, str)))
    return out[-n:]


def check(site_id):
    """연결 점검: 카드 표 읽기, 블로그 표 쓰기·지우기, 사진 저장소 올리기·지우기 → status/supabase-check.txt"""
    site = load_site(site_id)
    cfg = site.get("app") or {}
    app = (site.get("blog") or {}).get("app") or {}
    db = DB(cfg)
    base = db.url.rsplit("/rest/v1", 1)[0]
    lines = [f"점검 시각: {now_kst():%Y-%m-%d %H:%M}"]

    def step(name, fn):
        try:
            lines.append(f"OK  {name}: {fn()}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"실패 {name}: {str(e)[:300]}")

    def cards():
        rows = db.get(cfg.get("table", "cards"), {"select": "*", "limit": 1})
        r = requests.get(f"{db.url}/{cfg.get('table', 'cards')}", headers={**db.h, "Prefer": "count=exact", "Range": "0-0"}, timeout=60)
        total = r.headers.get("content-range", "?/?").split("/")[-1]
        return f"카드 {total}개, 칸: {', '.join(rows[0].keys()) if rows else '-'}"
    step("투표 카드 표 읽기", cards)
    step("카테고리 표 읽기", lambda: f"{len(db.get(cfg.get('category_table', 'categories'), {'select': '*'}))}개")

    table = app.get("table", "posts")

    def posts():
        db.get(table, {"select": "slug", "limit": 1})
        r = requests.post(f"{db.url}/{table}", headers={**db.h, "Prefer": "return=minimal"},
                          json={"slug": "zz-connection-test", "title": "연결 점검", "status": "draft", "content_html": "", "content_md": ""}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"쓰기 {r.status_code}: {r.text[:200]}")
        r = requests.delete(f"{db.url}/{table}", headers=db.h, params={"slug": "eq.zz-connection-test"}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"지우기 {r.status_code}: {r.text[:200]}")
        return "쓰기·지우기 됨"
    step(f"블로그 표({table})", posts)

    bucket = app.get("bucket", "blog")

    def storage():
        h = {k: v for k, v in db.h.items() if k != "Content-Type"}
        u = f"{base}/storage/v1/object/{bucket}/zz-connection-test.txt"
        r = requests.post(u, headers={**h, "Content-Type": "text/plain", "x-upsert": "true"}, data=b"ok", timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"올리기 {r.status_code}: {r.text[:200]}")
        pub = requests.get(f"{base}/storage/v1/object/public/{bucket}/zz-connection-test.txt", timeout=60).status_code
        requests.delete(u, headers=h, timeout=60)
        return f"올리기 됨, 공개 주소 응답 {pub}"
    step(f"사진 저장소({bucket})", storage)
    out = SITES.parent / "status" / "supabase-check.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    {"collect": collect, "insert": insert, "check": check}[sys.argv[2]](sys.argv[1])
