"""글 자동 점검: 네이버 원고, 인스타 캡션, 스레드 글.

사용: python3 tools/check_text.py posts/<글폴더>
결과: <글폴더>/text_qa.json, 문제가 있으면 종료 코드 1
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKERS = re.compile(r"\[(?:/?인용구[^\]]*|/?형광|구분선|표 서식[^\]]*|표 이미지 후보|이미지[^\]]*|사진[^\]]*)\]")
URL = re.compile(r"https?://\S+")
AD_WORDS = ["광고 클릭", "광고를 눌러", "클릭해 주세요", "클릭 부탁"]
GREETINGS = ["안녕하세요", "오늘 날씨", "반갑습니다"]
# 근거 없이 결과를 보장하거나 부풀리는 말 (제목·본문·캡션 공통)
HYPE = ["무조건", "100%", "완벽 정리", "완벽하게", "최고의", "BEST", "베스트", "가장 쉬운", "누구나 쉽게", "보장합니다", "상위노출", "상위 노출"]
# 발행되면 안 되는 작업 메모
MEMO = ["[확인 필요]", "TODO", "검토 메모", "실습 예시", "(예시)", "XXX"]
# 사장님의 실제 경험을 말하는 표현 → topics/experience.md 에 확인된 기록이 있어야 해요
EXPERIENCE = ["현장에서", "현장 가 보면", "제가 직접", "직접 해 보니", "직접 해보니", "고객님", "의뢰", "시공해 보면",
              "써 보니", "써보니", "사용해 보니", "사용해보니", "써 봤", "써봤", "사서 써",
              "작업하다 보면", "저희", "우드엔조이에서", "제 경험", "실제로 가 보면"]
COUPANG_URL = re.compile(r"https?://(?:link\.|www\.|m\.)?coupang\.com\S*")
COUPANG_MARK = re.compile(r"\[쿠팡:\s*([\w-]+)\s*\|\s*([^\]]+?)\s*\]")
# 공정위 심사지침: 모호한 표시 금지, 받은 물건·수수료가 있는 글에 '내돈내산' 금지
VAGUE = ["소정의", "수수료를 받을 수", "수수료 지급 가능", "내돈내산"]
BRIEF_KEYS = ["reader", "question", "answer", "out_of_scope", "next_action"]


def experience_ids():
    f = ROOT / "topics/experience.md"
    if not f.exists():
        return {}
    ids = {}
    text = re.sub(r"```.*?```", "", f.read_text(encoding="utf-8"), flags=re.S)   # 형식 예시는 빼고
    for block in re.split(r"\n(?=## )", text):
        m = re.match(r"## (E\d+)", block)
        if m:
            ids[m.group(1)] = bool(re.search(r"^- 확인: 사장님", block, flags=re.M))
    return ids


def plain(text):
    return re.sub(r"\s+", " ", MARKERS.sub("", text)).strip()


def ngrams(text, n=3):
    t = re.sub(r"\s+", "", plain(text))
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def check_coupang(post, post_dir):
    """쿠팡 링크가 있는 글: 대가성 문구(본문 첫 부분), 링크 수, 링크 목록, 모호한 표현."""
    out = []
    settings = json.loads((ROOT / "config/settings.json").read_text(encoding="utf-8"))
    cfg = settings.get("affiliate", {}).get("coupang", {})
    md_file = post_dir / "naver.md"
    md = md_file.read_text(encoding="utf-8") if md_file.exists() else ""
    marks = COUPANG_MARK.findall(md)
    items = (post.get("affiliate") or {}).get("items", [])
    social = {"인스타": (post.get("instagram") or {}).get("caption", ""),
              "스레드": "\n".join((post.get("threads") or {}).get("posts", []))}
    for label, t in social.items():
        if COUPANG_URL.search(t) or COUPANG_MARK.search(t):
            if label not in [{"instagram": "인스타", "threads": "스레드"}.get(x) for x in cfg.get("platforms", [])]:
                out.append(f"{label}: 쿠팡 링크는 아직 네이버에만 넣어요 (settings.json affiliate.coupang.platforms)")
    if not marks and not items:
        return out
    if not cfg.get("enabled"):
        return out + ["쿠팡: settings.json 에서 affiliate.coupang.enabled 가 꺼져 있어요"]
    lib_f = ROOT / "topics/coupang_links.json"
    lib = {i["key"]: i for i in json.loads(lib_f.read_text(encoding="utf-8")).get("items", [])} if lib_f.exists() else {}
    keys = [k for k, _ in marks]
    for k in keys:
        if k not in lib:
            out.append(f'쿠팡: "{k}"가 topics/coupang_links.json 에 없어요')
        elif not lib[k].get("url"):
            out.append(f'쿠팡: "{k}" 링크 주소가 아직 없어요 (사장님이 만들어 넣기 전엔 글에서 빼요)')
        elif not COUPANG_URL.fullmatch(lib[k]["url"]):
            out.append(f'쿠팡: "{k}" 주소가 쿠팡 주소가 아니에요')
    if sorted(set(keys)) != sorted(set(items)):
        out.append(f"쿠팡: 본문 표시 {sorted(set(keys))}와 post.json affiliate.items {sorted(set(items))}가 달라요")
    limit = cfg.get("naver_max_links", 2)
    if len(marks) > limit:
        out.append(f"쿠팡: 네이버 링크가 {len(marks)}개예요 ({limit}개 이하, 교체·구매 문단에만)")
    disclosure = cfg.get("disclosure", "")
    body = plain(md)
    pos = body.find(disclosure) if disclosure else -1
    if pos < 0:
        out.append(f'쿠팡: 대가성 문구가 없거나 바뀌었어요 → "{disclosure}" 그대로')
    elif pos > 80:
        out.append("쿠팡: 대가성 문구는 본문 첫 부분(첫 줄)에 있어야 해요 (공정위 심사지침, 더보기·글 끝 안 됨)")
    for label, t in {"네이버": md, **social}.items():
        for w in VAGUE:
            if w in t:
                out.append(f'{label}: "{w}" 같은 모호한·오해 표현은 쓰지 않아요 (공정위 심사지침)')
    # 시험 기간: 링크 넣은 네이버 글 수 제한
    until = cfg.get("test_until")
    if until and post.get("id", "")[:10] <= until:
        n = 0
        for f in (ROOT / "posts").glob("*/post.json"):
            other = json.loads(f.read_text(encoding="utf-8"))
            if other.get("id") != post.get("id") and (other.get("affiliate") or {}).get("items") and other.get("id", "")[:10] <= until:
                n += 1
        if n + 1 > cfg.get("test_max_posts", 3):
            out.append(f"쿠팡: 시험 기간({until}까지)엔 링크 글을 {cfg.get('test_max_posts', 3)}편까지만 (이미 {n}편)")
    return out


def check(post_dir):
    post_dir = Path(post_dir).resolve()
    post = json.loads((post_dir / "post.json").read_text(encoding="utf-8"))
    terms = json.loads((ROOT / "config/terms.json").read_text(encoding="utf-8"))
    issues, info = [], {}

    def banned_in(label, text):
        for w in terms["banned"]:
            if w["term"] in text:
                issues.append(f'{label}: 확인 안 된 용어 "{w["term"]}" → {w["use"]}')

    # ---- 네이버 원고 ----
    if "naver" in post.get("platforms", []):
        md = (post_dir / "naver.md").read_text(encoding="utf-8")
        body = plain(md)
        info["naver_chars"] = len(body)
        if not 1800 <= len(body) <= 3800:
            issues.append(f"네이버: 글자 수 {len(body)}자 (권장 1,800~3,800자)")
        first = body[:120]
        if any(g in first for g in GREETINGS):
            issues.append("네이버: 첫 문장이 인사·날씨로 시작해요 (독자 상황으로 시작)")
        if md.count("[인용구-요약]") < 1:
            issues.append("네이버: 결론 요약 인용구가 없어요")
        if md.count("[인용구-팁]") < 1:
            issues.append("네이버: 현장 팁 인용구가 없어요")
        if "|" not in md:
            issues.append("네이버: 표가 없어요")
        subs = re.findall(r"^\*\*(.+?)\*\*\s*$", md, re.M)
        if len(subs) < 3:
            issues.append(f"네이버: 소제목이 {len(subs)}개예요 (3개 이상)")
        if COUPANG_URL.search(md):
            issues.append("네이버: 쿠팡 주소를 직접 쓰지 말고 [쿠팡: 키 | 링크 문구] 표시로 넣어요 (topics/coupang_links.json)")
        if len(URL.findall(md)) > 1:
            issues.append("네이버: 외부 링크가 2개 이상이에요 (최대 1개)")
        if any(w in body for w in AD_WORDS):
            issues.append("네이버: 광고 클릭 유도 문구가 있어요")
        if re.search(r"\d[\d,]*\s*원", body) and "기준" not in body:
            issues.append('네이버: 가격이 있는데 "○년 ○월 기준" 표기가 없어요')
        if md.count("[형광]") > 3:
            issues.append("네이버: 형광 강조가 너무 많아요 (3개 이하)")
        banned_in("네이버", body)
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from naver_markdown import card_captions, check as md_check, convert
        converted, _ = convert(md, captions=card_captions(post_dir))
        for prob in md_check(converted):
            issues.append("네이버 업로드 형식: " + prob)
        missing = [k for k in re.findall(r"\{(card\d\d)\}", converted) if not (post_dir / "cards" / f"{k[4:]}.jpg").exists() and (post_dir / "cards.json").exists()]
        if missing:
            issues.append(f"네이버: 본문에 넣을 카드 이미지가 없어요 {missing}")
        title = post["title"]
        kw = post.get("keywords", {}).get("main", "")
        if kw and kw.replace(" ", "") not in title.replace(" ", "")[:24]:
            issues.append(f'제목: 핵심 키워드 "{kw}"가 앞쪽에 없어요')
        if len(title) > 45:
            issues.append(f"제목: {len(title)}자로 길어요 (45자 이하)")
        # 예전 글과 겹침 (네이버 유사문서 예방)
        mine = ngrams(md)
        for other in (ROOT / "posts").glob("*/naver.md"):
            if other.parent == post_dir:
                continue
            o = ngrams(other.read_text(encoding="utf-8"))
            if mine and o:
                sim = len(mine & o) / len(mine | o)
                if sim > 0.25:
                    issues.append(f"네이버: 예전 글 {other.parent.name}과 문장이 많이 겹쳐요 ({sim:.0%})")
        used = json.loads((ROOT / "topics/used.json").read_text(encoding="utf-8"))
        if any(u["title"] == title and u["id"] != post["id"] for u in used):
            issues.append("제목: 예전에 쓴 제목과 같아요")
        if not post.get("terms_evidence"):
            issues.append("용어 근거가 비어 있어요 (쇼핑몰 상품명 등에서 확인한 용어를 적어야 해요)")
        # 검색량: 글에 적은 숫자는 반드시 키워드 도구 조회 결과와 같아야 해요 (지어낸 숫자 방지)
        vol = post.get("keywords", {}).get("volume")
        if vol:
            kwf = ROOT / "topics/keywords.json"
            saved = json.loads(kwf.read_text(encoding="utf-8"))["keywords"] if kwf.exists() else {}
            for k, v in vol.items():
                e = saved.get(k.replace(" ", ""))
                if not e:
                    issues.append(f'검색량: "{k}"는 키워드 도구로 조회한 기록이 없어요 (topics/keywords.json)')
                else:
                    # 그날 조회한 값과 대조 (키워드는 일·화·목마다 다시 조회되니 history 에서 찾아요)
                    hist = dict(e.get("history") or {})
                    if e.get("checked"):
                        hist[e["checked"]] = e.get("total")
                    if v.get("checked") not in hist:
                        issues.append(f'검색량: "{k}"를 {v.get("checked")}에 조회한 기록이 없어요 (기록된 날짜 {", ".join(sorted(hist))})')
                    elif v.get("total") != hist[v["checked"]]:
                        issues.append(f'검색량: "{k}" 숫자가 {v["checked"]} 조회 기록({hist[v["checked"]]})과 달라요')
        # 브리프: 누구의 어떤 질문에 무엇으로 답하는 글인지 (쓰기 전에 정함)
        brief = post.get("brief") or {}
        missing_b = [k for k in BRIEF_KEYS if not str(brief.get(k, "")).strip()]
        if missing_b:
            issues.append(f"브리프가 비어 있어요: {', '.join(missing_b)} (독자·질문·핵심 답·다루지 않을 것·다음 행동)")
        # 키워드 채우기 (횟수를 채우면 오히려 읽기 불편하고 스팸 정책 대상)
        if kw:
            n = body.replace(" ", "").count(kw.replace(" ", ""))
            limit = len(body) // 250 + 2
            info["keyword_count"] = n
            if n > limit:
                issues.append(f'네이버: 핵심 키워드 "{kw}"가 {n}번 나와요 (이 길이면 {limit}번 이하, 필요한 곳에만)')

    # ---- 쿠팡 파트너스 ----
    issues += check_coupang(post, post_dir)

    # ---- 인스타 캡션 ----
    if "instagram" in post.get("platforms", []):
        cap = post["instagram"]["caption"]
        info["ig_chars"] = len(cap)
        tags = re.findall(r"#\S+", cap)
        if len(cap) > 2200:
            issues.append(f"인스타: 캡션 {len(cap)}자 (2,200자 이하)")
        if len(tags) > 5:
            issues.append(f"인스타: 해시태그 {len(tags)}개 (인스타 규정상 5개 이하)")
        if URL.search(cap):
            issues.append("인스타: 캡션 링크는 눌리지 않아요 ('프로필 링크'로 안내)")
        if len(cap.split("\n")[0]) > 60:
            issues.append("인스타: 첫 줄이 길어요 (더보기 전에 보이는 첫 줄은 60자 이하)")
        banned_in("인스타", cap)
        qa = post_dir / "cards/qa.json"
        if not qa.exists() or not json.loads(qa.read_text(encoding="utf-8"))["ok"]:
            issues.append("인스타: 카드 이미지 점검을 통과하지 못했어요")

    # ---- 스레드 ----
    if "threads" in post.get("platforms", []):
        posts = post["threads"]["posts"]
        for i, t in enumerate(posts):
            label = "스레드 본문" if i == 0 else f"스레드 댓글{i}"
            n = len(t.replace("[네이버 글 링크]", "https://blog.naver.com/cafe_peanut/000000000000"))
            if n > 500:
                issues.append(f"{label}: {n}자 (500자 이하)")
            if i < len(posts) - 1 and (URL.search(t) or "[네이버 글 링크]" in t):
                issues.append(f"{label}: 링크는 마지막 댓글에만 넣어요")
            if len(re.findall(r"#\S+", t)) > 1:
                issues.append(f"{label}: 스레드 주제 태그는 1개만")
            banned_in(label, t)
        if "[네이버 글 링크]" not in posts[-1] and not URL.search(posts[-1]):
            issues.append("스레드: 마지막 댓글에 블로그 링크 자리가 없어요")

    # ---- 공통: 과장 표현, 남은 작업 메모, 확인 안 된 경험담 ----
    texts = {"제목": post.get("title", "")}
    if (post_dir / "naver.md").exists():
        texts["네이버"] = (post_dir / "naver.md").read_text(encoding="utf-8")
    if post.get("instagram"):
        texts["인스타"] = post["instagram"].get("caption", "")
    if post.get("threads"):
        texts["스레드"] = "\n".join(post["threads"].get("posts", []))
    exp_ok = experience_ids()
    used_exp = post.get("experience_used") or []
    for label, text in texts.items():
        for w in HYPE:
            if w.lower() in text.lower():
                issues.append(f'{label}: 근거 없는 과장 표현 "{w}" (본문이 실제로 보여주는 범위로 바꾸기)')
        for w in MEMO:
            if w in text:
                issues.append(f'{label}: 작업 메모 "{w}"가 남아 있어요')
        said = [w for w in EXPERIENCE if w in text]
        if said and not any(exp_ok.get(e) for e in used_exp):
            issues.append(f'{label}: 경험 표현 "{said[0]}"이 있는데 확인된 경험 기록이 없어요 '
                          f'(topics/experience.md 에 사장님 확인 기록 → post.json experience_used)')
    for e in used_exp:
        if e not in exp_ok:
            issues.append(f"경험 기록 {e}가 topics/experience.md 에 없어요")
        elif not exp_ok[e]:
            issues.append(f"경험 기록 {e}는 아직 사장님 확인 전이에요")

    result = {"ok": not issues, "issues": issues, "info": info}
    (post_dir / "text_qa.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    r = check(sys.argv[1])
    if r["ok"]:
        print("글 점검 통과", r["info"])
    else:
        print("글 점검 실패:\n- " + "\n- ".join(r["issues"]))
        sys.exit(1)
