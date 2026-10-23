"""네이버 블로그 업로드 (uplika 경유).

네이버는 공식 글쓰기 API가 없어서, uplika 크롬 확장이 사장님 컴퓨터의 크롬(네이버 로그인 상태)에서
편집기를 열고 글을 채워 발행해요. 크롬이 꺼져 있으면 켜질 때까지(최대 7일) 기다려요.

사용:
  python3 tools/publish_naver.py posts/<글폴더> --open private    # 비공개로 올리기 (검토용)
  python3 tools/publish_naver.py posts/<글폴더> --open public     # 공개로 올리기
  python3 tools/publish_naver.py posts/<글폴더> --refresh         # 대기 중이던 글 상태·주소 다시 확인
  python3 tools/publish_naver.py posts/<글폴더> --dry-run         # 보낼 내용만 출력

필요한 환경변수: UPLIKA_API_KEY (uplika 대시보드에서 발급, GitHub Secrets에 저장)
설정: config/settings.json 의 naver.category (블로그 카테고리 이름), naver.account_id (비우면 자동)
"""
import json
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from naver_markdown import card_captions, check, convert  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.uplika.com"


class Uplika:
    def __init__(self, dry):
        self.dry = dry
        self.key = os.environ.get("UPLIKA_API_KEY", "DRY" if dry else "")
        if not self.key:
            raise SystemExit("UPLIKA_API_KEY 가 없어요. GitHub Secrets 설정을 확인하세요.")
        self.n = 0

    def call(self, method, path, body=None):
        if self.dry:
            self.n += 1
            short = {k: (v[:50] + "…" if isinstance(v, str) and len(v) > 50 else v) for k, v in (body or {}).items()}
            print(f"  [미리보기] {method} {path} {json.dumps(short, ensure_ascii=False)[:300]}")
            return {"id": f"dry_{self.n}", "uploadUrl": "https://example.com/upload", "contentType": "image/jpeg",
                    "accounts": [{"id": "acc_naver", "platform": "naver_blog"}, {"id": "acc_ig", "platform": "instagram"}, {"id": "acc_th", "platform": "threads"}], "targets": [{"status": "published", "url": None}]}
        r = requests.request(method, API + path, json=body, timeout=90,
                             headers={"authorization": f"Bearer {self.key}", "content-type": "application/json"})
        if r.status_code >= 400:
            raise RuntimeError(f"uplika 오류 {r.status_code} {path}: {r.text[:400]}")
        res = r.json() if r.text else {}
        if isinstance(res, dict) and isinstance(res.get("data"), dict):
            res = {**res, **res["data"]}   # {"data": {...}} 형태로 오는 응답 풀기
        return res

    def upload(self, path, alt):
        data = path.read_bytes()
        pre = self.call("POST", "/v1/media/presign", {"fileName": path.name, "contentType": "image/jpeg", "bytes": len(data),
                                                      "width": 1080, "height": 1350, "altText": alt,
                                                      # 카드는 Claude가 코드로 그린 이미지라 네이버 'AI 활용' 표시를 켜요
                                                      "aiGenerated": True})
        if not self.dry:
            put = requests.put(pre["uploadUrl"], data=data, headers={"content-type": pre.get("contentType", "image/jpeg")}, timeout=120)
            put.raise_for_status()
        self.call("POST", f"/v1/media/{pre['id']}/complete", {})
        return pre["id"]


def naver_account(api, settings):
    if settings.get("account_id"):
        return settings["account_id"]
    accs = api.call("GET", "/v1/accounts")
    items = accs if isinstance(accs, list) else (accs.get("data") or accs.get("accounts") or [])
    for a in items:
        if str(a.get("platform", "")).startswith("naver") or "naver" in json.dumps(a).lower():
            return a["id"]
    raise SystemExit("uplika에 연결된 네이버 블로그가 없어요. uplika 대시보드 → 연결 → Naver Blog")


def refresh(post_dir):
    """크롬이 꺼져 있어 '대기'였던 글의 상태·주소를 다시 확인해요."""
    post_file = post_dir / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8"))
    naver = post.get("naver") or {}
    if not naver.get("uplika_post_id") or naver.get("status") in ("published", "failed"):
        return
    st = Uplika(False).call("GET", f"/v1/posts/{naver['uplika_post_id']}")
    t = (st.get("targets") or [{}])[0]
    naver["status"] = t.get("status", naver.get("status"))
    url = t.get("url") or t.get("permalink")
    if url:
        naver["url"] = url
        if naver.get("open") == "public":
            post["naver_url"] = url
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"네이버 상태: {naver['status']} {url or ''}")


def main():
    if "--refresh" in sys.argv:
        refresh(Path(sys.argv[1]).resolve())
        return
    post_dir = Path(sys.argv[1]).resolve()
    dry = "--dry-run" in sys.argv
    open_type = sys.argv[sys.argv.index("--open") + 1] if "--open" in sys.argv else "private"
    post_file = post_dir / "post.json"
    post = json.loads(post_file.read_text(encoding="utf-8"))
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))["naver"]
    naver = post.setdefault("naver", {})
    if naver.get("uplika_post_id") and naver.get("open") == open_type and not dry:
        print("이미 같은 공개 범위로 올라간 글이에요. 건너뜀")
        return

    md = (post_dir / "naver.md").read_text(encoding="utf-8")
    captions = card_captions(post_dir)
    # 1) 미리 변환해서 남은 표시가 없는지 확인 (실패하면 아무것도 올리지 않음)
    text, tags = convert(md, captions=captions)
    problems = check(text)
    if problems:
        raise SystemExit("네이버 원고 변환 실패:\n- " + "\n- ".join(problems))
    needed = sorted(set(k for k in captions if "{" + k + "}" in text))

    api = Uplika(dry)
    account = naver_account(api, settings)
    # 2) 본문에 들어가는 카드만 업로드
    media = {}
    for key in needed:
        f = post_dir / "cards" / f"{key[4:]}.jpg"
        media[key] = api.upload(f, captions[key])
    text, _ = convert(md, media=media, captions=captions)
    # 3) 글 올리기
    body = {
        "content": text,
        "accountIds": [account],
        "mediaIds": list(media.values()),
        "options": {"naver_blog": {"title": post["title"], "category": settings["category"], "tags": tags[:30],
                                   "layout": "as-is"}},
        # uplika 문서상 공개 범위(openType)는 '임시저장 → 발행' 단계에서 정해요
        "draft": True,
    }
    res = api.call("POST", "/v1/posts", body)
    pid = res.get("id")
    res = api.call("POST", f"/v1/posts/{pid}/publish", {"openType": open_type})
    # 4) 확장이 실제로 올릴 때까지 잠깐 확인 (크롬이 꺼져 있으면 '대기'로 남기고 끝)
    url, status = None, "publishing"
    for _ in range(1 if dry else 12):
        st = res if dry else api.call("GET", f"/v1/posts/{pid}")
        targets = st.get("targets", [])
        if targets:
            status = targets[0].get("status", status)
            url = targets[0].get("url") or targets[0].get("permalink")
        if status in ("published", "failed", "partial"):
            break
        time.sleep(10)
    if dry:
        print(f"미리보기 끝 · 공개 범위 {open_type} · 이미지 {len(media)}장 · 태그 {len(tags)}개")
        return
    if status == "failed":
        # 실패한 글은 '올라감'으로 치지 않아요. 자동으로 다시 시키지 않아요('발행이 잠시 제한'일 수 있어서)
        naver.update({"uplika_post_id": pid, "status": "failed", "failed_open": open_type})
        post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit(f"네이버 업로드 실패 (자동 재시도 안 함, 확인 후 직접 다시 실행): {json.dumps(st, ensure_ascii=False)[:400]}")
    naver.update({"uplika_post_id": pid, "open": open_type, "status": status})
    if url:
        naver["url"] = url
        if open_type == "public":
            post["naver_url"] = url
    post_file.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"네이버 {open_type} 업로드: {status} {url or '(크롬이 켜지면 올라가요)'}")


if __name__ == "__main__":
    main()
