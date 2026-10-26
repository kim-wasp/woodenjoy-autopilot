"""네이버 검색광고 '키워드 도구'로 월간 검색량 조회 (네이버 공식 API).

  python3 tools/keywords.py                     # topics/seed_keywords.txt 전부 조회
  python3 tools/keywords.py 싱크대경첩 씽크경첩    # 지정한 것만 조회
  python3 tools/keywords.py --dry-run 싱크대경첩   # 키 없이 요청 모양만 확인
  python3 tools/keywords.py --show 싱크대경첩      # 저장된 결과 보기 (키 필요 없음)

필요한 환경변수 (GitHub Secrets 에만 넣어요):
  NAVER_AD_API_KEY      검색광고 '액세스라이선스'
  NAVER_AD_SECRET_KEY   검색광고 '비밀키'
  NAVER_AD_CUSTOMER_ID  검색광고 'CUSTOMER_ID'(숫자)
선택 (블로그 글 수 = 경쟁 정도 참고, 네이버 개발자센터 '검색' API):
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

결과: topics/keywords.json  (조회일과 함께 저장. 숫자를 지어내지 않기 위해 글에는 여기 있는 값만 써요)
주의
- 검색량은 '광고 시스템이 집계한 최근 한 달 조회수'예요. 10 미만은 "<10"으로 와요
- comp_ad(광고 경쟁도)는 광고 입찰 경쟁이에요. 블로그 순위 난이도로 쓰지 않아요
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "topics/keywords.json"
SEED = ROOT / "topics/seed_keywords.txt"
API = "https://api.searchad.naver.com"
KST = timezone(timedelta(hours=9))
BATCH = 5          # 한 번에 보낼 힌트 키워드 수 (공식 안내 최대 5개)
RELATED_KEEP = 15  # 힌트마다 저장할 연관 키워드 수


def signature(secret, ts, method, uri):
    msg = f"{ts}.{method}.{uri}".encode()
    return base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()


def to_int(v):
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).replace(",", "").strip()
    return 5 if s.startswith("<") else int(s or 0)   # "<10"은 5로 계산하되 원래 표시는 따로 저장


def ad_request(words, dry):
    uri = "/keywordstool"
    params = {"hintKeywords": ",".join(words), "showDetail": "1"}
    if dry:
        print(f"  [미리보기] GET {API}{uri} {params}")
        return [{"relKeyword": w, "monthlyPcQcCnt": 100, "monthlyMobileQcCnt": "< 10", "compIdx": "중간"} for w in words]
    import requests
    key, secret, cust = (os.environ.get(k, "") for k in ("NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY", "NAVER_AD_CUSTOMER_ID"))
    if not (key and secret and cust):
        raise SystemExit("검색광고 API 키가 없어요 (NAVER_AD_API_KEY, NAVER_AD_SECRET_KEY, NAVER_AD_CUSTOMER_ID)")
    for attempt in range(3):
        ts = str(int(time.time() * 1000))
        headers = {"X-Timestamp": ts, "X-API-KEY": key, "X-Customer": str(cust),
                   "X-Signature": signature(secret, ts, "GET", uri)}
        r = requests.get(API + uri, params=params, headers=headers, timeout=30)
        if r.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"키워드 도구 오류 {r.status_code}: {r.text[:300]}")
        return r.json().get("keywordList", [])
    raise RuntimeError("요청이 너무 많다고 해요(429). 잠시 뒤 다시 실행하세요")


def blog_total(word, dry):
    cid, sec = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if dry or not (cid and sec):
        return None
    import requests
    r = requests.get("https://openapi.naver.com/v1/search/blog.json", params={"query": word, "display": 1},
                     headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": sec}, timeout=20)
    return r.json().get("total") if r.ok else None


def row(item):
    pc, mo = item.get("monthlyPcQcCnt", 0), item.get("monthlyMobileQcCnt", 0)
    clean = lambda v: str(v).replace(" ", "").replace(",", "")
    return {"pc": clean(pc), "mobile": clean(mo), "total": to_int(pc) + to_int(mo),
            "comp_ad": item.get("compIdx", "")}


def load():
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"source": "네이버 검색광고 키워드 도구 (월간 조회수, PC+모바일)", "keywords": {}}


def norm(w):
    return w.replace(" ", "").strip()


def run(words, dry):
    data = load()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    words = list(dict.fromkeys(norm(w) for w in words if norm(w)))   # 공백 제거·중복 제거 (API는 공백을 받지 않아요)
    for i in range(0, len(words), BATCH):
        chunk = words[i:i + BATCH]
        items = ad_request(chunk, dry)
        by_kw = {norm(it["relKeyword"]): it for it in items}
        related = sorted((it for it in items if norm(it["relKeyword"]) not in chunk),
                         key=lambda it: -(to_int(it.get("monthlyPcQcCnt", 0)) + to_int(it.get("monthlyMobileQcCnt", 0))))
        for w in chunk:
            it = by_kw.get(w)
            entry = {**row(it), "checked": today} if it else {"total": None, "note": "결과 없음(검색량이 거의 없거나 광고 불가 키워드)", "checked": today}
            entry["related"] = [{"kw": r["relKeyword"], **row(r)} for r in related[:RELATED_KEEP]]
            bt = blog_total(w, dry)
            if bt is not None:
                entry["blog_docs"] = bt
            # 예전 조회 값은 history 에 남겨요 (글에 적은 숫자를 나중에도 대조할 수 있게)
            prev = data["keywords"].get(w) or {}
            hist = dict(prev.get("history") or {})
            if prev.get("checked") and prev.get("total") is not None:
                hist.setdefault(prev["checked"], prev["total"])
            if entry.get("total") is not None:
                hist[today] = entry["total"]
            if hist:
                entry["history"] = dict(sorted(hist.items()))
            data["keywords"][w] = entry
        if not dry:
            time.sleep(1)
    data["updated"] = today
    if dry:
        print(json.dumps({w: data["keywords"][w] for w in words}, ensure_ascii=False, indent=1)[:1500])
        print("미리보기 끝 (저장 안 함)")
        return
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    show(words)


def show(words):
    data = load()["keywords"]
    print(f"{'키워드':<16}{'월간 합계':>8}{'PC':>8}{'모바일':>8}  광고경쟁(참고)  블로그글수  조회일")
    for w in words:
        e = data.get(norm(w))
        if not e:
            print(f"{w:<16}  (조회 안 됨)")
            continue
        print(f"{w:<16}{str(e.get('total')):>8}{e.get('pc', ''):>8}{e.get('mobile', ''):>8}  {e.get('comp_ad', ''):<12}"
              f"{str(e.get('blog_docs', '-')):>10}  {e.get('checked')}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--show" in sys.argv:
        show(args)
        sys.exit()
    if not args:
        args = [l.strip() for l in SEED.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    run(args, "--dry-run" in sys.argv)
