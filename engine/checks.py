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
        if rules.get("require_sources", True) and not re.search(r"^## (참고|출처)", md, re.M):
            issues.append("블로그: '## 참고 자료' 출처 목록이 없어요")
        if "[[hero]]" not in md and not re.search(r"\[\[(card|photo):\d+\]\]", md):
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
    return issues
