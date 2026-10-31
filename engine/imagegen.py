"""AI 사진형 대표 이미지 만들기.

사이트 설정 images.hero.provider:
  - "openai": OpenAI 이미지 API (비밀키 OPENAI_API_KEY, 모델 images.hero.model 기본 gpt-image-1)
  - "gemini": Google Gemini 이미지 (비밀키 GEMINI_API_KEY, 모델 기본 gemini-2.5-flash-image)
  - "none":   만들지 않음
시험: MOCK_IMAGE=1 이면 단색 견본 이미지를 만들어요.

원칙: 사진 안에 글자를 넣지 않아요(AI는 한글을 자주 틀려요). 글자는 카드에서 코드로 넣어요.
"""
import base64
import io
import os

import requests
from PIL import Image, ImageDraw

from common import log, secret

NO_TEXT = (" Photorealistic, natural light, no text, no letters, no logos, no watermarks, "
           "no people's faces in close-up, realistic proportions.")


def _save(img_bytes, out, size):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = size
    # 가운데를 기준으로 원하는 비율로 자르고 크기 맞추기
    r = w / h
    if im.width / im.height > r:
        nw = int(im.height * r)
        im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = int(im.width / r)
        im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
    im.resize((w, h), Image.LANCZOS).save(out, "JPEG", quality=90)


def generate(prompt, out, cfg, size=(1200, 675)):
    provider = (cfg or {}).get("provider", "openai")
    if provider == "none":
        return None
    full = prompt.strip() + NO_TEXT
    keyname = {"openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}.get(provider)
    if keyname and not os.environ.get("MOCK_IMAGE") and not secret(keyname, required=False):
        log(f"  이미지 키({keyname})가 아직 없어서 사진 없이 진행해요")
        return None
    if os.environ.get("MOCK_IMAGE"):
        im = Image.new("RGB", size, (216, 226, 222))
        d = ImageDraw.Draw(im)
        d.rectangle([40, 40, size[0] - 40, size[1] - 40], outline=(47, 107, 87), width=8)
        im.save(out, "JPEG", quality=85)
        log("  [시험 모드] 대표 이미지 견본")
        return out
    if provider == "openai":
        r = requests.post("https://api.openai.com/v1/images/generations", timeout=300,
                          headers={"Authorization": f"Bearer {secret('OPENAI_API_KEY')}"},
                          json={"model": cfg.get("model", "gpt-image-1"), "prompt": full,
                                "size": "1536x1024", "quality": cfg.get("quality", "high"), "n": 1})
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI 이미지 오류 {r.status_code}: {r.text[:300]}")
        d = r.json()["data"][0]
        raw = base64.b64decode(d["b64_json"]) if d.get("b64_json") else requests.get(d["url"], timeout=120).content
    elif provider == "gemini":
        model = cfg.get("model", "gemini-2.5-flash-image")
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                          params={"key": secret("GEMINI_API_KEY")}, timeout=300,
                          json={"contents": [{"parts": [{"text": full + " Aspect ratio 16:9."}]}],
                                "generationConfig": {"responseModalities": ["IMAGE"]}})
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini 이미지 오류 {r.status_code}: {r.text[:300]}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        raw = base64.b64decode(next(p["inlineData"]["data"] for p in parts if "inlineData" in p))
    else:
        raise SystemExit(f"알 수 없는 이미지 제공자: {provider}")
    _save(raw, out, size)
    log(f"  대표 이미지 생성 ({provider})")
    return out
