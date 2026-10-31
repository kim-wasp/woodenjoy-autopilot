"""Claude API 로 글을 써요 (공식 Messages API).

- 비밀키: ANTHROPIC_API_KEY
- 모델: 사이트 설정 llm.model (기본 claude-opus-5-5, 글 품질 우선)
- 웹 검색: llm.web_search 가 true 면 Claude 의 웹 검색 도구로 최신 자료를 먼저 찾아요
- 시험: MOCK_LLM=1 이면 API 를 부르지 않고 engine/mock/ 의 예시 답을 돌려줘요
"""
import json
import os
import re
import time
from pathlib import Path

import requests

from common import ROOT, log, secret

API = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-opus-5-5"


def _extract_json(text):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    return json.loads(raw)


def ask_json(system, prompt, model=None, web_search=False, max_tokens=16000, mock_name=None):
    """프롬프트를 보내고 JSON 한 덩어리를 돌려받아요."""
    if os.environ.get("MOCK_LLM"):
        f = ROOT / "engine/mock" / f"{mock_name or 'post'}.json"
        log(f"  [시험 모드] {f.name} 사용")
        return json.loads(f.read_text(encoding="utf-8"))
    body = {
        "model": model or DEFAULT_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }
    if web_search:
        body["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    headers = {"x-api-key": secret("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
               "content-type": "application/json"}
    for attempt in range(4):
        r = requests.post(API, json=body, headers=headers, timeout=600)
        if r.status_code in (429, 500, 502, 503, 529):
            time.sleep(15 * (attempt + 1))
            continue
        if r.status_code == 400 and web_search and "web_search" in r.text:
            log("  웹 검색 도구를 쓸 수 없어서 검색 없이 진행해요")
            body.pop("tools", None)
            web_search = False
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"Claude API 오류 {r.status_code}: {r.text[:500]}")
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        try:
            return _extract_json(text)
        except (ValueError, json.JSONDecodeError):
            body["messages"] += [{"role": "assistant", "content": text},
                                 {"role": "user", "content": "형식이 잘못됐어요. 설명 없이 JSON 한 덩어리만 다시 주세요."}]
    raise RuntimeError("Claude API 가 계속 바빠요. 잠시 뒤 다시 실행하세요")
