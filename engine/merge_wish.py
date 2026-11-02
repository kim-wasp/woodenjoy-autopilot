"""글 만들기 중에 생긴 '링크 필요' 상품을 최신 main 의 쿠팡 링크 목록에 합쳐요 (사장님이 그 사이 넣은 링크는 그대로)"""
import json
import sys
from pathlib import Path

saved, target = Path(sys.argv[1]), Path(sys.argv[2])
if saved.exists():
    new = json.loads(saved.read_text(encoding="utf-8"))
    cur = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"items": []}
    keys = {i.get("key") for i in cur.get("items", [])}
    for it in new.get("items", []):
        if it.get("key") not in keys:
            cur.setdefault("items", []).append(it)
    target.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
