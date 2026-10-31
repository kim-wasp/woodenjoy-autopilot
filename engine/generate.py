"""글 한 편 만들기: 제목(검색 기반) → 블로그 글 → 사진·카드 → 인스타·스레드 → 점검 → AI 티 다듬기.

사용:
  python3 engine/generate.py <사이트id> [--topic "주제나 제목"] [--notes "고칠 점"] [--out 폴더]
  python3 engine/generate.py <사이트id> --ideas        # 글감 10개 추천 → sites/<id>/ideas.json
결과: content/<사이트id>/<날짜>-<슬러그>/ 에 post.json, article.md, article.html, hero.jpg, photo*.jpg, cards/*.jpg

사이트 설정에서 고르는 것
- 기본 채널 blog.platform: naver | wordpress | none(커먼센스처럼 앱·사이트로 보내는 SNS 전용)
- SNS: instagram.enabled / threads.enabled (기본 채널에 더해 선택)
- 수익화 monetization: stage(pre_adsense|adsense|adpost), coupang, internal_links, humanize
- 이미지 images: hero(대표 사진), blog_inline(cards|photos|mixed|none), photo_style, instagram(cards|photo_cards)
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONTENT, ROOT, SITES, load_json, load_site, log, now_kst, post_dirs, save_json, slugify  # noqa: E402
import checks  # noqa: E402
import imagegen  # noqa: E402
import llm  # noqa: E402
import mdhtml  # noqa: E402

SYSTEM = """당신은 한국어 블로그·SNS 콘텐츠로 수익을 내는 편집장입니다. 목표는 검색 유입·클릭·체류시간, 그리고 '거짓말 안 하는 곳'이라는 신뢰입니다.

반드시 지킬 것
1. 사실만 씁니다. 숫자·규격·제도·가격·통계는 웹 검색으로 확인한 것만 쓰고, 확인한 출처를 sources 에 남깁니다. 확인 못 한 내용은 빼세요.
2. 후킹은 강하게, 내용은 사실로. 첫 줄·카드 표지·제목은 손해 회피("모르고 하면 손해"), 흔한 실수 지적, 반전, 본문 근거가 있는 구체적 숫자로 강하게 씁니다. 근거 없는 '100%·무조건·누구나·최고'는 쓰지 않습니다. 제목이 약속한 답은 본문에 반드시 있어야 합니다.
3. 사람들이 실제로 쓰는 말을 씁니다(쇼핑몰 상품명·포털 검색어에서 쓰는 소비자 용어). 업계 용어는 괄호로 한 번만.
4. 경험담·후기·사연을 지어내지 않습니다. 운영자의 경험은 [운영자 경험] 에 있는 것만 씁니다.
5. AI 티를 내지 않습니다: "~를 통해·~에 있어서·~에 의해" 같은 번역투, "결론적으로·시사하는 바가 크다·다음과 같다·~할 때입니다" 같은 관용구, 같은 대구의 반복, 연결어미 뒤 쉼표("~고,"), 같은 끝맺음 4번 이상 연속을 피하세요. 문장 길이를 섞으세요.
6. 의학·법률·금융 정보는 단정하지 말고 전문가 상담이 필요한 경계를 분명히 씁니다. 정치 글은 한쪽을 편들지 않고 사실과 각 입장의 근거를 나란히 씁니다.
7. 광고 클릭을 유도하는 문구("광고 눌러 주세요" 등)는 절대 쓰지 않습니다. 제휴 링크는 독자에게 실제로 필요한 자리에만, 대가성 문구와 함께.
8. 출력은 설명 없이 JSON 한 덩어리입니다."""

STAGE_GUIDE = {
    "pre_adsense": "[수익화 단계: 애드센스 승인 전]\n- 승인 기준(독창성·충분한 정보·신뢰)이 최우선. 다른 글을 짜깁기한 듯한 일반론 금지, 이 글만의 판단 기준·비교표·체크리스트를 넣으세요.\n"
                   "- 작성 기준과 확인 날짜를 본문 끝에 한 줄로(예: '2026년 11월 기준, 공식 자료 확인'). 제휴 링크는 넣지 마세요.\n- 소제목마다 충분한 문단(얇은 단락 나열 금지).",
    "adsense": "[수익화 단계: 애드센스 운영 중]\n- 검색 클릭률(CTR)이 높은 제목, 첫 화면에서 답을 주되 더 읽을 이유(비교표·FAQ·체크리스트)를 남겨 체류시간을 늘리세요.\n"
               "- 소제목 5~7개, 각 소제목 아래 2~4문단(광고가 자연스럽게 들어갈 자리). 관련 글 내부 링크 2~3개.",
    "adpost": "[수익화 단계: 네이버 애드포스트]\n- 첫 3줄 훅, 결론 먼저, 질문형 소제목, 표와 이미지가 많은 글(모바일에서 끝까지 스크롤하게). 체류시간과 공감·저장을 노리세요.",
}

CARD_GUIDE = """카드(인스타 캐러셀, 1080x1350) 규칙:
- slides 6~8장. 1장째는 표지(가장 강한 후킹, "big": true), 마지막 장은 저장·유입 안내.
- 장마다 새 정보 하나. 같은 문장 반복 금지.
- title: 2~3줄(\\n), 한 줄 10자 이내, 강조할 말은 *별표*로. sub: 1~2줄, 한 줄 18자 이내. badge(선택): 16자 이내.
- body 종류(다른 종류를 섞어 쓰세요):
  {"kind":"steps","items":[{"d":"한 줄 14자 이내","s":"보충 20자 이내(선택)"}] 2~4개,"tip":"선택, 40자 이내"}
  {"kind":"chips","label":"예시 설명","example":["표기1","표기2","표기3"],"legend":[["표기1","뜻 16자 이내"],...]}  (3~4개)
  {"kind":"grid","items":[{"label":"8자 이내"}] 4개}
  {"kind":"image","src":"hero.jpg","height":560}  ← 대표 사진을 카드 안에 넣을 때(표지에만)
- 같은 body 종류는 최대 2번, 연달아 쓰지 마세요(비슷한 장은 점검에서 떨어져요). image 를 쓰는 표지는 title 2줄.
- 숫자·단계·비교처럼 정확해야 하는 정보는 카드 글자로 씁니다.
- 숫자만 덩그러니 두지 마세요. 무엇의 수치인지 같은 칸에 적어요(✕ "2023년 2.95%" → ○ "100만원 이상 송금 2.95%→3.17%").
- 표지·마지막 장 제목은 읽다 멈추게: 반전(평균은 A인데 1위는 B), 손해·오해 지적(이거 모르면 ○○), 질문형 도발. 단, 사실 그대로."""

PHOTO_CARD_GUIDE = """[인스타 사진 카드 모드] 카드 중 2~4장은 사진 배경 카드로 만드세요: {"title":"…","sub":"…","photo":"photo1.jpg"} (body 없이, 흰 글자가 사진 위에 올라가요).
표지는 반드시 사진 배경 카드(photo1.jpg). 사진 파일 이름은 photo_prompts 의 번호와 맞추세요(photo1.jpg = id 1)."""


# ---------- 재료 ----------
def blog_kind(site):
    return (site.get("blog") or {}).get("platform", "none")


def img_cfg(site):
    i = site.get("images") or {}
    return {
        "hero": i.get("hero", {"provider": "openai"}),
        "blog_inline": i.get("blog_inline", "cards"),          # cards | photos | mixed | none
        "photo_style": i.get("photo_style", ""),
        "instagram": i.get("instagram", "cards"),              # cards | photo_cards
        "photos": int(i.get("photos", 3)),
    }


def schema(site):
    blog = blog_kind(site) != "none"
    ic = img_cfg(site)
    need_photos = (blog and ic["blog_inline"] in ("photos", "mixed")) or ic["instagram"] == "photo_cards"
    parts = ['"title": "제목 (핵심 키워드를 앞쪽에, 45자 이내)"',
             '"slug": "영문-소문자-하이픈"',
             '"keywords": {"main": "핵심 키워드", "sub": ["연관 키워드"...]}',
             '"brief": {"reader": "누가 어떤 상황에서", "question": "답할 질문 1개", "answer": "핵심 답 한 문장", "out_of_scope": "다루지 않을 것", "next_action": "읽고 할 행동"}',
             '"why_this_topic": "이 주제를 고른 근거 (검색량·시기·검색 결과)"']
    if blog:
        r = site.get("rules", {})
        inline = {"cards": "소제목 아래 적절한 곳에 [[card:번호]] 2~3개(카드 번호는 slides 순서)",
                  "photos": "소제목 아래 적절한 곳에 [[photo:번호]] 2~3개(photo_prompts 번호)",
                  "mixed": "[[card:번호]] 1~2개와 [[photo:번호]] 1~2개를 섞어서",
                  "none": "본문 이미지는 [[hero]] 하나만"}[ic["blog_inline"]]
        parts += ['"meta_description": "검색 결과 설명 80~150자"',
                  f'"article_md": "본문 마크다운 {r.get("min_chars", 2500)}~{r.get("max_chars", 6000)}자. 첫 문단은 독자 상황+결론. '
                  '## 소제목(질문형), 표 1개 이상, ## 자주 묻는 질문, 마지막에 ## 참고 자료 (출처 링크 목록). '
                  f'이미지 자리: 첫 문단 뒤 [[hero]], {inline}"']
    if need_photos:
        parts.append(f'"photo_prompts": [{{"id": 1, "prompt": "사진 묘사(영어). {ic["photo_style"] or "주제에 맞는 현실적인 장면"}", "alt": "한국어 대체 텍스트"}}] 최대 {ic["photos"]}개')
    parts += ['"hero_prompt": "대표 사진 묘사(영어). 글 주제 장면, 사진 속 글자 없음"',
              '"cards": {"slides": [...]}']
    if site.get("instagram", {}).get("enabled"):
        parts.append('"instagram": {"caption": "첫 줄 60자 이내 후킹 → 핵심 2~4줄 → 저장 유도 → 프로필 링크 안내. 링크 금지, 해시태그 5개 이하"}')
    if site.get("threads", {}).get("enabled"):
        parts.append('"threads": {"posts": ["본문(후킹 질문/반전, 500자 이내)", "댓글1(핵심 정리)", "댓글2(블로그·사이트로 이어지는 이유 + {LINK})"]}')
    parts.append('"sources": [{"title": "출처 제목", "url": "https://..."}]')
    return "{\n  " + ",\n  ".join(parts) + "\n}"


def site_profile(site):
    keys = ["name", "topic", "audience", "tone", "url", "writing_guide"]
    prof = {k: site[k] for k in keys if site.get(k)}
    prof["base"] = {"naver": "네이버 블로그", "wordpress": "워드프레스 블로그", "appblog": "앱 안의 블로그(커먼센스 /blog, 애드센스 목표)",
                    "none": "블로그 없음(SNS → 사이트/앱으로 유입)"}[blog_kind(site)]
    prof["sns"] = [p for p in ("instagram", "threads") if site.get(p, {}).get("enabled")]
    return json.dumps(prof, ensure_ascii=False, indent=1)


def published_posts(site_id):
    out = []
    for d in post_dirs(site_id):
        p = load_json(d / "post.json", {})
        url = (p.get("published") or {}).get("blog_url")
        out.append({"title": p.get("title", ""), "url": url})
    return out


def keyword_data(site):
    own = SITES / site["id"] / "keywords.json"
    kw = load_json(own) or load_json(ROOT / "topics/keywords.json") or {}
    rows = []
    for k, v in (kw.get("keywords") or {}).items():
        if own.exists() or any(s.replace(" ", "") in k or k in s.replace(" ", "") for s in site.get("seeds", [])):
            rows.append(f"{k}: 월 {v.get('total')}회 ({v.get('checked')})")
    return "\n".join(rows[:60])


def coupang_items(site):
    m = site.get("monetization") or {}
    c = m.get("coupang") or {}
    if not c.get("enabled") or m.get("stage") == "pre_adsense":
        return []
    data = load_json(ROOT / c.get("links_file", f"sites/{site['id']}/coupang.json"), {})
    return [i for i in data.get("items", []) if i.get("url")]


def experiences(site):
    f = ROOT / site.get("experience_file", f"sites/{site['id']}/experience.md")
    if not f.exists():
        return ""
    blocks = re.split(r"\n(?=## )", f.read_text(encoding="utf-8"))
    ok = [b.strip() for b in blocks if re.search(r"^- 확인: 사장님", b, re.M)]
    return "\n\n".join(ok)[:4000]


def build_prompt(site, topic, notes):
    blog = blog_kind(site) != "none"
    m = site.get("monetization") or {}
    posts = published_posts(site["id"])
    p = [f"[사이트]\n{site_profile(site)}",
         f"[오늘] {now_kst():%Y-%m-%d (%a)}",
         "[최근에 쓴 제목 — 겹치지 않게]\n" + "\n".join([x["title"] for x in posts][-30:] or ["(없음)"])]
    if blog:
        p.append(STAGE_GUIDE.get(m.get("stage", "pre_adsense" if blog_kind(site) == "wordpress" else "adpost"), ""))
        links = [x for x in posts if x["url"]][-40:]
        if m.get("internal_links", True) and links:
            p.append("[내부 링크 후보 — 관련 있는 글만 본문에 2~3개 자연스럽게 [제목](주소)로]\n" + "\n".join(f"- {x['title']}: {x['url']}" for x in links))
        cp = coupang_items(site)
        if cp:
            p.append("[쿠팡 파트너스 링크 — 독자에게 실제로 필요한 문단에만 최대 2개, 아래 주소만 그대로 사용, 다른 쇼핑 링크 금지]\n"
                     + "\n".join(f"- {i['name']} ({i.get('note', '')}): {i['url']}" for i in cp))
    exp = experiences(site)
    if exp:
        p.append("[운영자 경험 — 사장님이 확인한 것만, 필요할 때 이 범위 안에서]\n" + exp)
    kd = keyword_data(site)
    if kd:
        p.append("[네이버 월간 검색량 (검색광고 키워드 도구, 실제 조회값)]\n" + kd)
    if topic:
        p.append(f"[주제/제목 지정]\n{topic}\n(이 주제로 쓰되 제목은 검색 키워드와 후킹을 살려 다듬어도 됩니다)")
    else:
        p.append("[주제 고르기]\n사이트 주제 안에서, 지금 시기에 검색이 많고 최근 글과 겹치지 않는 주제를 웹 검색으로 확인해 하나 고르세요. "
                 "검색량 자료가 있으면 우선 참고하고 근거를 why_this_topic 에 적으세요.\n후보 키워드: " + ", ".join(site.get("seeds", [])))
    extra = []
    if (site.get("app") or {}).get("kind") == "commonsense":
        import commonsense
        extra = commonsense.recent_inserted(site["id"])
    if extra:
        p.append("[앱에 새로 들어간 카드 — 주제로 쓰기 좋아요]\n" + "\n".join(extra[-10:]))
    if notes:
        p.append(f"[사장님이 고쳐 달라고 한 점 — 반드시 반영]\n{notes}")
    p.append(CARD_GUIDE)
    if img_cfg(site)["instagram"] == "photo_cards":
        p.append(PHOTO_CARD_GUIDE)
    p.append("[출력 JSON 형식]\n" + schema(site))
    return "\n\n".join(p)


# ---------- 파일·이미지 ----------
def brand_file(site):
    b = site.get("brand", {})
    data = {"cardLabel": b.get("cardLabel", site.get("name", "")), "handle": b.get("handle", ""), "colors": b.get("colors", {})}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f, ensure_ascii=False)
    f.close()
    return f.name


def render_cards(site, d):
    env = {**os.environ, "BRAND_FILE": brand_file(site)}
    tf = SITES / site["id"] / "terms.json"
    if tf.exists():
        env["TERMS_FILE"] = str(tf)
    r = subprocess.run(["node", str(ROOT / "tools/render_cards.js"), str(d)], capture_output=True, text=True, env=env)
    log("  " + (r.stdout.strip() or r.stderr.strip()).replace("\n", "\n  "))
    qa = load_json(d / "cards/qa.json", {"ok": False, "issues": [r.stderr.strip()[:300]]})
    return qa.get("issues", []) if r.returncode else []


def make_images(site, res, d):
    d.mkdir(parents=True, exist_ok=True)
    ic = img_cfg(site)
    if ic["hero"].get("provider") != "none" and not (d / "hero.jpg").exists() and res.get("hero_prompt"):
        try:
            imagegen.generate(res["hero_prompt"] + (" " + ic["photo_style"] if ic["photo_style"] else ""), d / "hero.jpg", ic["hero"])
        except Exception as e:  # noqa: BLE001
            log(f"  대표 이미지 실패: {e}")
    for ph in (res.get("photo_prompts") or [])[:ic["photos"]]:
        f = d / f"photo{ph['id']}.jpg"
        if f.exists():
            continue
        size = (1080, 1350) if ic["instagram"] == "photo_cards" else (1200, 800)
        try:
            imagegen.generate(ph["prompt"] + (" " + ic["photo_style"] if ic["photo_style"] else ""), f, ic["hero"], size=size)
        except Exception as e:  # noqa: BLE001
            log(f"  사진 {ph['id']} 실패: {e}")
    # 없는 사진을 가리키는 카드는 정리해요
    for s in res["cards"].get("slides", []):
        b = s.get("body") or {}
        if b.get("kind") == "image" and not (d / b.get("src", "hero.jpg")).exists():
            s.pop("body")
        if s.get("photo") and not (d / s["photo"]).exists():
            s.pop("photo")


def write_post(site, res, d, topic):
    d.mkdir(parents=True, exist_ok=True)
    platforms = []
    if blog_kind(site) != "none":
        platforms.append("blog")
    platforms += [p for p in ("threads", "instagram") if site.get(p, {}).get("enabled")]
    old = load_json(d / "post.json", {})
    post = {
        "id": f"{site['id']}/{d.name}", "site": site["id"], "title": res["title"], "status": "draft",
        "created_at": now_kst().isoformat(timespec="minutes"), "requested_topic": topic or "",
        "keywords": res.get("keywords", {}), "brief": res.get("brief", {}), "why_this_topic": res.get("why_this_topic", ""),
        "meta_description": res.get("meta_description", ""), "hero_prompt": res.get("hero_prompt", ""),
        "photos": [{"file": f"photo{p['id']}.jpg", "alt": p.get("alt", "")} for p in res.get("photo_prompts") or []],
        "sources": res.get("sources", []), "platforms": platforms, "blog_platform": blog_kind(site),
        "instagram": res.get("instagram") if "instagram" in platforms else None,
        "threads": res.get("threads") if "threads" in platforms else None,
        "revision": old.get("revision", 0) + (1 if old else 0),
    }
    md = res.get("article_md")
    if md:
        cp = coupang_items(site)
        disclosure = (site.get("monetization") or {}).get("coupang", {}).get(
            "disclosure", "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.")
        if cp and "link.coupang.com" in md and disclosure not in md:
            md = disclosure + "\n\n" + md
            post["coupang"] = True
        (d / "article.md").write_text(md, encoding="utf-8")
        res["article_md"] = md
    save_json(d / "post.json", post)
    save_json(d / "cards.json", res["cards"])
    return post


def preview_html(site, post, d):
    f = d / "article.md"
    if not f.exists():
        return
    alts = {p["file"]: p["alt"] for p in post.get("photos", [])}

    def img(name):
        if name == "hero":
            return ("hero.jpg", post["title"]) if (d / "hero.jpg").exists() else (None, None)
        kind, n = name.split(":")
        if kind == "photo":
            fn = f"photo{n}.jpg"
            return (fn, alts.get(fn, "")) if (d / fn).exists() else (None, None)
        fn = f"cards/{int(n):02d}.jpg"
        return (fn, f"카드 {n}") if (d / fn).exists() else (None, None)
    (d / "article.html").write_text(mdhtml.convert(f.read_text(encoding="utf-8"), img), encoding="utf-8")


# ---------- AI 티 다듬기 (im-not-ai 규칙) ----------
def humanize(site, md):
    if not md or not (site.get("monetization") or {}).get("humanize", True) or os.environ.get("MOCK_LLM"):
        return md
    rules = (ROOT / "tools/humanize/quick-rules.md").read_text(encoding="utf-8")[:14000]
    res = llm.ask_json(
        "당신은 한국어 윤문가입니다. 사실·숫자·고유명사·링크·[[...]] 표시·표·제목 구조는 그대로 두고 AI 티가 나는 문장만 고칩니다. 출력은 JSON 한 덩어리.",
        "아래 규칙으로 블로그 글의 AI 티를 빼 주세요. 바꾸는 양은 30% 이하, 후킹(첫 문단의 강한 말)은 살리세요.\n\n[규칙]\n" + rules
        + '\n\n[글]\n' + md + '\n\n출력: {"article_md": "고친 전체 글", "changed": ["고친 이유 몇 가지"]}',
        model=(site.get("llm") or {}).get("model"), web_search=False, mock_name="humanize")
    new = res.get("article_md") or md
    keep = re.findall(r"\[\[[^\]]+\]\]|https?://[^\s)]+|\d[\d,.]*", md)
    lost = [k for k in set(keep) if k not in new]
    ratio = 1 - difflib.SequenceMatcher(None, md, new).ratio()
    if lost or ratio > 0.35:
        log(f"  AI 티 다듬기 취소 (바뀐 비율 {ratio:.0%}, 빠진 표시·숫자 {len(lost)}개)")
        return md
    log(f"  AI 티 다듬기 완료 (바뀐 비율 {ratio:.0%})")
    return new


# ---------- 실행 ----------
def generate(site_id, topic=None, notes=None, out=None):
    site = load_site(site_id)
    llm_cfg = site.get("llm", {})
    log(f"[{site['name']}] 글 만들기 시작 · 주제: {topic or '자동 선택'}")
    res = llm.ask_json(SYSTEM, build_prompt(site, topic, notes), model=llm_cfg.get("model"),
                       web_search=llm_cfg.get("web_search", True), mock_name=f"{site_id}_post")
    d = Path(out) if out else CONTENT / site_id / f"{now_kst():%Y-%m-%d}-{slugify(res.get('slug') or res['title'])}"
    issues = []
    for attempt in range(3):
        make_images(site, res, d)
        post = write_post(site, res, d, topic)
        card_issues = render_cards(site, d)
        issues = checks.check(site, post, res.get("article_md")) + [f"카드: {x}" for x in card_issues]
        cp_urls = {i["url"] for i in coupang_items(site)}
        for u in re.findall(r"https?://link\.coupang\.com/\S+?(?=[)\s])", res.get("article_md") or ""):
            if u not in cp_urls:
                issues.append(f"블로그: 등록되지 않은 쿠팡 링크 {u[:40]}")
        if not issues:
            break
        log("  점검에 걸림 → 고치기:\n   - " + "\n   - ".join(issues))
        if attempt == 2 or os.environ.get("MOCK_LLM"):
            break
        res = llm.ask_json(SYSTEM, "아래 JSON 에서 점검에 걸린 부분만 고쳐서 전체 JSON 을 다시 주세요. 사실과 후킹은 유지하세요.\n\n"
                           f"[점검 결과]\n- " + "\n- ".join(issues) + "\n\n[이전 JSON]\n" + json.dumps(res, ensure_ascii=False),
                           model=llm_cfg.get("model"), web_search=False, mock_name=f"{site_id}_post")
    if not issues and res.get("article_md"):
        new = humanize(site, res["article_md"])
        if new != res["article_md"] and not checks.check(site, load_json(d / "post.json"), new):
            (d / "article.md").write_text(new, encoding="utf-8")
    post = load_json(d / "post.json")
    post["checks"] = {"ok": not issues, "issues": issues, "at": now_kst().isoformat(timespec="minutes")}
    save_json(d / "post.json", post)
    preview_html(site, post, d)
    log(f"완료: {d.relative_to(ROOT)} · 점검 {'통과' if not issues else '실패 ' + str(len(issues)) + '건'}")
    print(f"::set-output-dir::{d.relative_to(ROOT)}")
    return d, issues


def ideas(site_id):
    site = load_site(site_id)
    prompt = "\n\n".join([
        f"[사이트]\n{site_profile(site)}", f"[오늘] {now_kst():%Y-%m-%d}",
        "[최근 제목]\n" + "\n".join([x["title"] for x in published_posts(site_id)][-30:] or ["(없음)"]),
        "[검색량]\n" + (keyword_data(site) or "(자료 없음)"),
        "웹 검색으로 지금 시기에 검색 수요가 있고 수익(애드센스·애드포스트 단가, 제휴)에도 유리한 주제를 확인해 글감 10개를 추천하세요. 최근 제목과 겹치지 않게. "
        'JSON: {"ideas": [{"title": "후킹 있는 제목안", "keyword": "핵심 키워드", "why": "근거(검색량/시기/이슈/수익성)", "angle": "다른 글과 다른 점"}]}'])
    res = llm.ask_json(SYSTEM, prompt, model=site.get("llm", {}).get("model"), web_search=True, mock_name=f"{site_id}_ideas")
    res["updated"] = now_kst().isoformat(timespec="minutes")
    save_json(SITES / site_id / "ideas.json", res)
    log(f"글감 {len(res.get('ideas', []))}개 저장 → sites/{site_id}/ideas.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--topic")
    ap.add_argument("--notes")
    ap.add_argument("--out")
    ap.add_argument("--ideas", action="store_true")
    a = ap.parse_args()
    if a.ideas:
        ideas(a.site)
    else:
        _, iss = generate(a.site, a.topic, a.notes, a.out)
        sys.exit(1 if iss else 0)
