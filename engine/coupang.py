"""쿠팡 파트너스 Open API: 상품 검색 → 파트너스 링크 자동 채우기

키는 깃허브 Secrets(COUPANG_ACCESS_KEY, COUPANG_SECRET_KEY)에만 둬요. 화면·로그에 찍지 않아요.
호출 제한이 빡빡해서(시간당 초과 시 정지) 한 번 실행에 최대 MAX_CALLS 번만 불러요.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

HOST = "https://api-gateway.coupang.com"
BASE = "/v2/providers/affiliate_open_api/apis/openapi/v1"
MAX_CALLS = 5
_calls = 0


def ready():
    return bool(os.environ.get("COUPANG_ACCESS_KEY") and os.environ.get("COUPANG_SECRET_KEY"))


def _auth(method, path_query):
    path, _, query = path_query.partition("?")
    dt = time.strftime("%y%m%dT%H%M%SZ", time.gmtime())
    msg = dt + method + path + query
    sig = hmac.new(os.environ["COUPANG_SECRET_KEY"].encode(), msg.encode(), hashlib.sha256).hexdigest()
    return (f"CEA algorithm=HmacSHA256, access-key={os.environ['COUPANG_ACCESS_KEY']}, "
            f"signed-date={dt}, signature={sig}")


def _call(method, path_query, body=None):
    global _calls
    if not ready() or _calls >= MAX_CALLS:
        return None
    _calls += 1
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(HOST + path_query, data=data, method=method, headers={
        "Authorization": _auth(method, path_query), "Content-Type": "application/json;charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            res = json.loads(r.read().decode())
    except Exception as e:  # 키·응답 내용은 찍지 않아요
        print(f"  쿠팡 API 실패: {type(e).__name__} {getattr(e, 'code', '')}")
        return None
    if str(res.get("rCode")) != "0":
        print(f"  쿠팡 API 응답 코드 {res.get('rCode')}: {str(res.get('rMessage'))[:80]}")
        return None
    return res.get("data")


def search(keyword, limit=10):
    q = urllib.parse.urlencode({"keyword": keyword, "limit": limit})
    d = _call("GET", f"{BASE}/products/search?{q}")
    return (d or {}).get("productData") or []


def deeplink(urls):
    d = _call("POST", f"{BASE}/deeplink", {"coupangUrls": list(urls)})
    return {x.get("originalUrl"): x.get("shortenUrl") for x in (d or [])}


def pick(products):
    """광고 상품 말고 로켓배송 우선, 그다음 검색 순위대로"""
    good = [p for p in products if p.get("productUrl") and p.get("productName")]
    rocket = [p for p in good if p.get("isRocket")]
    return (rocket or good or [None])[0]


def fill(items, today):
    """url 빈 '링크 필요' 상품을 검색해서 채워요. 바뀐 개수를 돌려줘요"""
    n = 0
    for it in items:
        if it.get("url") or not (it.get("search") or it.get("name")):
            continue
        if not ready() or _calls >= MAX_CALLS:
            break
        p = pick(search(it.get("search") or it["name"]))
        if not p:
            it["status"] = f"검색 결과 없음 ({today})"
            continue
        it.update({
            "url": p["productUrl"],
            "picked": p["productName"][:80],
            "price": p.get("productPrice"),
            "rocket": bool(p.get("isRocket")),
            "status": f"API 자동 ({today}) 확인 전",
        })
        n += 1
    return n
