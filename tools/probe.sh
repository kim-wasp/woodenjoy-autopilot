#!/bin/bash
# 점검용 — 사용량 장부 시험 (아주 짧은 호출 1번)
cd engine && python3 - <<'PY'
import llm, usage
usage.SITE = "woodenjoy"
def card_review():
    return llm.ask_json("JSON만", '{"ok":true} 를 그대로 출력', model="claude-haiku-5-5", max_tokens=20)
print(card_review())
print("장부:", usage.ENTRIES)
PY
