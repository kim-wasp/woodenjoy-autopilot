"""forsmartlife 애드센스 재신청 전 정리 (2026-11-17)

  python3 tools/fsl_fix.py            무엇을 바꿀지 보고만
  python3 tools/fsl_fix.py --apply    실제로 바꾸기

1) 과장 제목 정리(주소는 그대로)  2) 본문에 남은 ** 표시를 굵은 글씨로  3) AI 이미지 안내 한 줄
4) 출처 없는 글에 공식 자료 2~4개 (웹 검색으로 찾고 열리는 것만)  5) 문의 페이지 설명
"""
import base64
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
from common import secret  # noqa: E402

BASE = "https://forsmartlife.com/wp-json/wp/v2"
H = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{secret('WP_FORSMARTLIFE_PASS')}".encode()).decode()}
APPLY = "--apply" in sys.argv
AI_NOTE = '<p class="ai-image-note" style="font-size:13px;color:#777">※ 이 글의 사진은 이해를 돕기 위해 AI로 만든 이미지예요. 실제 인물·장소가 아니에요.</p>'

TITLES = {
    942: "토마토 효능 7가지, 생으로 먹을 때와 익혀 먹을 때 차이",
    931: "저속노화 식단 원칙 5가지, 매일 식탁에서 바꿀 것",
    921: "식후 식곤증과 혈당 스파이크, 당뇨 전단계라면 확인할 점",
    896: "수면 부채와 치매 위험, 잠자는 동안 뇌 노폐물이 빠지는 원리",
    891: "위고비 근손실 예방법, 체중 감량 중 근육 지키는 식사와 운동",
    886: "당뇨 초기증상 7가지와 혈당 검사를 받아야 할 때",
    801: "치매 예방을 위해 줄여야 할 생활 습관 3가지",
    796: "대체 감미료, 혈당과 장에 미치는 영향과 고르는 기준",
    791: "거북목 교정 10분 스트레칭 루틴, 굽은 등 펴는 순서",
    741: "허리 디스크와 단순 근육통 구별 포인트, 병원 가야 하는 신호",
    700: "근감소증 예방 단백질 식품 5가지, 4050 하루 섭취 기준",
    695: "봄철 우울감, 햇볕 쬐기로 생활 리듬 잡는 법",
    679: "항히스타민제 복용법, 내성 걱정과 졸음 줄이는 방법",
    657: "층간소음 없는 홈트레이닝 루틴, 매트 위에서 하는 운동",
    639: "비타민D 결핍, 햇볕만으로 충분할까? 보충제 기준",
    646: "무릎 부담 줄이는 등산화 고르는 법",
    627: "구내염이 자주 생길 때 확인할 비타민 결핍과 관리법",
    602: "혈당 스파이크 줄이는 식사 순서, 채소 먼저 먹는 방법",
    439: "황사 마스크 재사용, 어디까지 괜찮을까",
    421: "기초대사량 높이는 생활 습관, 봄철 체중 관리",
    382: "미세먼지 심한 날 환기 기준과 공기청정기 쓰는 법",
    370: "졸음 적은 알레르기 약 고르는 기준, 꽃가루 비염",
    365: "환절기 대상포진 초기 증상 5가지와 진료 시기",
    354: "춘곤증과 갑상선 질환 구별하는 법",
    283: "벚꽃 구경 뒤 눈이 따가울 때, 결막염 예방법",
    277: "봄철 자외선, 피부 노화 막는 관리 루틴",
    269: "꽃샘추위 체온 관리법, 면역력 지키는 생활 습관",
    134: "미세먼지 디톡스 루틴, 코 세척과 두피 세정법",
    93: "봄철 결막염 증상과 방치하면 안 되는 이유",
    85: "안구건조증, 눈 기름샘(마이봄샘) 관리 루틴",
    81: "환절기 불면증, 저녁 습관으로 수면 리듬 잡기",
}


def req(m, path, **kw):
    r = requests.request(m, BASE + path, headers=H, timeout=120, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code} {path} {r.text[:200]}")
    return r


def all_posts():
    out, page = [], 1
    while True:
        r = req("GET", f"/posts?status=publish&per_page=20&page={page}&context=edit&_fields=id,slug,title,content,link")
        out += r.json()
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            return out
        page += 1


def find_sources(title, text):
    import llm
    import sources
    x = llm.ask_json(
        "당신은 건강 정보 팩트체커예요. JSON만 답해요.",
        f"[글 제목] {title}\n[글 앞부분]\n{text[:3000]}\n\n"
        "이 글의 핵심 내용을 뒷받침하는 공식·신뢰 자료를 웹 검색으로 2~4개 찾아요. 우선순위: 질병관리청 국가건강정보포털(health.kdca.go.kr), 질병관리청, "
        "식품의약품안전처, 보건복지부, 국민건강보험공단, 서울대병원·서울아산병원·삼성서울병원 등 대학병원 건강정보, 대한OO학회, WHO. 블로그·쇼핑몰·광고성 기사 금지. "
        "글 내용과 실제로 관련된 페이지만(주제 일치). "
        'JSON: {"links": [{"title": "기관명, 자료 제목", "url": "https://..."}]}',
        model="claude-sonnet-5-5", web_search=True, max_searches=4, max_tokens=2000)
    return [l for l in (x.get("links") or []) if l.get("url") and sources.alive(l["url"])][:4]


def main():
    posts = all_posts()
    print(f"글 {len(posts)}개")
    n_t = n_b = n_ai = n_s = 0
    for p in posts:
        raw = p["content"]["raw"]
        new = raw
        upd = {}
        if p["id"] in TITLES and p["title"]["raw"] != TITLES[p["id"]]:
            upd["title"] = TITLES[p["id"]]
            n_t += 1
            print(f"제목 {p['id']}: {p['title']['raw']} → {TITLES[p['id']]}")
        new2 = re.sub(r"\*\*([^*\n<>]{1,80}?)\*\*", r"<strong>\1</strong>", new)
        if new2 != new:
            n_b += 1
            new = new2
        has_img = bool(re.search(r"<img\b", new))
        if has_img and "ai-image-note" not in new and "AI로 만든" not in new:
            new = new.rstrip() + "\n\n" + AI_NOTE
            n_ai += 1
        ext = [u for u in re.findall(r'href="(https?://[^"]+)"', new) if "forsmartlife.com" not in u and "coupang" not in u]
        if not ext:
            n_s += 1
            if APPLY:
                text = re.sub(r"<[^>]+>", " ", raw)
                links = find_sources(p["title"]["raw"], text)
                if links:
                    block = '<h2>참고 자료</h2>\n<ul>\n' + "\n".join(f'<li><a href="{l["url"]}" target="_blank" rel="noopener">{l["title"]}</a></li>' for l in links) + "\n</ul>\n<p style=\"font-size:13px;color:#777\">자료 확인: 2026년 11월</p>"
                    if AI_NOTE in new:
                        new = new.replace(AI_NOTE, block + "\n\n" + AI_NOTE)
                    else:
                        new = new.rstrip() + "\n\n" + block
                    print(f"출처 {p['id']} {p['slug']}: {len(links)}개")
                else:
                    print(f"출처 못 찾음 {p['id']} {p['slug']}")
            else:
                print(f"출처 없음 {p['id']} {p['slug']}")
        if new != raw:
            upd["content"] = new
        if upd and APPLY:
            req("POST", f"/posts/{p['id']}", json=upd)
    print(f"제목 {n_t} / 굵은글씨 표시 {n_b} / AI 안내 {n_ai} / 출처 없음 {n_s}")
    pages = req("GET", "/pages?per_page=50&context=edit&_fields=id,slug,content").json()
    c = next((x for x in pages if x["slug"] == "contact"), None)
    if c:
        print("문의 페이지:\n" + c["content"]["raw"][:1500])


if __name__ == "__main__":
    main()
