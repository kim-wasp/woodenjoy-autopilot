"""오늘의 이슈를 숫자로 고르기 (정치 블로그 글감용)

1) 구글 트렌드 한국 실시간 인기 검색어 (검색 급증, 대략 검색 수)
2) 구글 뉴스 RSS (최근 24시간·6시간 기사 수, 헤드라인)
네이버 검색 API는 쓰지 않아요: 2026-09-07 약관 개정으로 검색 결과를 AI에 넣거나 광고 수익화에 쓰는 것이 금지됐고,
개발자센터 신규 신청도 2026-07-30에 끝났어요.
"""
import html
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from common import log, now_kst, secret

TRENDS_URLS = ["https://trends.google.com/trending/rss?geo=KR", "https://trends.google.co.kr/trending/rss?geo=KR"]
POOL_QUERIES = ["국회", "대통령실", "더불어민주당", "국민의힘", "본회의 법안", "외교부", "정부 발표", "선거"]
UA = {"User-Agent": "Mozilla/5.0 (studio trends)"}


def _txt(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _traffic(s):
    """'2,000+' / '2만+' → 숫자"""
    s = (s or "").replace(",", "").replace("+", "").strip()
    m = re.match(r"([\d.]+)\s*(만|천|K|M)?", s, re.I)
    if not m:
        return 0
    n = float(m.group(1))
    return int(n * {"만": 10000, "천": 1000, "k": 1000, "m": 1000000}.get((m.group(2) or "").lower(), 1))


def google_trends():
    for url in TRENDS_URLS:
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200 and "<item>" in r.text:
                return parse_trends(r.text)
        except requests.RequestException as e:
            log(f"  구글 트렌드 읽기 실패: {e}")
    log("  구글 트렌드를 못 읽었어요 → 네이버 기사 수만으로 골라요")
    return []


def parse_trends(xml):
    out = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", it, re.S) or [None, ""])[1]  # noqa: E731
        news = [{"title": _txt(t), "url": _txt(u), "source": _txt(s)} for t, u, s in
                re.findall(r"<ht:news_item_title>(.*?)</ht:news_item_title>.*?<ht:news_item_url>(.*?)</ht:news_item_url>.*?<ht:news_item_source>(.*?)</ht:news_item_source>", it, re.S)]
        out.append({"keyword": _txt(g("title")), "traffic": _traffic(_txt(g("ht:approx_traffic"))), "traffic_label": _txt(g("ht:approx_traffic")), "news": news[:3]})
    return out


def has_naver():
    return False  # 약관상 쓰지 않아요 (위 설명)


def _gnews(query, window="1d"):
    """구글 뉴스 RSS (열쇠 필요 없음, 최근 기사 최대 100개) → 네이버 형식으로"""
    r = requests.get("https://news.google.com/rss/search", params={"q": f"{query} when:{window}", "hl": "ko", "gl": "KR", "ceid": "KR:ko"}, headers=UA, timeout=20)
    r.raise_for_status()
    out = []
    for it in re.findall(r"<item>(.*?)</item>", r.text, re.S):
        g = lambda tag: (re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", it, re.S) or [None, ""])[1]  # noqa: E731
        out.append({"title": g("title"), "link": _txt(g("link")), "pubDate": _txt(g("pubDate")), "description": ""})
    return out


def _naver(query, start=1):
    if not has_naver():
        return _gnews(query) if start == 1 else []
    r = requests.get("https://openapi.naver.com/v1/search/news.json", timeout=20,
                     params={"query": query, "display": 100, "start": start, "sort": "date"},
                     headers={"X-Naver-Client-Id": secret("NAVER_CLIENT_ID"), "X-Naver-Client-Secret": secret("NAVER_CLIENT_SECRET")})
    r.raise_for_status()
    return r.json().get("items", [])


def _recent(items, since):
    out = []
    for i in items:
        try:
            if parsedate_to_datetime(i["pubDate"]) >= since:
                out.append(i)
        except (KeyError, TypeError, ValueError):
            pass
    return out


def news_pool(hours=24):
    """정치 관련 최근 헤드라인 모음 (AI가 이슈를 묶는 재료)"""
    since = now_kst() - timedelta(hours=hours)
    seen, pool = set(), []
    for q in POOL_QUERIES:
        try:
            for i in _recent(_naver(q), since):
                t = _txt(i.get("title"))
                k = re.sub(r"\W", "", t)[:30]
                if k in seen:
                    continue
                seen.add(k)
                pool.append({"title": t, "desc": _txt(i.get("description"))[:60], "url": i.get("originallink") or i.get("link")})
        except requests.RequestException as e:
            log(f"  네이버 뉴스 '{q}' 실패: {e}")
    return pool


def source_name():
    return "네이버 뉴스" if has_naver() else "구글 뉴스"


def count_24h(query, hours=24, max_pages=5):
    """최근 24시간 기사 수 (최대 500건까지 셈) + 최근 기사 3개"""
    since = now_kst() - timedelta(hours=hours)
    n, top = 0, []
    for p in range(max_pages):
        try:
            items = _naver(query, 1 + p * 100)
        except requests.RequestException as e:
            log(f"  기사 수 세기 실패 '{query}': {e}")
            break
        rec = _recent(items, since)
        n += len(rec)
        top += [{"title": _txt(i.get("title")), "url": i.get("originallink") or i.get("link")} for i in rec[:3 - len(top)]] if len(top) < 3 else []
        if len(rec) < len(items) or len(items) < 100:
            break
    return n, top


def count_6h(query):
    """기사가 100건을 넘어 24시간 수로 순위가 안 갈릴 때: 최근 6시간 기사 수"""
    try:
        return len(_gnews(query, "6h"))
    except requests.RequestException:
        return 0


def trend_match(keyword, trends):
    """후보 키워드와 겹치는 구글 트렌드 검색어의 검색 수"""
    k = keyword.replace(" ", "")
    best = None
    for t in trends:
        tk = t["keyword"].replace(" ", "")
        if tk and (tk in k or k in tk or any(w in tk for w in keyword.split() if len(w) >= 3)):
            if not best or t["traffic"] > best["traffic"]:
                best = t
    return best


def naver_volume(keyword):
    """네이버 월간 검색 수 (검색광고 키워드 도구, PC+모바일). 검색 API가 아니라서 약관 문제 없음.
    키워드 도구는 띄어쓰기 없는 단어만 받아요. 못 읽으면 None."""
    import os, sys
    from pathlib import Path
    if not os.environ.get("NAVER_AD_API_KEY"):
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    try:
        import keywords as kt
        w = re.sub(r"\s+", "", keyword or "")[:30]
        if not w:
            return None
        for it in kt.ad_request([w], False):
            if kt.norm(it.get("relKeyword", "")) == w:
                return kt.to_int(it.get("monthlyPcQcCnt", 0)) + kt.to_int(it.get("monthlyMobileQcCnt", 0))
        return 0
    except Exception as e:  # noqa: BLE001
        log(f"  네이버 검색량 실패 '{keyword}': {e}")
        return None


def naver_creator_trends(days=7):
    """사장님이 관리화면 '트렌드'에 붙여넣은 네이버 크리에이터 어드바이저 인기·급등 검색어 (최근 days일).
    크리에이터 어드바이저는 공개 API가 없어 자동 수집하지 않고, 사장님이 직접 본 것만 써요."""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "status/naver_trends.json"
    if not f.exists():
        return []
    try:
        entries = json.loads(f.read_text(encoding="utf-8")).get("entries", [])
    except Exception:  # noqa: BLE001
        return []
    out, seen = [], set()
    for e in entries:
        try:
            at = datetime.fromisoformat(e["at"].replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            continue
        if (now_kst() - at).days > days:
            continue
        for k in e.get("keywords", []):
            if k not in seen:
                seen.add(k)
                out.append({"keyword": k, "label": e.get("label", ""), "date": at.astimezone(now_kst().tzinfo).strftime("%m-%d")})
    return out


def auto_trends(site_id):
    """tools/trend_watch.py 가 매일 만든 급등 검색어 (네이버 검색광고 키워드 도구 + 구글 트렌드)"""
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent.parent / "status/trends_auto.json"
    if not f.exists():
        return {}
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    upd = d.get("updated", "")
    try:
        if (now_kst() - datetime.fromisoformat(upd)).days > 3:
            return {}
    except Exception:  # noqa: BLE001
        return {}
    return {"updated": upd, "site": (d.get("sites") or {}).get(site_id) or {}, "google": d.get("google") or []}


def naver_trends_block(site_id=None, days=7):
    parts = []
    a = auto_trends(site_id) if site_id else {}
    r = (a.get("site") or {}).get("rising") or []
    if r:
        parts.append("[이 사이트 분야 급등 검색어 — 네이버 검색광고 키워드 도구, 최근 30일 검색 수를 매일 재서 7일 전과 비교 (" + a["updated"][:10] + ")]\n"
                     + "\n".join(f"- {x['keyword']}: 월 {x['now']:,}회" + (f" (7일 전 {x['before']:,}회, +{int(x['change'] * 100)}%)" if x.get("before") else " (새로 등장)") for x in r[:20]))
    top = (a.get("site") or {}).get("top") or []
    if top:
        parts.append("[이 사이트 분야 검색 많은 말 — 같은 자료]\n" + ", ".join(f"{x['keyword']}({x['now']:,})" for x in top[:15]))
    g = a.get("google") or []
    if g:
        parts.append("[구글 트렌드 한국 실시간 인기 검색어 — 사회적으로 갑자기 뜬 이슈. 이 사이트 주제와 관련 있는 것만 참고]\n"
                     + "\n".join(f"- {x['keyword']} ({x['traffic']})" + (": " + " / ".join(x["news"]) if x.get("news") else "") for x in g[:15]))
    t = naver_creator_trends(days)
    if t:
        parts.append("[네이버 크리에이터 어드바이저 인기·급등 검색어 — 사장님이 직접 확인해 붙여넣은 것]\n"
                     + "\n".join(f"- {x['keyword']}" + (f" ({x['label']}, {x['date']})" if x["label"] else f" ({x['date']})") for x in t[:40]))
    if not parts:
        return ""
    return ("\n\n".join(parts) + "\n"
            "트렌드 쓰는 법: 1) 글감을 고를 때 이 사이트 주제와 맞는 급등 검색어가 있으면 우선 고려하고, 고른 근거(why_this_topic)에 그 숫자를 적어요. "
            "2) 글을 쓸 때 이 글과 직접 관련 있는 검색어가 있으면 제목·소제목·본문에 자연스럽게 1~2번 넣어요(같은 뜻의 말을 사람들이 실제로 치는 표현으로 바꾸는 정도). "
            "3) 관련 없는 검색어를 억지로 끼워 넣거나 나열하지 말아요. 검색어에 담긴 사실(사건·숫자)은 확인된 것만.")
