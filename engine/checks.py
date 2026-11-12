"""글 점검 (모든 사이트 공통). 문제 목록을 돌려줘요. 빈 목록이면 통과.

- 블로그: 길이, 소제목 수, 표, 출처, 이미지 자리, 남은 작업 메모, 과장 표현, 키워드 반복
- 인스타: 2,200자, 해시태그 5개, 링크 금지, 첫 줄 길이
- 스레드: 각 500자, 링크는 마지막에만
- 공통: 사이트 금지어, AI 티(im-not-ai 점수기, high 면 실패)
"""
import re
import sys

from common import ROOT

sys.path.insert(0, str(ROOT / "tools/humanize"))
try:
    import metrics_v2  # im-not-ai 점수기 (MIT)
except Exception:  # noqa: BLE001
    metrics_v2 = None

TH_BAIT = ["동의하면", "공감하면", "좋아요 눌러", "좋아요 꾹", "댓글 달아", "댓글로 알려", "동의?", "다들 어때", "너희 생각은"]
TH_STOCK = ["걱정 끝", "대방출", "총정리", "알아보자", "알아볼게", "결론부터 말하면", "솔직히 말할게", "핵심은:", "결과는?"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def threads_style(posts, topic_tag=None):
    """스레드 문구 점검 (threads-kr 스킬 규칙): 반응 낚시, AI 티, 이모지, 주제 태그"""
    out = []
    allt = "\n".join(posts)
    for w in TH_BAIT:
        if w in allt:
            out.append(f"반응 낚시 문구 '{w}' 빼기")
    for w in TH_STOCK:
        if w in allt:
            out.append(f"상투어 '{w}' 빼기")
    if "—" in allt or "–" in allt:
        out.append("대시(—) 대신 쉼표나 줄바꿈")
    if re.search(r"아니라[^\n.?!]{0,30}(야|거야|임)[.!]?(\s|$)", allt):
        out.append("'X가 아니라 Y야' 대구 대신 Y를 바로 말하기")
    if "‍" in allt:
        out.append("조합 이모지(가족·피부색 등) 빼기")
    if len(EMOJI.findall(allt)) > 2:
        out.append(f"이모지 {len(EMOJI.findall(allt))}개 → 2개 이하")
    if posts:
        first = posts[0].strip().split("\n")[0]
        if len(first) > 30:
            out.append(f"본문 첫 줄 {len(first)}자 → 한 줄 15자 안팎으로")
        lines = [x for x in posts[0].split("\n") if x.strip()]
        if len(lines) >= 5 and all(len(x) <= 20 for x in lines):
            out.append("한 문장 한 줄씩 늘어놓기 → 숨 쉴 자리에서만 줄바꿈")
    if topic_tag is not None:
        t = str(topic_tag).strip()
        if not t or len(t) > 20 or re.search(r"[.&#]", t):
            out.append(f"주제 태그 '{t}' → # 없이 20자 이내 1개, 마침표·& 금지")
    return out


IG_BAIT = ["YES 남겨", "댓글에 YES", "공감하면", "동의하면", "좋아요 눌러", "좋아요 꾹", "맞팔", "선팔"]


def caption_style(ig, post=None):
    """인스타 캡션 점검 (instagram-kr 스킬 규칙): 반응 낚시, AI 티, 이모지, 표지 반복"""
    out = []
    for w in IG_BAIT:
        if w in ig:
            out.append(f"반응 낚시 문구 '{w}' 빼기")
    for w in TH_STOCK:
        if w in ig:
            out.append(f"상투어 '{w}' 빼기")
    if "—" in ig or "–" in ig:
        out.append("대시(—) 대신 쉼표나 줄바꿈")
    if re.search(r"아니라[^\n.?!]{0,30}(예요|이에요|입니다)[.!]?(\s|$)", ig):
        out.append("'X가 아니라 Y예요' 대구 대신 Y를 바로 말하기")
    n = len(EMOJI.findall(ig))
    if n > 3:
        out.append(f"이모지 {n}개 → 3개 이하")
    cover = ((post or {}).get("instagram") or {}).get("cover_hooks") or []
    first = ig.strip().split("\n")[0].replace(" ", "")
    if first and any(first == str(c).replace("*", "").replace("\n", "").replace(" ", "") for c in cover[:1]):
        out.append("캡션 첫 줄이 표지 문구와 똑같아요 (다른 각도로)")
    return out


HYPE = ["무조건", "100%", "완벽 정리", "완벽하게", "최고의", "BEST", "베스트", "가장 쉬운", "누구나 쉽게", "보장합니다",
        "상위노출", "상위 노출", "기적", "단 하나의 비밀"]
MEMO = ["[확인 필요]", "TODO", "검토 메모", "실습 예시", "(예시)", "XXX", "{LINK}"]
URL = re.compile(r"https?://\S+")


def ai_tell(text, genre="blog"):
    if not metrics_v2 or len(text) < 200:
        return None
    try:
        return metrics_v2.compute_all_v2(text, genre=genre)["risk_band"]
    except Exception:  # noqa: BLE001
        return None


# 앞 글자가 한글이 아닐 때만(문제가, 경제가 같은 말은 빼려고)
FIRST_PERSON = re.compile(r"(?<![가-힣])(저는|제가|저도|저희|제 경험|제 주변)|(해보니|써보니|먹어보니|겪어보니|마셔보니)")


def plain(md):
    t = re.sub(r"\[\[[^\]]+\]\]", "", md)
    t = re.sub(r"^\|.*\|$", "", t, flags=re.M)
    return re.sub(r"[#>*\-|]", "", t)


def check(site, post, article_md=None):
    issues = []
    rules = site.get("rules", {})
    banned = rules.get("banned_words", [])
    texts = {"제목": post.get("title", "")}

    if site.get("blog", {}).get("platform") and site["blog"]["platform"] != "none":
        md = article_md or ""
        body = plain(md)
        n = len(re.sub(r"\s+", " ", body).strip())
        lo, hi = rules.get("min_chars", 2500), rules.get("max_chars", 6000)
        if not lo <= n <= hi:
            issues.append(f"블로그: 글자 수 {n}자 (기준 {lo:,}~{hi:,}자)")
        h2 = len(re.findall(r"^## ", md, re.M))
        if h2 < 3:
            issues.append(f"블로그: 소제목(##)이 {h2}개 (3개 이상)")
        if rules.get("require_table", True) and not re.search(r"^\|.*\|$", md, re.M):
            issues.append("블로그: 표가 없어요")
        static = site["blog"]["platform"] == "static"
        if static:
            # 짧은 글 형식: 한 줄 결론, 핵심은 짧게, 나머지는 '더 자세히'로
            if not post.get("conclusion"):
                issues.append("블로그: 한 줄 결론(conclusion)이 없어요")
            if not re.search(r"^## 더 자세히", md, re.M):
                issues.append("블로그: '## 더 자세히' 칸이 없어요")
            core = plain(re.split(r"^## (?:편집자 생각|더 자세히)", md, maxsplit=1, flags=re.M)[0])
            core_n = len(re.sub(r"\s+", " ", core).strip())
            if core_n > rules.get("core_max_chars", 1200):
                issues.append(f"블로그: 핵심 부분이 {core_n}자 (짧고 쉽게 {rules.get('core_max_chars', 1200)}자 이내로)")
            if rules.get("require_sources", True) and not post.get("sources"):
                issues.append("블로그: 출처(sources)가 없어요")
        elif rules.get("require_sources", True) and not re.search(r"^## (참고|출처)", md, re.M):
            issues.append("블로그: '## 참고 자료' 출처 목록이 없어요")
        if not static and "[[hero]]" not in md and not re.search(r"\[\[(card|photo):\d+\]\]", md):
            issues.append("블로그: 본문 이미지 자리([[hero]]·[[card:N]]·[[photo:N]])가 없어요")
        if re.search(r"광고(를)? (클릭|눌러)", md):
            issues.append("블로그: 광고 클릭 유도 문구 (애드센스·애드포스트 정책 위반)")
        if "link.coupang.com" in md and "쿠팡 파트너스 활동" not in md:
            issues.append("블로그: 쿠팡 링크가 있는데 대가성 문구가 없어요")
        kw = (post.get("keywords") or {}).get("main", "").replace(" ", "")
        if kw:
            cnt = body.replace(" ", "").count(kw)
            if cnt > n // 250 + 3:
                issues.append(f"블로그: 핵심 키워드 '{kw}' {cnt}번 반복 (줄이기)")
        texts["블로그"] = md
        band = ai_tell(body)
        if band == "high":
            issues.append("블로그: AI 티가 강해요 (번역투·AI 관용구·같은 끝맺음 반복 줄이기)")

    ig = (post.get("instagram") or {}).get("caption")
    if ig is not None:
        if len(ig) > 2200:
            issues.append(f"인스타: 캡션 {len(ig)}자 (2,200자 이하)")
        tags = re.findall(r"#\S+", ig)
        if len(tags) > 5:
            issues.append(f"인스타: 해시태그 {len(tags)}개 (5개 이하)")
        if URL.search(ig):
            issues.append("인스타: 캡션 링크는 눌리지 않아요 (프로필 링크로 안내)")
        if len(ig.split("\n")[0]) > 60:
            issues.append("인스타: 첫 줄이 60자 넘어요")
        issues += [f"인스타: {x}" for x in caption_style(ig, post)]
        texts["인스타"] = ig

    th = (post.get("threads") or {}).get("posts")
    if th is not None:
        if not 1 <= len(th) <= 5:
            issues.append(f"스레드: 글이 {len(th)}개 (1~5개)")
        for i, t in enumerate(th):
            body = t.replace("{LINK}", "https://x.kr/xxxxxxxxxxxx")
            if len(body) > 500:
                issues.append(f"스레드 {i + 1}: {len(body)}자 (500자 이하)")
            if i < len(th) - 1 and ("{LINK}" in t or URL.search(t)):
                issues.append(f"스레드 {i + 1}: 링크는 마지막 글에만")
        if th and len(th[0]) > 250:
            issues.append(f"스레드 본문: {len(th[0])}자 (짧게, 250자 이하)")
        jon = sum(len(re.findall(r"(요|니다|세요)[.!?]?(\s|$)", t)) for t in th)
        if jon > 1:
            issues.append(f"스레드: 존댓말 문장 {jon}개 (친근한 반말로)")
        issues += [f"스레드: {x}" for x in threads_style(th, (post.get("threads") or {}).get("topic_tag"))]
        texts["스레드"] = "\n".join(th)

    for label, text in texts.items():
        for w in HYPE:
            if w.lower() in text.lower():
                issues.append(f"{label}: 근거 없는 과장 표현 '{w}'")
        for w in MEMO:
            if w in text and not (w == "{LINK}" and label == "스레드"):
                issues.append(f"{label}: 작업 메모 '{w}'가 남아 있어요")
        for w in banned:
            if w in text:
                issues.append(f"{label}: 금지어 '{w}'")
        if rules.get("no_first_person"):
            for m in FIRST_PERSON.finditer(text):
                issues.append(f"{label}: 1인칭 체험담 표현 '{m.group(0)}' (편집팀이 자료를 정리한 글이라 경험담 금지)")
                break
    return issues
