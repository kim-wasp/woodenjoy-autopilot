"""인스타그램·스레드 자동 업로드.

사용:
  python3 tools/publish.py posts/<글폴더>            # 실제 업로드
  python3 tools/publish.py posts/<글폴더> --dry-run  # 무엇을 보낼지 출력만
  python3 tools/publish.py posts/<글폴더> --only threads   # 한 플랫폼만 (시간표 업로드용)

필요한 환경변수 (GitHub 저장소 Settings → Secrets 에 저장):
  IG_USER_ID, IG_TOKEN            인스타 (Instagram 로그인 방식 API 토큰)
  THREADS_USER_ID, THREADS_TOKEN  스레드
  IMAGE_BASE_URL                  카드 이미지가 공개된 주소 앞부분
                                  예) https://raw.githubusercontent.com/<아이디>/woodenjoy-autopilot/main
업로드 전에 카드 점검·글 점검을 다시 돌려서 하나라도 실패하면 올리지 않아요.
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
IG = "https://graph.instagram.com"
TH = "https://graph.threads.net/v1.0"


def env(name):
    v = os.environ.get(name)
    if not v:
        raise SystemExit(f"환경변수 {name} 가 없어요. GitHub Secrets 설정을 확인하세요.")
    return v


class Api:
    def __init__(self, dry):
        self.dry = dry
        self.n = 0

    def post(self, url, data):
        if self.dry:
            self.n += 1
            shown = {k: (v[:60] + "…" if isinstance(v, str) and len(v) > 60 else v) for k, v in data.items() if k != "access_token"}
            print(f"  [미리보기] POST {url.split('?')[0]} {shown}")
            return {"id": f"DRY{self.n}"}
        r = requests.post(url, data=data, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:300]}")
        return r.json()

    def wait_ready(self, base, cid, token, field="status_code", ok="FINISHED", tries=20):
        if self.dry:
            return
        for _ in range(tries):
            r = requests.get(f"{base}/{cid}", params={"fields": field, "access_token": token}, timeout=30).json()
            st = r.get(field) or r.get("status")
            if st == ok:
                return
            if st in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"처리 실패: {r}")
            time.sleep(6)
        raise RuntimeError("처리 시간이 너무 오래 걸려요")


def run_checks(post_dir):
    for cmd in (["node", str(ROOT / "tools/render_cards.js"), str(post_dir)],
                [sys.executable, str(ROOT / "tools/check_text.py"), str(post_dir)]):
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr.strip())
            raise SystemExit("점검 실패 → 업로드하지 않아요")


def card_urls(post_dir):
    base = env("IMAGE_BASE_URL").rstrip("/")
    rel = post_dir.relative_to(ROOT).as_posix()
    qa = json.loads((post_dir / "cards/qa.json").read_text(encoding="utf-8"))
    return [f"{base}/{rel}/cards/{f}" for f in qa["files"]]


def publish_instagram(api, post, urls):
    uid, tok = env("IG_USER_ID"), env("IG_TOKEN")
    children = []
    for u in urls:
        c = api.post(f"{IG}/{uid}/media", {"image_url": u, "is_carousel_item": "true", "access_token": tok})
        children.append(c["id"])
    for c in children:
        api.wait_ready(IG, c, tok)
    car = api.post(f"{IG}/{uid}/media", {"media_type": "CAROUSEL", "children": ",".join(children),
                                          "caption": post["instagram"]["caption"], "access_token": tok})
    api.wait_ready(IG, car["id"], tok)
    pub = api.post(f"{IG}/{uid}/media_publish", {"creation_id": car["id"], "access_token": tok})
    return pub["id"]


def publish_threads(api, post, cover_url, link):
    uid, tok = env("THREADS_USER_ID"), env("THREADS_TOKEN")
    ids, reply_to = [], None
    for i, text in enumerate(post["threads"]["posts"]):
        text = text.replace("[네이버 글 링크]", link)
        data = {"text": text, "access_token": tok}
        if i == 0:
            data.update({"media_type": "IMAGE", "image_url": cover_url})
        else:
            data.update({"media_type": "TEXT", "reply_to_id": reply_to})
        c = api.post(f"{TH}/{uid}/threads", data)
        api.wait_ready(TH, c["id"], tok, field="status", ok="FINISHED")
        if not api.dry:
            time.sleep(3)
        p = api.post(f"{TH}/{uid}/threads_publish", {"creation_id": c["id"], "access_token": tok})
        ids.append(p["id"])
        reply_to = p["id"]
    return ids


def find_account(api, word):
    accs = api.call("GET", "/v1/accounts")
    items = accs.get("accounts", accs if isinstance(accs, list) else [])
    for a in items:
        if word in json.dumps(a).lower():
            return a["id"]
    raise SystemExit(f"uplika에 {word} 계정이 연결돼 있지 않아요")


def publish_via_uplika(dry, post, post_dir, link):
    """인스타·스레드를 uplika로 올리기 (Meta 개발자 앱 없이)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from publish_naver import Uplika, card_captions
    api = Uplika(dry)
    qa = json.loads((post_dir / "cards/qa.json").read_text(encoding="utf-8"))
    caps = card_captions(post_dir)
    ids = [api.upload(post_dir / "cards" / f, caps.get(f"card{i + 1:02d}", f"카드 {i + 1}")) for i, f in enumerate(qa["files"])]
    out = {}
    if "instagram" in post["platforms"]:
        r = api.call("POST", "/v1/posts", {"content": post["instagram"]["caption"], "accountIds": [find_account(api, "instagram")],
                                           "mediaIds": ids, "wait": True})
        out["instagram"] = r.get("id")
    if "threads" in post["platforms"]:
        items = [{"content": t.replace("[네이버 글 링크]", link)} for t in post["threads"]["posts"]]
        items[0]["mediaIds"] = ids[:1]
        r = api.call("POST", "/v1/posts", {"threadItems": items, "accountIds": [find_account(api, "threads")], "wait": True})
        out["threads"] = r.get("id")
    return out


def main():
    post_dir = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv
    post_file = post_dir / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8"))
    if post.get("status") == "published" and not dry:
        print("이미 올라간 글이에요. 건너뜀")
        return
    run_checks(post_dir)
    brand = json.loads((ROOT / "config/brand.json").read_text(encoding="utf-8"))
    if dry:
        os.environ.setdefault("IMAGE_BASE_URL", "https://example.com")
        for k in ("IG_USER_ID", "IG_TOKEN", "THREADS_USER_ID", "THREADS_TOKEN"):
            os.environ.setdefault(k, "DRY")
    result = post.setdefault("published", {})
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))
    link = post.get("naver_url") or (post.get("naver") or {}).get("url") or brand["naverBlogHome"]
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    want = [p for p in ("instagram", "threads") if p in post["platforms"] and (only is None or p == only)]
    if settings.get("social_via") == "uplika":
        print("인스타·스레드 업로드 (uplika)…")
        todo = [p for p in want if not result.get(p)]
        if todo:
            result.update(publish_via_uplika(dry, {**post, "platforms": todo}, post_dir, link))
        if dry:
            print("미리보기 끝 (실제로 올리지 않았어요)")
            return
        finish(post, post_file, result)
        return
    api = Api(dry)
    urls = card_urls(post_dir)
    if "instagram" in want and not result.get("instagram"):
        print("인스타 업로드…")
        result["instagram"] = publish_instagram(api, post, urls)
    if "threads" in want and not result.get("threads"):
        print("스레드 업로드…")
        result["threads"] = publish_threads(api, post, urls[0], link)
    if dry:
        print("미리보기 끝 (실제로 올리지 않았어요)")
        return
    finish(post, post_file, result)


def finish(post, post_file, result):
    now = datetime.now(timezone.utc).isoformat()
    for p in ("instagram", "threads"):
        if result.get(p):
            result.setdefault(f"{p}_at", now)
    social_left = [p for p in ("instagram", "threads") if p in post["platforms"] and not result.get(p)]
    naver_left = "naver" in post["platforms"] and not (post.get("naver_url") or (post.get("naver") or {}).get("open") == "public")
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))
    naver_auto = settings["naver"].get("via") == "uplika" and settings.get("auto_publish") is True
    if social_left or (naver_left and naver_auto):
        post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        print("일부 업로드 완료, 남은 것:", social_left + (["naver"] if naver_left and naver_auto else []))
        return
    post["status"] = "published"
    result["at"] = now
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    used_file = ROOT / "topics/used.json"
    used = json.loads(used_file.read_text(encoding="utf-8"))
    if not any(u["id"] == post["id"] for u in used):
        used.append({"id": post["id"], "title": post["title"], "keyword": post.get("keywords", {}).get("main", "")})
        used_file.write_text(json.dumps(used, ensure_ascii=False, indent=2), encoding="utf-8")
    print("업로드 완료:", result)


if __name__ == "__main__":
    main()
