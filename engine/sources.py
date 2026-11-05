"""참고 자료·본문 링크 검증: 실제로 열리는 주소만 남겨요.
- 연결 실패, 404/410, 서비스가 끝난 주소(예: 다음 블로그)는 빼요
- 403·429처럼 '로봇 접근만 막는' 응답은 사람은 열 수 있어서 남겨요
"""
import re

import requests

DEAD_HOSTS = ("blog.daum.net", "cafe.daum.net/_c21_", "plus.google.com", "blog.me/")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
      "Accept-Language": "ko-KR,ko;q=0.9"}
_cache = {}


def alive(url):
    if url in _cache:
        return _cache[url]
    ok = True
    if any(h in url for h in DEAD_HOSTS):
        ok = False
    else:
        try:
            r = requests.get(url, headers=UA, timeout=12, allow_redirects=True, stream=True)
            ok = r.status_code < 400 or r.status_code in (401, 403, 405, 429, 999)
            r.close()
        except requests.RequestException:
            ok = False
    _cache[url] = ok
    return ok


LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def verify_article(md, keep_hosts=("link.coupang.com", "blog.naver.com/cafe_peanut", "commonsense-one.vercel.app", "myinfobay.com")):
    """반환: (고친 글, 뺀 주소 목록). 참고 자료 줄은 통째로 빼고, 본문 링크는 글자만 남겨요."""
    removed = []
    out = []
    in_refs = False
    for line in md.split("\n"):
        if line.startswith("## "):
            in_refs = bool(re.match(r"## (참고|출처)", line))
        links = LINK.findall(line)
        bad = [(t, u) for t, u in links if not any(k in u for k in keep_hosts) and not alive(u)]
        if bad:
            removed += [u for _, u in bad]
            if in_refs and line.lstrip().startswith(("-", "*", "1", "2", "3", "4", "5", "6", "7", "8", "9")):
                continue
            for t, u in bad:
                line = line.replace(f"[{t}]({u})", t)
        out.append(line)
    return "\n".join(out), removed
