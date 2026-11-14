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

import re
import requests
from PIL import Image, ImageDraw

from common import log, secret

IMAGES = {}  # 이번 실행에서 만든 사진 수 (모델별)

NO_TEXT = (" Looks like a real unretouched photo taken by an ordinary person (not a stock photo, not CGI), natural light, imperfect everyday details, no text, no letters, no logos, no watermarks, "
           "no people's faces in close-up; never blur or pixelate faces — instead show people from behind, from the side, or naturally out of focus in the background; realistic proportions.")


def _realism(im):
    """AI 사진 특유의 매끈함·완벽한 수평·균일한 선명도를 줄여요 (휴대폰으로 대충 찍은 사진 쪽으로).
    매번 값이 조금씩 달라서 같은 보정 자국이 반복되지 않아요."""
    import random
    from PIL import ImageFilter, ImageEnhance, ImageChops
    w, h = im.size
    # 1) 손으로 든 폰처럼 아주 살짝 기울이고 가장자리 잘라내기
    ang = random.uniform(0.4, 1.3) * random.choice((-1, 1))
    big = im.rotate(ang, resample=Image.BICUBIC, expand=False)
    m = int(max(w, h) * 0.025)
    im = big.crop((m, m, w - m, h - m)).resize((w, h), Image.LANCZOS)
    # 2) AI 특유의 과한 선명도·채도·대비 살짝 낮추기
    im = im.filter(ImageFilter.GaussianBlur(random.uniform(0.35, 0.6)))
    im = ImageEnhance.Color(im).enhance(random.uniform(0.88, 0.96))
    im = ImageEnhance.Contrast(im).enhance(random.uniform(0.92, 0.98))
    # 3) 폰 센서 노이즈 (밝기 + 약한 색 노이즈)
    lum = Image.effect_noise((w, h), random.uniform(14, 22)).convert("RGB")
    im = Image.blend(im, lum, random.uniform(0.03, 0.05))
    # 4) 렌즈 주변부가 살짝 어두운 비네팅
    vig = Image.radial_gradient("L").resize((w, h)).point(lambda v: 255 - int(v * random.uniform(0.18, 0.28)))
    im = ImageChops.multiply(im, Image.merge("RGB", (vig, vig, vig)))
    # 5) 화이트밸런스를 매번 조금 다르게 (실내 형광등/전구색 느낌)
    r, g, b = im.split()
    k = random.uniform(-7, 7)
    r = r.point(lambda v: max(0, min(255, int(v + k))))
    b = b.point(lambda v: max(0, min(255, int(v - k))))
    im = Image.merge("RGB", (r, g, b))
    # 6) 메신저·앱을 한 번 거친 것처럼 JPEG 한 번 더 압축
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=random.randint(80, 88))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _save(img_bytes, out, size, realism=False):
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
    im = im.resize((w, h), Image.LANCZOS)
    if realism:
        im = _realism(im)
    im.save(out, "JPEG", quality=86 if realism else 90)


def generate(prompt, out, cfg, size=(1200, 675)):
    provider = (cfg or {}).get("provider", "openai")
    if provider == "none":
        return None
    # 'AI 화보' 쪽으로 끌고 가는 말은 빼요
    prompt = re.sub(r"(?i)\b(stunning|beautiful|gorgeous|cinematic|epic|8k|4k|ultra[- ]?detailed|hyper[- ]?realistic|photorealistic|professional photo(graphy)?|award[- ]winning|masterpiece|dramatic lighting|bokeh)\b,?\s*", "", prompt)
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
        IMAGES[cfg.get("model", "gpt-image-1")] = IMAGES.get(cfg.get("model", "gpt-image-1"), 0) + 1
    elif provider == "gemini":
        # 구글은 이미지 모델 이름이 자주 바뀌어요 → 설정한 이름부터 차례로 시도
        models = [cfg.get("model")] if cfg.get("model", "").startswith("gemini") else []
        models += ["gemini-3-pro-image", "gemini-3.1-flash-image", "gemini-2.5-flash-image"]
        raw, err = None, ""
        for model in dict.fromkeys(models):
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              params={"key": secret("GEMINI_API_KEY")}, timeout=300,
                              json={"contents": [{"parts": [{"text": full}]}],
                                    "generationConfig": {"responseModalities": ["IMAGE"],
                                                         "imageConfig": {"aspectRatio": "1:1" if size[1] == size[0] else ("4:5" if size[1] > size[0] else "16:9")}}})
            if r.status_code == 404:
                err = f"{model} 없음"
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Gemini 이미지 오류 {r.status_code}: {r.text[:300]}")
            parts = r.json()["candidates"][0]["content"]["parts"]
            raw = base64.b64decode(next(p["inlineData"]["data"] for p in parts if "inlineData" in p))
            IMAGES[model] = IMAGES.get(model, 0) + 1
            break
        if raw is None:
            raise RuntimeError(f"Gemini 이미지 모델을 찾지 못했어요 ({err})")
    else:
        raise SystemExit(f"알 수 없는 이미지 제공자: {provider}")
    _save(raw, out, size, realism=bool((cfg or {}).get("realism")))
    log(f"  대표 이미지 생성 ({provider})")
    return out
