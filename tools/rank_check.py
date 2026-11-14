"""발행한 글의 네이버 검색 순위 확인 (uplika 경유: 사장님 브라우저의 uplika 확장이 네이버 통합검색 공개 화면을 읽어요).

- 대상: 콘텐츠 스튜디오로 올린 글 중 발행 후 30일 안의 글. 발행 1·3·7·14·30일째에 한 번씩 (하루 최대 40개 검색어)
- 검색어: 글의 핵심 키워드(keywords.main)
- 네이버 블로그 글은 블로그 아이디로, 다른 사이트 글은 주소(도메인)로 결과 목록에서 찾아요
- 결과: status/ranks.json (스튜디오 '순위' 화면, 다음 글감 고르기에 참고)
- 구글 순위는 서치콘솔 연결(구글 클라우드)이 필요해서 아직 없어요
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
NOW = datetime.now(KST)
CHECK_DAYS = (1, 3, 7, 14, 30)
MAX_KEYWORDS = 40
OUT = ROOT / "status/ranks.json"


def check(args):
    """uplika REST: 네이버 통합검색 확인 (사장님 계정 전체 범위 키 필요 → UPLIKA_RESEARCH_KEY)"""
    import time
    key = os.environ.get("UPLIKA_RESEARCH_KEY") or os.environ.get("UPLIKA_API_KEY")
    h = {"authorization": f"Bearer {key}", "content-type": "application/json"}
    for _ in range(12):  # 다른 확인이 돌고 있으면(429 naver_search_busy) 기다렸다 다시
        r = requests.post("https://api.uplika.com/v1/naver/visibility/checks", json=args, headers=h, timeout=120)
        if r.status_code != 429:
            break
        try:
            wait = int(r.json()["error"].get("retryAfterSeconds") or 40)
        except Exception:  # noqa: BLE001
            wait = 40
        print(f"  다른 확인이 진행 중이라 {wait}초 뒤 다시")
        time.sleep(min(wait, 90))
    if r.status_code >= 400:
        raise RuntimeError(f"uplika {r.status_code}: {r.text[:300]}")
    res = r.json()
    res = res.get("data", res) if isinstance(res, dict) else res
    for _ in range(12):  # 확장이 아직 읽는 중이면 잠시 뒤 결과 다시 받기
        if not (res.get("partial") and res.get("pending") and res.get("runId")):
            break
        time.sleep(30)
        g = requests.get(f"https://api.uplika.com/v1/naver/visibility/runs/{res['runId']}", headers=h, timeout=60)
        if g.status_code >= 400:
            break
        res = g.json().get("data", g.json())
    return res


def targets(data):
    out = []
    for f in sorted((ROOT / "content").glob("*/*/post.json")):
        p = json.loads(f.read_text(encoding="utf-8"))
        pub = p.get("published") or {}
        url, at = pub.get("blog_url"), pub.get("blog_at")
        kw = ((p.get("keywords") or {}).get("main") or "").strip()
        if not (url and at and kw):
            continue
        age = (NOW - datetime.fromisoformat(at)).days
        if age > 31:
            continue
        rec = data["posts"].get(url) or {}
        last = max([c["day"] for c in rec.get("checks", [])] or [0])  # 늦게 확인한 날 이전 차수는 건너뜀
        due = [d for d in CHECK_DAYS if last < d <= max(age, 0)]
        if age >= 1 and due:
            out.append({"url": url, "keyword": kw, "title": p.get("title", ""), "site": p.get("site") or f.parts[-3], "age": age, "day": due[-1]})
    return out[:MAX_KEYWORDS]


def main():
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"posts": {}}
    if not (os.environ.get("UPLIKA_RESEARCH_KEY") or os.environ.get("UPLIKA_API_KEY")):
        print("uplika 키가 없어서 건너뜀"); return
    todo = targets(data)
    print(f"확인할 글 {len(todo)}개")
    if not todo:
        return
    data.pop("last_error", None)
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        naver = [t for t in batch if "blog.naver.com" in t["url"]]
        blog = urlparse(naver[0]["url"]).path.strip("/").split("/")[0] if naver else None
        args = {"keywords": sorted({t["keyword"] for t in batch})}
        if blog:
            args["blog"] = blog
        try:
            res = check(args)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "bridge_offline" in msg:
                msg = "uplika 확장이 켜진 브라우저가 없어서 다음 시간에 다시 시도"
            print("순위 확인 실패:", msg)
            data["last_error"] = msg[:300]
            break
        if res.get("partial") and res.get("pending"):
            print("확장이 아직 읽는 중인 검색어:", res["pending"])
        by_kw = {r["keyword"]: r for r in res.get("results") or []}
        missing = [t["keyword"] for t in batch if t["keyword"] not in by_kw or by_kw[t["keyword"]].get("error")]
        if missing:
            print("  결과 없음:", missing, {k: by_kw[k].get("error") for k in missing if k in by_kw})
        for t in batch:
            r = by_kw.get(t["keyword"])
            if not r or r.get("error"):
                continue
            host = urlparse(t["url"]).netloc.replace("www.", "")
            rank, area = None, None
            for o in r.get("organic") or []:
                ou = o.get("url", "")
                if ou.rstrip("/") == t["url"].rstrip("/") or ("blog.naver.com" not in t["url"] and host in ou) or \
                        ("blog.naver.com" in t["url"] and o.get("logNo") and o["logNo"] in t["url"]):
                    rank, area = o.get("order"), o.get("area")
                    break
            v = r.get("verdict") or {}
            rec = data["posts"].setdefault(t["url"], {"title": t["title"], "keyword": t["keyword"], "site": t["site"], "checks": []})
            rec["checks"].append({"day": t["day"], "at": r.get("checkedAt"), "rank": rank, "area": area,
                                  "read": r.get("organicRead", True), "briefing": bool(r.get("briefing")), "cited": bool(v.get("cited"))})
            print(f"  {t['site']} {t['keyword']}: {rank or '10위 밖'} ({t['day']}일째)")
    data["updated"] = NOW.isoformat(timespec="minutes")
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
