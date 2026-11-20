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


def pick(products, keyword=""):
    """검색어 낱말이 상품명에 많이 들어간 것 → 로켓배송 → 검색 순위 순. 세트·묶음은 단품 검색이면 뒤로"""
    good = [p for p in products if p.get("productUrl") and p.get("productName")]
    if not good:
        return None
    words = [w for w in (keyword or "").split() if len(w) > 1]
    bundle = not any(w in keyword for w in ("세트", "묶음"))

    def score(ip):
        i, p = ip
        name = p["productName"].replace(" ", "")
        hit = sum(w in name for w in words)
        extra = bundle and any(w in name for w in ("세트", "본품+", "+보강판", "묶음"))
        return (-hit, extra, not p.get("isRocket"), i)
    return sorted(enumerate(good), key=score)[0][1]


def fill(items, today):
    """url 빈 '링크 필요' 상품을 검색해서 채워요. 바뀐 개수를 돌려줘요"""
    n = 0
    for it in items:
        if it.get("url") or not (it.get("search") or it.get("name")):
            continue
        if not ready() or _calls >= MAX_CALLS:
            break
        kw = it.get("search") or it["name"]
        p = pick(search(kw), kw)
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
