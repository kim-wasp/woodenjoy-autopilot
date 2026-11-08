"""승인된 글을 올려요: 블로그(워드프레스/네이버) · 인스타 · 스레드.

  python3 engine/publish.py <글폴더> <blog|instagram|threads> [--dry-run]

- 워드프레스: REST API + 앱 비밀번호 (사이트 설정 blog.wordpress.user, 비밀키 이름 app_password_secret)
- 인스타·스레드: Meta 공식 API (비밀키 이름 instagram.token_secret / threads.token_secret)
  카드 이미지는 공개 저장소 주소(raw.githubusercontent.com)로 넘겨요
- 결과는 post.json 의 published 에 기록돼요
"""
import base64
import os
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from common import ROOT, load_json, load_site, log, now_kst, save_json, secret, supabase_base  # noqa: E402
import mdhtml  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "kim-wasp/woodenjoy-autopilot")
TEST = False
RAW = f"https://raw.githubusercontent.com/{REPO}/main"


def raw_url(d, name):
    return f"{RAW}/{d.relative_to(ROOT).as_posix()}/{name}"


def link_for(site, post):
    return (post.get("published") or {}).get("blog_url") or site.get("url", "")


def body_images(d, post, md):
    """본문의 [[card:N]]·[[photo:N]] 자리에 들어갈 파일과 대체 텍스트"""
    import re
    slides = (load_json(d / "cards.json") or {}).get("slides", [])
    alts = {p["file"]: p.get("alt", "") for p in post.get("photos", [])}
    out = {}
    for kind, n in re.findall(r"\[\[(card|photo):(\d+)\]\]", md):
        n = int(n)
        if kind == "card":
            f = d / "cards" / f"{n:02d}.jpg"
            alt = slides[n - 1]["title"].replace("*", "").replace("\n", " ") if n <= len(slides) else ""
        else:
            f = d / f"photo{n}.jpg"
            alt = alts.get(f.name, "")
        if f.exists():
            out[f"{kind}:{n}"] = (f, alt)
    return out


# ---------- 네이버 (uplika) ----------
def publish_naver(site, d, post, dry):
    import re
    if not dry:
        os.environ["UPLIKA_API_KEY"] = secret("UPLIKA_API_KEY")
    from publish_naver import Uplika  # tools/publish_naver.py (크롬 확장으로 올려요)
    api = Uplika(dry)
    md = (d / "article.md").read_text(encoding="utf-8")
    media = {}
    imgs = body_images(d, post, md)
    if (d / "hero.jpg").exists():
        imgs["hero"] = (d / "hero.jpg", post["title"])
    for key, (f, alt) in imgs.items():
        media[key] = api.upload(f, alt)
    def rep(m):
        k = m.group(1)
        return f"![{imgs[k][1]}](media:{media[k]}){{.ai}}" if k in media else ""
    text = re.sub(r"\[\[(hero|card:\d+|photo:\d+)\]\]", rep, md)
    # 쿠팡 대가성 문구: 공정위 지침대로 본문 첫 부분에, 본문보다 크고 눈에 띄는 색으로 (굵게 + 19 + 빨강)
    text = re.sub(r"^[*_ ]*(이 포스팅은 쿠팡 파트너스 활동의 일환으로[^\n]*?)[*_ ]*$",
                  lambda m: f"**{m.group(1)}** {{.size=19 .color=#e7000b}}", text, count=1, flags=re.M)
    # 쿠팡 링크가 있는 문단 아래에 상품 이미지 카드(@card) 추가 → 눈에 잘 띄게 (네이버는 HTML 배너를 못 넣어요)
    seen, lines = set(), []
    for line in text.split("\n"):
        lines.append(line)
        for u in re.findall(r"https://link\.coupang\.com/[^\s)\]]+", line):
            if u not in seen and not line.lstrip().startswith(("-", "|")):
                seen.add(u)
                lines += ["", f"@card({u})", ""]
    text = "\n".join(lines)
    kw = post.get("keywords") or {}
    tags = [t.replace(" ", "") for t in [kw.get("main", "")] + kw.get("sub", []) if t][:10]
    cfg = site["blog"].get("naver", {})
    acc = cfg.get("account_id")
    if not acc:
        accs = api.call("GET", "/v1/accounts")
        items = accs if isinstance(accs, list) else (accs.get("data") or accs.get("accounts") or [])
        acc = next(a["id"] for a in items if str(a.get("platform", "")).startswith("naver"))
    title = ("[시험] " if TEST else "") + post["title"]
    res = api.call("POST", "/v1/posts", {"content": text, "accountIds": [acc], "mediaIds": list(media.values()), "wait": True,
                                         "options": {"naver_blog": {"title": title, "category": cfg.get("category", ""),
                                                                    "tags": tags, "layout": "as-is",
                                                                    "openType": "private" if TEST else "public"}}})
    t = (res.get("targets") or [{}])[0]
    if t.get("status") == "failed":
        raise RuntimeError(f"네이버 업로드 실패: {t.get('error')}")
    return {"blog": res.get("id"), "blog_url": res.get("permalink") or t.get("permalink")}


# ---------- 앱 블로그 (커먼센스 /blog, Supabase) ----------
def publish_appblog(site, d, post, dry):
    """사진은 Supabase Storage(공개 버킷)에, 글은 posts 표에 넣어요. 앱의 /blog 페이지가 이 표를 읽어요."""
    import re
    cfg = site["blog"].get("app", {})
    app = site.get("app") or {}
    base = supabase_base("https://example.supabase.co" if dry else secret(app.get("supabase_url_secret", "SUPABASE_URL")))
    key = "DRY" if dry else secret(app.get("supabase_key_secret", "SUPABASE_SERVICE_KEY"))
    h = {"apikey": key, **({} if key.startswith("sb_") else {"Authorization": f"Bearer {key}"})}
    bucket, table = cfg.get("bucket", "blog"), cfg.get("table", "posts")
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", d.name)

    def upload(f):
        path = f"{slug}/{f.name if f.parent == d else 'card-' + f.name}"
        if dry:
            log(f"  [미리보기] 사진 올리기 {bucket}/{path}")
        else:
            r = requests.post(f"{base}/storage/v1/object/{bucket}/{path}", headers={**h, "Content-Type": "image/jpeg", "x-upsert": "true"},
                              data=f.read_bytes(), timeout=120)
            if r.status_code >= 400:
                raise RuntimeError(f"사진 올리기 실패 {r.status_code}: {r.text[:200]}")
        return f"{base}/storage/v1/object/public/{bucket}/{path}"
    md = (d / "article.md").read_text(encoding="utf-8")
    urls = {}
    if (d / "hero.jpg").exists():
        urls["hero"] = upload(d / "hero.jpg")
    for k, (f, alt) in body_images(d, post, md).items():
        urls[k] = upload(f)
    alts = {k: a for k, (f, a) in body_images(d, post, md).items()}
    html = mdhtml.convert(md, lambda k: (urls.get(k), post["title"] if k == "hero" else alts.get(k, "")))
    row = {"slug": slug, "title": post["title"], "description": post.get("meta_description", ""), "content_html": html, "content_md": md,
           "hero_url": urls.get("hero"), "keywords": [(post.get("keywords") or {}).get("main", "")] + (post.get("keywords") or {}).get("sub", []),
           "sources": post.get("sources", []), "category": post.get("category") if post.get("category") in (cfg.get("categories") or []) else cfg.get("category", ""), "status": "published",
           "published_at": now_kst().isoformat(timespec="seconds")}
    if dry:
        log(f"  [미리보기] {table} 에 글 추가: {row['slug']} ({len(html)}자 HTML)")
    else:
        r = requests.post(f"{base}/rest/v1/{table}", headers={**h, "Content-Type": "application/json", "Prefer": "resolution=merge-duplicates,return=representation"},
                          params={"on_conflict": "slug"}, json=row, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"글 저장 실패 {r.status_code}: {r.text[:300]}")
    url = site["blog"].get("url", site.get("url", "")).rstrip("/") + cfg.get("path", "/blog") + "/" + slug
    return {"blog": slug, "blog_url": url}


# ---------- 독립 정적 블로그 (예: 시시비비노트, GitHub 저장소 → Cloudflare가 자동으로 띄움) ----------
def publish_static(site, d, post, dry):
    """글 폴더를 블로그 저장소의 posts/<날짜>-<슬러그>/ 로 복사하고 올려요. 저장소에 올라가면 Cloudflare가 1~2분 안에 사이트를 다시 만들어요."""
    import re
    import shutil
    import subprocess
    import tempfile
    import yaml
    cfg = site["blog"].get("static", {})
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", d.name)
    today = now_kst().date().isoformat()
    md = (d / "article.md").read_text(encoding="utf-8")
    md = re.sub(r"^\s*\[\[hero\]\]\s*$", "", md, flags=re.M)  # 대표 사진은 블로그 틀이 제목 아래에 넣어요
    imgs = body_images(d, post, md)
    files = []

    def rep(m):
        k = m.group(1)
        if k not in imgs:
            return ""
        f, alt = imgs[k]
        name = f.name if f.parent == d else "card-" + f.name
        files.append((f, name))
        return f"![{alt}]({name})"
    md = re.sub(r"^\s*\[\[(card:\d+|photo:\d+)\]\]\s*$", rep, md, flags=re.M)
    # 출처 목록은 블로그 틀이 글 끝에 따로 보여 줘요 → 본문의 참고 자료 칸은 빼요
    md = re.sub(r"\n## (참고 자료|참고|출처)\s*\n.*?(?=\n## |\Z)", "\n", md, flags=re.S)
    md = re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"
    cats = cfg.get("categories") or []
    meta = {"title": post["title"], "description": post.get("meta_description", ""), "date": today,
            "category": post.get("category") if post.get("category") in cats else cfg.get("category", ""),
            "conclusion": post.get("conclusion", ""), "tags": [(post.get("keywords") or {}).get("main", "")] + (post.get("keywords") or {}).get("sub", []),
            "sources": [{"title": x.get("title", ""), "url": x["url"]} for x in post.get("sources", []) if x.get("url")]}
    if (d / "hero.jpg").exists():
        meta["hero"] = "hero.jpg"
        meta["hero_alt"] = post["title"]
        files.append((d / "hero.jpg", "hero.jpg"))
    text = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + md
    folder = f"{cfg.get('path', 'posts')}/{today}-{slug}"
    url = site["blog"].get("url", site.get("url", "")).rstrip("/") + f"/posts/{slug}/"
    if dry:
        log(f"  [미리보기] {cfg['repo']} {folder}/post.md ({len(md)}자) + 사진 {len(files)}장 → {url}")
        return {"blog": folder, "blog_url": url}
    tok = secret(cfg.get("token_secret", "SISIBIBI_TOKEN"))
    tmp = Path(tempfile.mkdtemp())
    run = lambda *a: subprocess.run(a, cwd=tmp, check=True, capture_output=True, text=True)  # noqa: E731
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://x-access-token:{tok}@github.com/{cfg['repo']}.git", str(tmp)],
                   check=True, capture_output=True, text=True)
    old = [p for p in (tmp / cfg.get("path", "posts")).glob(f"*-{slug}") if p.is_dir()]
    for p in old:  # 같은 글을 다시 올리면 바꿔요 (날짜가 달라도 하나만)
        shutil.rmtree(p)
    out = tmp / folder
    out.mkdir(parents=True, exist_ok=True)
    (out / "post.md").write_text(text, encoding="utf-8")
    for f, name in files:
        shutil.copy(f, out / name)
    run("git", "config", "user.name", "studio-bot")
    run("git", "config", "user.email", "bot@users.noreply.github.com")
    run("git", "add", "-A")
    run("git", "commit", "-qm", f"글 올림: {post['title']}")
    for i in range(3):
        r = subprocess.run(["git", "push", "-q", "origin", "HEAD"], cwd=tmp, capture_output=True, text=True)
        if r.returncode == 0:
            break
        subprocess.run(["git", "pull", "-q", "--rebase"], cwd=tmp, capture_output=True, text=True)
    else:
        raise RuntimeError(f"블로그 저장소에 올리기 실패: {r.stderr.replace(tok, '***')[:300]}")
    shutil.rmtree(tmp, ignore_errors=True)
    return {"blog": folder, "blog_url": url}


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
    for key, (f, alt) in body_images(d, post, md).items():
        urls[key] = wp.media(f, alt)["source_url"]
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
    """본문 → 댓글 → 대댓글. 중간에 실패해도 올린 것까지 기록해서, 다음 실행 때 본문을 또 올리지 않고 이어서 올려요."""
    tok = "DRY" if dry else secret(site["threads"]["token_secret"])
    link = link_for(site, post)
    prog = post.setdefault("threads_progress", {"ids": []})
    ids = list(prog.get("ids") or [])
    reply_to = ids[-1] if ids else None
    for i, text in enumerate(post["threads"]["posts"]):
        if i < len(ids):
            continue
        data = {"text": text.replace("{LINK}", link), "access_token": tok, "media_type": "TEXT"}  # 글만 (사장님 지시)
        if reply_to:
            data["reply_to_id"] = reply_to
        tag = re.sub(r"[.&#]", "", str((post["threads"].get("topic_tag") or ""))).strip()[:50]
        if i == 0 and tag:
            data["topic_tag"] = tag  # 주제 태그 1개 (본문에만)
        try:
            try:
                c = _post(dry, f"{TH}/me/threads", data)
            except Exception as e:  # 태그 때문에 거절되면 태그 없이 한 번 더
                if "topic_tag" not in data:
                    raise
                log(f"  주제 태그 '{tag}' 거절됨 → 태그 없이 올려요: {str(e)[:120]}")
                data.pop("topic_tag")
                c = _post(dry, f"{TH}/me/threads", data)
            _wait(dry, TH, c["id"], tok, "status")
            p = _post(dry, f"{TH}/me/threads_publish", {"creation_id": c["id"], "access_token": tok})
        except Exception as e:
            if not dry:
                prog["ids"] = ids
                prog["error"] = str(e)[:300]
                save_json(d / "post.json", post)
                if "permission" in str(e) and ids:
                    raise RuntimeError(f"스레드 본문은 올라갔는데 댓글 권한이 없어요(토큰을 댓글 권한까지 넣어 다시 받아야 해요): {e}")
            raise
        ids.append(p["id"])
        reply_to = p["id"]
        if not dry:
            prog["ids"] = ids
            save_json(d / "post.json", post)
    post.pop("threads_progress", None)
    return {"threads": ids}


def publish(d, platform, dry=False):
    d = Path(d).resolve()
    post = load_json(d / "post.json")
    site = load_site(post["site"])
    pub = post.setdefault("published", {})
    if pub.get(platform) and not dry and not os.environ.get("FORCE"):
        log("이미 올라갔어요")
        return
    log(f"[{site['name']}] {post['title']} → {platform}")
    if platform == "blog":
        kind = site["blog"]["platform"]
        if kind == "wordpress":
            res = publish_wordpress(site, d, post, dry)
        elif kind == "naver":
            res = publish_naver(site, d, post, dry)
        elif kind == "appblog":
            res = publish_appblog(site, d, post, dry)
        elif kind == "static":
            res = publish_static(site, d, post, dry)
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
    if TEST:
        log(f"시험 업로드 끝 (기록하지 않음): {res}")
        return
    pub.update(res)
    pub[f"{platform}_at"] = now_kst().isoformat(timespec="seconds")
    if all(pub.get(p) for p in post["platforms"]):
        post["status"] = "published"
    save_json(d / "post.json", post)
    log(f"완료: {res}")


TEST = "--test" in sys.argv  # 네이버 비공개 시험: 제목 앞 [시험], 기록 안 남김

if __name__ == "__main__":
    publish(sys.argv[1], sys.argv[2], "--dry-run" in sys.argv)
