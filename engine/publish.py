"""승인된 글을 올려요: 블로그(워드프레스/네이버) · 인스타 · 스레드.

  python3 engine/publish.py <글폴더> <blog|instagram|threads> [--dry-run]

- 워드프레스: REST API + 앱 비밀번호 (사이트 설정 blog.wordpress.user, 비밀키 이름 app_password_secret)
- 인스타·스레드: Meta 공식 API (비밀키 이름 instagram.token_secret / threads.token_secret)
  카드 이미지는 공개 저장소 주소(raw.githubusercontent.com)로 넘겨요
- 결과는 post.json 의 published 에 기록돼요
"""
import base64
import os
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from common import ROOT, load_json, load_site, log, now_kst, save_json, secret  # noqa: E402
import mdhtml  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "kim-wasp/woodenjoy-autopilot")
RAW = f"https://raw.githubusercontent.com/{REPO}/main"


def raw_url(d, name):
    return f"{RAW}/{d.relative_to(ROOT).as_posix()}/{name}"


def link_for(site, post):
    return (post.get("published") or {}).get("blog_url") or site.get("url", "")


# ---------- 워드프레스 ----------
class WP:
    def __init__(self, site, dry):
        cfg = site["blog"]["wordpress"]
        self.base = site["blog"]["url"].rstrip("/") + "/wp-json/wp/v2"
        self.dry = dry
        if not dry:
            token = base64.b64encode(f"{cfg['user']}:{secret(cfg['app_password_secret'])}".encode()).decode()
            self.h = {"Authorization": f"Basic {token}"}

    def req(self, method, path, **kw):
        if self.dry:
            log(f"  [미리보기] {method} {self.base}{path} {list(kw.get('json', {}).keys()) if 'json' in kw else ''}")
            return {"id": 1, "source_url": "https://example.com/x.jpg", "link": "https://example.com/post"}
        r = requests.request(method, self.base + path, headers={**self.h, **kw.pop("headers", {})}, timeout=120, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"워드프레스 오류 {r.status_code} {path}: {r.text[:300]}")
        return r.json()

    def media(self, f, alt):
        m = self.req("POST", "/media", data=f.read_bytes() if not self.dry else b"",
                     headers={"Content-Disposition": f'attachment; filename="{f.name}"', "Content-Type": "image/jpeg"})
        if alt and not self.dry:
            self.req("POST", f"/media/{m['id']}", json={"alt_text": alt})
        return m

    def category_id(self, name):
        if not name:
            return None
        found = self.req("GET", "/categories", params={"search": name, "per_page": 20})
        for c in found if isinstance(found, list) else []:
            if c.get("name") == name:
                return c["id"]
        return self.req("POST", "/categories", json={"name": name})["id"]


def publish_wordpress(site, d, post, dry):
    wp = WP(site, dry)
    urls = {}
    hero_id = None
    if (d / "hero.jpg").exists():
        m = wp.media(d / "hero.jpg", post["title"])
        hero_id, urls["hero"] = m["id"], m["source_url"]
    md = (d / "article.md").read_text(encoding="utf-8")
    slides = (load_json(d / "cards.json") or {}).get("slides", [])
    import re
    for n in sorted({int(x) for x in re.findall(r"\[\[card:(\d+)\]\]", md)}):
        f = d / "cards" / f"{n:02d}.jpg"
        if f.exists():
            alt = slides[n - 1]["title"].replace("*", "").replace("\n", " ") if n <= len(slides) else ""
            urls[f"card:{n}"] = wp.media(f, alt)["source_url"]
    html = mdhtml.convert(md, lambda k: (urls.get(k), post["title"] if k == "hero" else ""))
    body = {"title": post["title"], "content": html, "status": site["blog"]["wordpress"].get("status", "publish"),
            "excerpt": post.get("meta_description", ""), "slug": d.name[11:]}
    if hero_id:
        body["featured_media"] = hero_id
    cat = wp.category_id(site["blog"]["wordpress"].get("category"))
    if cat:
        body["categories"] = [cat]
    res = wp.req("POST", "/posts", json=body)
    return {"blog": res.get("id"), "blog_url": res.get("link")}


# ---------- 인스타 · 스레드 ----------
IG, TH = "https://graph.instagram.com", "https://graph.threads.net/v1.0"


def _post(dry, url, data):
    if dry:
        log(f"  [미리보기] POST {url} {[k for k in data if k != 'access_token']}")
        return {"id": "DRY"}
    r = requests.post(url, data=data, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(f"업로드 실패 {r.status_code}: {r.text[:300]}")
    return r.json()


def _wait(dry, base, cid, tok, field):
    if dry:
        return
    for _ in range(25):
        st = requests.get(f"{base}/{cid}", params={"fields": field, "access_token": tok}, timeout=30).json().get(field)
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"처리 실패: {st}")
        time.sleep(6)
    raise RuntimeError("처리 시간이 너무 오래 걸려요")


def card_urls(d):
    qa = load_json(d / "cards/qa.json", {})
    return [raw_url(d, f"cards/{f}") for f in qa.get("files", [])]


def publish_instagram(site, d, post, dry):
    tok = "DRY" if dry else secret(site["instagram"]["token_secret"])
    urls = card_urls(d)
    kids = []
    for u in urls:
        kids.append(_post(dry, f"{IG}/me/media", {"image_url": u, "is_carousel_item": "true", "access_token": tok})["id"])
    for k in kids:
        _wait(dry, IG, k, tok, "status_code")
    car = _post(dry, f"{IG}/me/media", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                         "caption": post["instagram"]["caption"], "access_token": tok})
    _wait(dry, IG, car["id"], tok, "status_code")
    return {"instagram": _post(dry, f"{IG}/me/media_publish", {"creation_id": car["id"], "access_token": tok})["id"]}


def publish_threads(site, d, post, dry):
    tok = "DRY" if dry else secret(site["threads"]["token_secret"])
    urls = card_urls(d)
    link = link_for(site, post)
    ids, reply_to = [], None
    for i, text in enumerate(post["threads"]["posts"]):
        data = {"text": text.replace("{LINK}", link), "access_token": tok}
        if i == 0 and urls:
            data.update({"media_type": "IMAGE", "image_url": urls[0]})
        else:
            data["media_type"] = "TEXT"
        if reply_to:
            data["reply_to_id"] = reply_to
        c = _post(dry, f"{TH}/me/threads", data)
        _wait(dry, TH, c["id"], tok, "status")
        p = _post(dry, f"{TH}/me/threads_publish", {"creation_id": c["id"], "access_token": tok})
        ids.append(p["id"])
        reply_to = p["id"]
    return {"threads": ids}


def publish(d, platform, dry=False):
    d = Path(d).resolve()
    post = load_json(d / "post.json")
    site = load_site(post["site"])
    pub = post.setdefault("published", {})
    if pub.get(platform) and not dry:
        log("이미 올라갔어요")
        return
    log(f"[{site['name']}] {post['title']} → {platform}")
    if platform == "blog":
        kind = site["blog"]["platform"]
        if kind == "wordpress":
            res = publish_wordpress(site, d, post, dry)
        else:
            raise SystemExit(f"블로그 종류 {kind} 는 아직 이 엔진에서 올리지 않아요")
    elif platform == "instagram":
        res = publish_instagram(site, d, post, dry)
    elif platform == "threads":
        res = publish_threads(site, d, post, dry)
    else:
        raise SystemExit(f"알 수 없는 플랫폼 {platform}")
    if dry:
        log("미리보기 끝")
        return
    pub.update(res)
    pub[f"{platform}_at"] = now_kst().isoformat(timespec="seconds")
    if all(pub.get(p) for p in post["platforms"]):
        post["status"] = "published"
    save_json(d / "post.json", post)
    log(f"완료: {res}")


if __name__ == "__main__":
    publish(sys.argv[1], sys.argv[2], "--dry-run" in sys.argv)
