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


def mcp(name, args):
    r = requests.post("https://api.uplika.com/mcp", timeout=120,
                      headers={"authorization": f"Bearer {os.environ['UPLIKA_API_KEY']}", "content-type": "application/json",
                               "accept": "application/json, text/event-stream"},
                      json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})
    t = r.text
    if t.startswith("event:") or "\ndata:" in t or t.startswith("data:"):
        t = [ln[5:].strip() for ln in t.splitlines() if ln.startswith("data:")][-1]
    j = json.loads(t)
    if "error" in j:
        raise RuntimeError(str(j["error"])[:300])
    res = j.get("result") or {}
    for c in res.get("content") or []:
        if c.get("type") == "text":
            try:
                return json.loads(c["text"])
            except ValueError:
                raise RuntimeError(c["text"][:300])
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
        done = {c["day"] for c in rec.get("checks", [])}
        due = [d for d in CHECK_DAYS if d <= max(age, 0) and d not in done]
        if age >= 1 and due:
            out.append({"url": url, "keyword": kw, "title": p.get("title", ""), "site": p.get("site") or f.parts[-3], "age": age, "day": due[-1]})
    return out[:MAX_KEYWORDS]


def main():
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"posts": {}}
    todo = targets(data)
    print(f"확인할 글 {len(todo)}개")
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        naver = [t for t in batch if "blog.naver.com" in t["url"]]
        blog = urlparse(naver[0]["url"]).path.strip("/").split("/")[0] if naver else None
        args = {"keywords": sorted({t["keyword"] for t in batch})}
        if blog:
            args["blog"] = blog
        try:
            res = mcp("check_naver_visibility", args)
        except Exception as e:  # noqa: BLE001
            print("순위 확인 실패:", e)
            data["last_error"] = str(e)[:300]
            break
        if res.get("partial") and res.get("pending"):
            print("확장이 아직 읽는 중인 검색어:", res["pending"])
        by_kw = {r["keyword"]: r for r in res.get("results") or []}
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
