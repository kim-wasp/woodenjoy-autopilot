"""forsmartlife 애드센스 대비 사이트 정리. 기본은 미리보기, --apply 로 반영. 원문은 status/audit/pages-raw.json 에 백업돼 있어요."""
import base64, json, os, sys
import requests
APPLY = "--apply" in sys.argv
B = "https://forsmartlife.com/wp-json"
S = requests.Session()
S.headers.update({"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"})
log = []
def post(path, body, what):
    log.append(what)
    print(("반영 " if APPLY else "미리보기 ") + what)
    if APPLY:
        r = S.post(B + path, json=body, timeout=90)
        print("   ", r.status_code, r.text[:150] if r.status_code >= 300 else "")
def page(i):
    return S.get(f"{B}/wp/v2/pages/{i}", params={"context": "edit"}, timeout=60).json()["content"]["raw"]
def rep(raw, pairs, name):
    for a, b in pairs:
        if a not in raw:
            print(f"  !! {name}: 못 찾음 → {a[:60]}"); continue
        raw = raw.replace(a, b, 1)
    return raw
P = lambda t: f"<!-- wp:paragraph -->\n<p>{t}</p>\n<!-- /wp:paragraph -->"
HR = '<!-- wp:separator -->\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n<!-- /wp:separator -->'
HOW = ("글은 운영자가 주제를 정하고, 자료 조사와 초안 작성에는 AI 도구를 함께 씁니다. 숫자, 기준, 권고 내용은 질병관리청, 국가건강정보포털, 식품의약품안전처 같은 공식 자료와 대조해 확인하고, "
       "운영자가 읽고 승인한 글만 'WellnessNote 편집팀' 이름으로 게시합니다. 개인 경험담이나 확인되지 않은 후기는 쓰지 않고, 글마다 참고 자료와 작성 날짜를 적습니다.")

# 1) 소개: 운영자 소개는 그대로, 글과 어긋나는 '직접 실천해 검증' 문장만 고치고 작성 방식 추가
raw = page(18)
raw = rep(raw, [
    ("<p>16년간 두 아이를 키우면서 직접 겪고, 직접 확인하고, 직접 실천해본 것들을 정리하고 싶었습니다. 그게 WellnessNote의 시작이에요.</p>",
     "<p>16년간 두 아이를 키우며 생긴 궁금증을, 믿을 수 있는 공식 자료로 확인해 한곳에 정리하고 싶었습니다. 그게 WellnessNote의 시작이에요.</p>"),
    ("직접 실천해보고, 근거를 확인한 내용만 씁니다.", "공식 자료로 근거를 확인한 내용만 씁니다."),
    ("<p><strong>WellNote</strong> 두 딸을 키우며 직장 생활을 병행하는 워킹맘입니다. 아이들의 건강 문제를 계기로 공부를 시작해 16년간 직접 겪고 검증한 생활 건강 정보를 씁니다. 질병관리청·식품의약품안전처 등 공식 출처를 기반으로, 실천 가능한 건강 루틴을 전달합니다.</p>",
     "<p><strong>WellnessNote 운영자</strong>는 두 딸을 키우며 직장 생활을 병행하는 워킹맘입니다. 아이들의 건강 문제를 계기로 건강 정보를 공부하기 시작했고, 질병관리청·식품의약품안전처 등 공식 출처를 확인해 일상에서 실천할 수 있는 건강 정보를 정리합니다.</p>"),
    ("<p><strong>📌 건강 정보 이용 안내</strong></p>",
     "<p><strong>📌 글은 이렇게 만듭니다</strong></p>\n<!-- /wp:paragraph -->\n\n" + P(HOW) + "\n\n" + HR + "\n\n<!-- wp:paragraph -->\n<p><strong>📌 건강 정보 이용 안내</strong></p>"),
], "소개")
post("/wp/v2/pages/18", {"content": raw}, "소개 페이지: 직접 검증 문장 고치기, 작성 방식 추가, 운영자 이름 오타(WellNote) 고치기")

# 2) 편집 원칙: 날짜, 작성 과정(AI 활용·검토), 경험담 원칙
raw = page(807)
raw = rep(raw, [("<p>최종 업데이트: 2026년 5월</p>", "<p>최종 업데이트: 2026년 11월</p>")], "편집 원칙")
raw = raw.rstrip() + "\n\n" + HR + "\n\n" + '<!-- wp:heading {"level":3} -->\n<h3 class="wp-block-heading"><strong>6. 작성 과정과 AI 활용</strong></h3>\n<!-- /wp:heading -->\n\n' + P(HOW) + "\n\n" + \
      P("모든 글에는 병원 진료가 필요한 경우(위험 신호)를 따로 적고, 참고한 자료의 링크를 글 끝에 남깁니다. 링크가 열리지 않거나 내용이 바뀐 자료는 확인 후 고칩니다.")
post("/wp/v2/pages/807", {"content": raw}, "편집 원칙: 6. 작성 과정과 AI 활용 추가, 업데이트 날짜 11월")

# 3) 개인정보처리방침: 쓰지 않는 Akismet 빼기, 수정일
raw = page(3)
raw = rep(raw, [
    ('<!-- wp:list-item -->\n<li><strong>Akismet:</strong> 스팸 댓글 방지 (<a href="https://automattic.com/privacy/">정책 보기</a>)</li>\n<!-- /wp:list-item -->', ""),
    ("최종 수정일: 2026년 4월 21일", "최종 수정일: 2026년 11월 12일"),
], "개인정보처리방침")
raw = raw.replace("<!-- /wp:list-item -->\n\n</ul>", "<!-- /wp:list-item --></ul>")
post("/wp/v2/pages/3", {"content": raw}, "개인정보처리방침: 설치되지 않은 Akismet 항목 빼기, 최종 수정일")

# 4) 홈: 글 목록 위에 사이트 소개 한 단락 (애드센스 심사자가 첫 화면에서 사이트 목적을 알 수 있게)
raw = page(717)
if "home-intro" not in raw:
    intro = ('<!-- wp:group {"className":"home-intro"} -->\n<div class="wp-block-group home-intro">'
             '<!-- wp:heading {"level":1} -->\n<h1 class="wp-block-heading">공식 자료로 확인한 생활 건강 정보</h1>\n<!-- /wp:heading -->\n\n'
             + P("WellnessNote는 계절마다 달라지는 건강 문제, 매일의 건강 습관, 자주 겪는 증상을 질병관리청·국가건강정보포털 같은 공식 자료로 확인해 짧고 알아보기 쉽게 정리하는 블로그입니다. 글마다 참고 자료와 병원에 가야 하는 경우를 함께 적습니다.") + "\n\n"
             + P('<a href="/category/season-health-tips/">계절 건강</a> / <a href="/category/health-routine/">건강 루틴</a> / <a href="/category/symptom-management/">증상 관리</a> / <a href="/editorial-policy/">편집 원칙</a> / <a href="/about/">소개</a>')
             + "</div>\n<!-- /wp:group -->\n\n")
    post("/wp/v2/pages/717", {"content": intro + raw}, "홈: 글 목록 위에 사이트 소개(H1, 한 단락, 카테고리 링크) 추가")

# 5) 홈 검색 설명: 지금 '{{post_date}}'로 잘못 나와요
post("/rankmath/v1/updateMeta", {"objectType": "post", "objectID": 717, "meta": {
    "rank_math_title": "WellnessNote | 공식 자료로 확인한 생활 건강 정보",
    "rank_math_description": "계절 건강, 건강 루틴, 증상 관리 정보를 질병관리청·국가건강정보포털 등 공식 자료로 확인해 짧고 쉽게 정리합니다. 병원에 가야 하는 경우도 함께 안내해요."}},
    "홈 검색 제목/설명 고치기 (지금 설명이 '{{post_date}}'로 나와요)")

# 6) 사이트 한 줄 소개(태그라인)
post("/wp/v2/settings", {"description": "공식 자료로 확인한 생활 건강 정보"}, "사이트 태그라인 넣기 (지금 비어 있음)")

# 7) 카테고리 설명
for cid, desc in [(1, "독감, 한파, 미세먼지, 폭염, 식중독처럼 계절과 시기에 따라 늘어나는 건강 문제와 대비법을 공식 자료로 정리합니다."),
                  (3, "수면, 식사, 운동, 영양처럼 매일 하는 건강 습관을 근거와 함께 실천하기 쉽게 정리합니다."),
                  (4, "두통, 소화불량, 불면, 근육통처럼 자주 겪는 증상을 확인하는 법과 병원에 가야 하는 신호를 정리합니다.")]:
    post(f"/wp/v2/categories/{cid}", {"description": desc}, f"카테고리 {cid} 설명 넣기")

# 8) 작성자 소개(글 아래 작성자 상자)
post("/wp/v2/users/me", {"description": "WellnessNote 편집팀은 운영자가 주제를 정하고 공식 자료로 확인해 승인한 글을 게시합니다. 질병관리청·국가건강정보포털·식품의약품안전처 자료를 우선하며, 개인 경험담이나 확인되지 않은 후기는 쓰지 않습니다. 진단·처방을 대신하지 않습니다."},
     "작성자 소개 바꾸기 ('16년간 직접 검증' 문장 → 편집팀 작성 방식)")

# 9) 구글 색인 API 플러그인 끄기 (이미 자동화는 껐고, 플러그인도 비활성)
post("/wp/v2/plugins/fast-indexing-api/instant-indexing", {"status": "inactive"}, "Instant Indexing 플러그인 비활성화")

json.dump({"apply": APPLY, "log": log}, open(f"status/audit/adsense-fix-{'apply' if APPLY else 'dry'}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
