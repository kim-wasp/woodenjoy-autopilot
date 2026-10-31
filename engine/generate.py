"""글 한 편 만들기: 제목(검색 기반) → 글 → 대표 이미지 → 카드 → 인스타·스레드 → 점검.

사용:
  python3 engine/generate.py <사이트id> [--topic "주제나 제목"] [--notes "고칠 점"] [--out 폴더]
  python3 engine/generate.py <사이트id> --ideas        # 글감 10개 추천 → sites/<id>/ideas.json
결과: content/<사이트id>/<날짜>-<슬러그>/ 에 post.json, article.md, article.html, hero.jpg, cards/*.jpg
"""
import argparse
import json
import os
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

SYSTEM = """당신은 한국어 블로그·SNS 콘텐츠를 만드는 편집장입니다. 목표는 검색 유입과 클릭, 그리고 신뢰입니다.

반드시 지킬 것
1. 사실만 씁니다. 숫자·규격·제도·가격·통계는 웹 검색으로 확인한 것만 쓰고, 확인한 출처를 sources 에 남깁니다. 확인 못 한 내용은 빼세요.
2. 후킹은 강하게, 내용은 사실로. 첫 줄·카드 표지·제목은 손해 회피("모르고 하면 손해"), 흔한 실수 지적, 반전, 본문 근거가 있는 구체적 숫자로 강하게 씁니다. 근거 없는 '100%·무조건·누구나·최고'는 쓰지 않습니다. 제목이 약속한 답은 본문에 반드시 있어야 합니다.
3. 사람들이 실제로 쓰는 말을 씁니다(쇼핑몰 상품명·포털 검색어에서 쓰는 소비자 용어). 업계 용어는 괄호로 한 번만.
4. 경험담·후기·사연을 지어내지 않습니다. 운영자의 경험은 사이트 설정에 적힌 것만 씁니다.
5. AI 티를 내지 않습니다: "~를 통해·~에 있어서·~에 의해" 같은 번역투, "결론적으로·시사하는 바가 크다·다음과 같다·~할 때입니다" 같은 관용구, 같은 대구의 반복, 연결어미 뒤 쉼표("~고,"), 같은 끝맺음 4번 이상 연속을 피하세요. 문장 길이를 섞으세요.
6. 의학·법률·금융 정보는 단정하지 말고 '전문가 상담'이 필요한 경계를 분명히 씁니다.
7. 출력은 설명 없이 JSON 한 덩어리입니다."""

CARD_GUIDE = """카드(인스타 캐러셀, 1080x1350) 규칙:
- slides 6~8장. 1장째는 표지(가장 강한 후킹, "big": true), 마지막 장은 저장·유입 안내.
- 장마다 새 정보 하나. 같은 문장 반복 금지.
- title: 2~3줄(\\n), 한 줄 10자 이내, 강조할 말은 *별표*로. sub: 1~2줄, 한 줄 18자 이내. badge(선택): 16자 이내.
- body 종류(다른 종류를 섞어 쓰세요):
  {"kind":"steps","items":[{"d":"한 줄 14자 이내","s":"보충 20자 이내(선택)"}] 2~4개,"tip":"선택, 40자 이내"}
  {"kind":"chips","label":"예시 설명","example":["표기1","표기2","표기3"],"legend":[["표기1","뜻 16자 이내"],...]}  (3~4개)
  {"kind":"grid","items":[{"label":"8자 이내"}] 4개}
  {"kind":"image","src":"hero.jpg","height":620}  ← 대표 사진을 넣을 때(표지 1장에만)
- 같은 body 종류는 최대 2번, 연달아 쓰지 마세요(비슷한 장은 점검에서 떨어져요). image 를 쓰는 표지는 title 2줄.
- 숫자·단계·비교처럼 정확해야 하는 정보는 카드 글자로 씁니다."""


def schema(site):
    blog = site.get("blog", {}).get("platform", "none") != "none"
    parts = ['"title": "제목 (핵심 키워드를 앞쪽에, 45자 이내)"',
             '"slug": "영문-소문자-하이픈"',
             '"keywords": {"main": "핵심 키워드", "sub": ["연관 키워드"...]}',
             '"brief": {"reader": "누가 어떤 상황에서", "question": "답할 질문 1개", "answer": "핵심 답 한 문장", "out_of_scope": "다루지 않을 것", "next_action": "읽고 할 행동"}',
             '"why_this_topic": "이 주제를 고른 근거 (검색량·시기·검색 결과)"']
    if blog:
        r = site.get("rules", {})
        parts += ['"meta_description": "검색 결과 설명 80~150자"',
                  f'"article_md": "본문 마크다운 {r.get("min_chars", 2500)}~{r.get("max_chars", 6000)}자. 첫 문단은 독자 상황+결론. '
                  '## 소제목 3~6개(질문형), 표 1개 이상, 자주 묻는 질문(## 자주 묻는 질문), 마지막에 ## 참고 자료 (출처 링크 목록). '
                  '이미지 자리: 첫 문단 뒤 [[hero]], 소제목 아래 적절한 곳에 [[card:번호]] 2~3개(카드 번호는 slides 순서)"']
    parts += ['"hero_prompt": "대표 사진 묘사(영어). 글 주제 장면, 사진 속 글자 없음"',
              '"cards": {"slides": [...]}',
              '"instagram": {"caption": "첫 줄 60자 이내 후킹 → 핵심 2~4줄 → 저장 유도 → 프로필 링크 안내. 링크 금지, 해시태그 5개 이하"}',
              '"threads": {"posts": ["본문(후킹 질문/반전, 500자 이내)", "댓글1(핵심 정리)", "댓글2(블로그·사이트로 이어지는 이유 + {LINK})"]}',
              '"sources": [{"title": "출처 제목", "url": "https://..."}]']
    return "{\n  " + ",\n  ".join(parts) + "\n}"


def site_profile(site):
    keys = ["name", "topic", "audience", "tone", "url", "writing_guide", "operator"]
    prof = {k: site[k] for k in keys if site.get(k)}
    prof["blog"] = site.get("blog", {}).get("platform", "none")
    prof["sns"] = [p for p in ("instagram", "threads") if site.get(p, {}).get("enabled")]
    return json.dumps(prof, ensure_ascii=False, indent=1)


def recent_titles(site_id, n=40):
    out = []
    for d in post_dirs(site_id)[-n:]:
        p = load_json(d / "post.json", {})
        out.append(p.get("title", ""))
    return [t for t in out if t]


def keyword_data(site):
    kw = load_json(SITES / site["id"] / "keywords.json") or load_json(ROOT / "topics/keywords.json") or {}
    rows = []
    for k, v in (kw.get("keywords") or {}).items():
        if any(s.replace(" ", "") in k or k in s.replace(" ", "") for s in site.get("seeds", [])) or SITES.joinpath(site["id"], "keywords.json").exists():
            rows.append(f"{k}: 월 {v.get('total')}회 ({v.get('checked')})")
    return "\n".join(rows[:60])


def build_prompt(site, topic, notes):
    p = [f"[사이트]\n{site_profile(site)}",
         f"[오늘] {now_kst():%Y-%m-%d (%a)}",
         "[최근에 쓴 제목 — 겹치지 않게]\n" + "\n".join(recent_titles(site["id"])[-30:] or ["(없음)"])]
    kd = keyword_data(site)
    if kd:
        p.append("[네이버 월간 검색량 (검색광고 키워드 도구, 실제 조회값)]\n" + kd)
    if topic:
        p.append(f"[주제/제목 지정]\n{topic}\n(이 주제로 쓰되 제목은 검색 키워드와 후킹을 살려 다듬어도 됩니다)")
    else:
        p.append("[주제 고르기]\n사이트 주제 안에서, 지금 시기에 검색이 많고 최근 글과 겹치지 않는 주제를 웹 검색으로 확인해 하나 고르세요. "
                 "검색량 자료가 있으면 우선 참고하고 근거를 why_this_topic 에 적으세요.\n후보 키워드: " + ", ".join(site.get("seeds", [])))
    if notes:
        p.append(f"[사장님이 고쳐 달라고 한 점 — 반드시 반영]\n{notes}")
    p.append(CARD_GUIDE)
    p.append("[출력 JSON 형식]\n" + schema(site))
    return "\n\n".join(p)


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


def write_post(site, res, d, topic):
    d.mkdir(parents=True, exist_ok=True)
    platforms = []
    blog = site.get("blog", {}).get("platform", "none")
    if blog != "none":
        platforms.append("blog")
    platforms += [p for p in ("threads", "instagram") if site.get(p, {}).get("enabled")]
    old = load_json(d / "post.json", {})
    post = {
        "id": f"{site['id']}/{d.name}", "site": site["id"], "title": res["title"], "status": "draft",
        "created_at": now_kst().isoformat(timespec="minutes"), "requested_topic": topic or "",
        "keywords": res.get("keywords", {}), "brief": res.get("brief", {}), "why_this_topic": res.get("why_this_topic", ""),
        "meta_description": res.get("meta_description", ""), "hero_prompt": res.get("hero_prompt", ""),
        "sources": res.get("sources", []), "platforms": platforms,
        "instagram": res.get("instagram") if "instagram" in platforms else None,
        "threads": res.get("threads") if "threads" in platforms else None,
        "revision": old.get("revision", 0) + (1 if old else 0),
    }
    save_json(d / "post.json", post)
    if res.get("article_md"):
        (d / "article.md").write_text(res["article_md"], encoding="utf-8")
    save_json(d / "cards.json", res["cards"])
    return post


def make_images(site, res, d):
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "hero.jpg").exists() and res.get("hero_prompt"):
        try:
            imagegen.generate(res["hero_prompt"], d / "hero.jpg", site.get("images", {}).get("hero", {}))
        except Exception as e:  # noqa: BLE001
            log(f"  대표 이미지 실패: {e}")
    if not (d / "hero.jpg").exists():  # 사진이 없으면 표지의 사진 칸을 빼요
        for s in res["cards"].get("slides", []):
            if (s.get("body") or {}).get("kind") == "image":
                s.pop("body")


def preview_html(site, post, d):
    md = (d / "article.md").read_text(encoding="utf-8") if (d / "article.md").exists() else ""
    if not md:
        return

    def img(name):
        if name == "hero":
            return ("hero.jpg", post["title"]) if (d / "hero.jpg").exists() else (None, None)
        n = int(name.split(":")[1])
        f = d / "cards" / f"{n:02d}.jpg"
        return (f"cards/{n:02d}.jpg", f"카드 {n}") if f.exists() else (None, None)
    (d / "article.html").write_text(mdhtml.convert(md, img), encoding="utf-8")


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
        if not issues:
            break
        log("  점검에 걸림 → 고치기:\n   - " + "\n   - ".join(issues))
        if attempt == 2 or os.environ.get("MOCK_LLM"):
            break
        res = llm.ask_json(SYSTEM, "아래 JSON 에서 점검에 걸린 부분만 고쳐서 전체 JSON 을 다시 주세요. 사실과 후킹은 유지하세요.\n\n"
                           f"[점검 결과]\n- " + "\n- ".join(issues) + "\n\n[이전 JSON]\n" + json.dumps(res, ensure_ascii=False),
                           model=llm_cfg.get("model"), web_search=False, mock_name=f"{site_id}_post")
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
        "[최근 제목]\n" + "\n".join(recent_titles(site_id)[-30:] or ["(없음)"]),
        "[검색량]\n" + (keyword_data(site) or "(자료 없음)"),
        "웹 검색으로 지금 시기에 검색 수요가 있는 주제를 확인해 글감 10개를 추천하세요. 최근 제목과 겹치지 않게. "
        'JSON: {"ideas": [{"title": "후킹 있는 제목안", "keyword": "핵심 키워드", "why": "근거(검색량/시기/이슈)", "angle": "다른 글과 다른 점"}]}'])
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
