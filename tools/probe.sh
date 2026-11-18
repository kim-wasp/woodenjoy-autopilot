#!/bin/bash
# 점검용 (필요할 때 바꿔 써요) — 쿠팡 API 키 확인: 검색 1회, 개수만 출력
cd engine && python3 - <<'PY'
import coupang
print("키 있음:", coupang.ready())
r = coupang.search("목공용 본드", 5)
print("검색 결과 개수:", len(r))
p = coupang.pick(r)
print("링크 형식:", (p or {}).get("productUrl", "")[:28], "/ 로켓:", bool((p or {}).get("isRocket")))
PY
