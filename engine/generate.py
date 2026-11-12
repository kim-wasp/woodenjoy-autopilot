"""글 한 편 만들기: 제목(검색 기반) → 블로그 글 → 사진·카드 → 인스타·스레드 → 점검 → AI 티 다듬기.

사용:
  python3 engine/generate.py <사이트id> [--topic "주제나 제목"] [--notes "고칠 점"] [--out 폴더]
  python3 engine/generate.py <사이트id> --ideas        # 글감 10개 추천 → sites/<id>/ideas.json
결과: content/<사이트id>/<날짜>-<슬러그>/ 에 post.json, article.md, article.html, hero.jpg, photo*.jpg, cards/*.jpg

사이트 설정에서 고르는 것
- 기본 채널 blog.platform: naver | wordpress | none(커먼센스처럼 앱·사이트로 보내는 SNS 전용)
- SNS: instagram.enabled / threads.enabled (기본 채널에 더해 선택)
- 수익화 monetization: stage(pre_adsense|adsense|adpost), coupang, internal_links, humanize
- 이미지 images: hero(대표 사진), blog_inline(cards|photos|mixed|none), photo_style, instagram(cards|photo_cards)
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skills  # noqa: E402
from common import CONTENT, ROOT, SITES, load_json, load_site, log, now_kst, post_dirs, save_json, slugify  # noqa: E402
import checks  # noqa: E402
import imagegen  # noqa: E402
import llm  # noqa: E402
import mdhtml  # noqa: E402

SYSTEM = """당신은 한국어 블로그·SNS 콘텐츠로 수익을 내는 편집장입니다. 목표는 검색 유입·클릭·체류시간, 그리고 '거짓말 안 하는 곳'이라는 신뢰입니다.

반드시 지킬 것
1. 사실만 씁니다. 숫자·규격·제도·가격·통계는 웹 검색으로 확인한 것만 쓰고, 확인한 출처를 sources 에 남깁니다. 확인 못 한 내용은 빼세요.
2. 후킹은 강하게, 내용은 사실로. 첫 줄·카드 표지·제목은 손해 회피("모르고 하면 손해"), 흔한 실수 지적, 반전, 본문 근거가 있는 구체적 숫자로 강하게 씁니다. 근거 없는 '100%·무조건·누구나·최고'는 쓰지 않습니다. 제목이 약속한 답은 본문에 반드시 있어야 합니다.
3. 사람들이 실제로 쓰는 말을 씁니다(쇼핑몰 상품명·포털 검색어에서 쓰는 소비자 용어). 업계 용어는 괄호로 한 번만.
4. 경험담·후기·사연을 지어내지 않습니다. 운영자의 경험은 [운영자 경험] 에 있는 것만 씁니다.
5. AI 티를 내지 않습니다: "~를 통해·~에 있어서·~에 의해" 같은 번역투, "결론적으로·시사하는 바가 크다·다음과 같다·~할 때입니다" 같은 관용구, 같은 대구의 반복, 연결어미 뒤 쉼표("~고,"), 같은 끝맺음 4번 이상 연속을 피하세요. 문장 길이를 섞으세요.
6. 의학·법률·금융 정보는 단정하지 말고 전문가 상담이 필요한 경계를 분명히 씁니다. 정치 글은 한쪽을 편들지 않고 사실과 각 입장의 근거를 나란히 씁니다.
7. 광고 클릭을 유도하는 문구("광고 눌러 주세요" 등)는 절대 쓰지 않습니다. 제휴 링크는 독자에게 실제로 필요한 자리에만, 대가성 문구와 함께.
8. 출력은 설명 없이 JSON 한 덩어리입니다."""

STAGE_GUIDE = {
    "pre_adsense": "[수익화 단계: 애드센스 승인 전]\n- 승인 기준(독창성·충분한 정보·신뢰)이 최우선. 다른 글을 짜깁기한 듯한 일반론 금지, 이 글만의 판단 기준·비교표·체크리스트를 넣으세요.\n"
                   "- 작성 기준과 확인 날짜를 본문 끝에 한 줄로(예: '2026년 11월 기준, 공식 자료 확인'). 제휴 링크는 넣지 마세요.\n- 소제목마다 충분한 문단(얇은 단락 나열 금지).",
    "adsense": "[수익화 단계: 애드센스 운영 중]\n- 검색 클릭률(CTR)이 높은 제목, 첫 화면에서 답을 주되 더 읽을 이유(비교표·FAQ·체크리스트)를 남겨 체류시간을 늘리세요.\n"
               "- 소제목 5~7개, 각 소제목 아래 2~4문단(광고가 자연스럽게 들어갈 자리). 관련 글 내부 링크 2~3개.",
    "adpost": "[수익화 단계: 네이버 애드포스트]\n- 첫 3줄 훅, 결론 먼저, 질문형 소제목, 표와 이미지가 많은 글(모바일에서 끝까지 스크롤하게). 체류시간과 공감·저장을 노리세요.",
}

THREADS_GUIDE = """스레드 규칙 (사장님 지시):
- 말투: 친구한테 말하듯 친근한 반말. 본문·댓글·대댓글 모든 문장을 반말로 끝내요(~야, ~지?, ~거든, ~더라, ~해, ~임).
  '~요', '~습니다', '~세요' 로 끝나는 문장 금지. 예) "축의금 5만원 내면 욕먹을까?" "이거 나만 몰랐어?" "생각보다 많더라"
- 짧게. 후킹이 가장 중요.
- posts[0] 본문: 2~5줄, 200자 이내. 첫 줄에서 바로 멈추게(반전·도발 질문·"이거 나만 그래?"). 재미있는 에피소드나 상황 한 장면으로 시작해요.
  에피소드는 사실만: 기사·커뮤니티에서 실제 화제가 된 사연, 또는 "~하면 어떡할래?" 같은 가정 상황. 내가 겪은 척 지어낸 경험담 금지(운영자 경험 목록에 있는 것만 가능).
  본문에는 링크·해시태그·숫자 나열·정보 정리 금지. 이미지 없이 글만 올라가요.
  첫 줄은 15자 안팎 한 줄. 아래 패턴 중 이 글에 가장 센 것으로, 반드시 구체적 사실·숫자·물건·장면으로 채워요:
  반전(다들 믿는 상식 뒤집기) / 실수 장면(흔히 하는 실수) / 숫자(돈·시간·개수) / 장면(바로 그려지는 상황) / 진짜 궁금한 질문 / 둘 중 뭐가 나은지 비교.
  먼저 첫 줄 후보 3개를 서로 다른 패턴으로 만들어 hooks 에 넣고, 그중 가장 센 것을 본문 첫 줄로 써요.
  에피소드 2~4줄에는 숫자나 구체적인 물건 하나를 꼭 넣어요. 마지막 줄은 정보가 댓글에 있다는 걸 자연스럽게 알려요(매번 같은 문장 말고).
  줄바꿈은 숨 쉴 자리에서만. 한 문장 한 줄씩 끝까지 늘어놓지 말아요.
- posts[1] 댓글(본문에 다는 첫 댓글): 반말, 바로 써먹을 핵심 정보 2~4줄. 순서가 있으면 번호. 수치·규격·방법은 확인된 사실만.
- posts[2] 대댓글: 반말 1~2줄 + {LINK} (더 자세한 건 여기).
- topic_tag: 주제 태그 1개(# 없이, 20자 이내, 마침표·& 금지). 사람들이 실제로 찾는 넓은 주제(예: 셀프인테리어, 목공, 생활꿀팁). 매번 새로 지어낸 긴 태그 금지.
- 반응 낚시 금지: "동의하면 댓글", "공감하면 좋아요", "동의?", "다들 어때?" 같은 말(메타가 걸러내요). 끝은 사람들이 진짜 한마디 하고 싶어지는 구체적 질문이나 핵심 한 줄로.
- AI 티 금지: "X가 아니라 Y야" 식 대구 뒤집기, "~도 없고 ~도 없고" 부정 나열, "결과는? ~" "핵심은: ~" 같은 혼자 묻고 답하기,
  "이제 걱정 끝!" "꿀팁 대방출" 같은 상투어, 결산하는 마무리 문장, 대시(—, –), 줄마다 이모지, 근거 없는 감정 연출("솔직히 말할게, 진짜 무서웠어").
  이모지는 쓰더라도 1~2개, 가족·피부색 조합 이모지 금지.
"""

CARD_GUIDE = """카드(인스타 캐러셀, 1080x1350) 규칙:
- slides 6~8장. 1장째는 표지(가장 강한 후킹, "big": true), 마지막 장은 저장·유입 안내.
- 장마다 새 정보 하나. 같은 문장 반복 금지.
- 한 장에 들어가는 양이 정해져 있어요: 제목 3줄이면 sub 1줄 + 항목 2개까지, 제목 2줄이면 sub 2줄 + 항목 3개까지. 넘치면 계정명 자리를 침범해 점검에서 떨어져요.
- title: 2~3줄(\\n), 한 줄 10자 이내, 강조할 말은 *별표*로. sub: 1~2줄, 한 줄 18자 이내. badge(선택): 16자 이내.
- body 종류(다른 종류를 섞어 쓰세요):
  {"kind":"steps","items":[{"d":"한 줄 14자 이내","s":"보충 20자 이내(선택)"}] 2~4개,"tip":"선택, 40자 이내"}
  {"kind":"chips","label":"예시 설명","example":["표기1","표기2","표기3"],"legend":[["표기1","뜻 16자 이내"],...]}  (3~4개)
  {"kind":"grid","items":[{"label":"8자 이내"}] 4개}
  {"kind":"image","src":"hero.jpg","height":560}  ← 대표 사진을 카드 안에 넣을 때(표지에만)
- 같은 body 종류는 최대 2번, 연달아 쓰지 마세요(비슷한 장은 점검에서 떨어져요). image 를 쓰는 표지는 title 2줄.
- 숫자·단계·비교처럼 정확해야 하는 정보는 카드 글자로 씁니다.
- 숫자만 덩그러니 두지 마세요. 무엇의 수치인지 같은 칸에 적어요(✕ "2023년 2.95%" → ○ "100만원 이상 송금 2.95%→3.17%").
- 표지·마지막 장 제목은 읽다 멈추게: 반전(평균은 A인데 1위는 B), 손해·오해 지적(이거 모르면 ○○), 질문형 도발. 단, 사실 그대로.
- 구성(instagram-kr 스킬): 내용에 맞는 하나를 골라 instagram.framework 에 적어요.
  모음형(목록: 표지에 정확한 개수와 얻는 것, 한 장에 하나) / 실수 바로잡기형(표지 반전 → 왜 틀렸는지 → 방법마다 이름 붙여 ✕/○ 한 장씩 → 한 줄 정리) /
  순서형(표지에 완성 결과 → 문제 → 전체 단계 수·시간 먼저 → 단계마다 한 장 → 결과) / 비교형(표지 질문 → 기준마다 한 장 → '이런 집은 A, 이런 집은 B' 결론) /
  논쟁형(사회 통념: 표지 논쟁 질문 → 양쪽 입장 → 확인된 데이터 → 투표 안내, 한쪽 조롱 금지).
- 표지는 혼자서도 피드에서 멈추게, 표지만 보고 주제가 보이게. 답은 안에 있다는 열린 고리를 남겨 넘기게 해요.
  표지 후보 3개를 서로 다른 패턴(반전/실수/숫자/장면/질문/비교)으로 instagram.cover_hooks 에 넣고 가장 센 것을 표지 title 로 써요.
- 크기는 1080x1350(4:5, Meta 게시 API가 받는 가장 긴 세로). 프로필 그리드는 표지를 3:4로 좌우 조금 잘라 보여주니 표지 핵심 글자는 가운데에.
- 표지에 개수를 약속했으면 안쪽 장에서 정확히 그 개수만큼 채워요(부풀리려고 빈 장 넣기 금지).
- 마지막 장은 행동 하나만: 저장(쓸 때 꺼내보기) 또는 보내기(이 고민 있는 친구에게) 또는 프로필 링크. 셋을 한꺼번에 요구하지 않아요."""

PHOTO_CARD_GUIDE = """[인스타 사진 카드 모드] 카드 중 2~4장은 사진 배경 카드로 만드세요: {"title":"…","sub":"…","photo":"photo1.jpg"} (body 없이, 흰 글자가 사진 위에 올라가요).
표지는 반드시 사진 배경 카드(photo1.jpg). 사진 파일 이름은 photo_prompts 의 번호와 맞추세요(photo1.jpg = id 1)."""


# ---------- 재료 ----------
def blog_kind(site):
    return (site.get("blog") or {}).get("platform", "none")


def img_cfg(site):
    i = site.get("images") or {}
    return {
        "hero": i.get("hero", {"provider": "openai"}),
        "blog_inline": i.get("blog_inline", "cards"),          # cards | photos | mixed | none
        "photo_style": i.get("photo_style", ""),
        "instagram": i.get("instagram", "cards"),              # cards | photo_cards
        "photos": int(i.get("photos", 3)),
    }


def needs_cards(site):
    """카드뉴스가 필요한지: 인스타를 켜거나 블로그 본문에 카드를 넣을 때만"""
    ic = img_cfg(site)
    return bool(site.get("instagram", {}).get("enabled")) or (blog_kind(site) != "none" and ic["blog_inline"] in ("cards", "mixed"))


def schema(site):
    blog = blog_kind(site) != "none"
    ic = img_cfg(site)
    need_photos = (blog and ic["blog_inline"] in ("photos", "mixed")) or ic["instagram"] == "photo_cards"
    parts = ['"title": "제목 (핵심 키워드를 앞쪽에, 45자 이내)"',
             '"slug": "영문-소문자-하이픈"',
             '"keywords": {"main": "핵심 키워드", "sub": ["연관 키워드"...]}',
             '"brief": {"reader": "누가 어떤 상황에서", "question": "답할 질문 1개", "answer": "핵심 답 한 문장", "out_of_scope": "다루지 않을 것", "next_action": "읽고 할 행동"}',
             '"why_this_topic": "이 주제를 고른 근거 (검색량·시기·검색 결과)"']
    if blog:
        r = site.get("rules", {})
        inline = {"cards": "소제목 아래 적절한 곳에 [[card:번호]] 2~3개(카드 번호는 slides 순서)",
                  "photos": "소제목 아래 적절한 곳에 [[photo:번호]] 2~3개(photo_prompts 번호)",
                  "mixed": "[[card:번호]] 1~2개와 [[photo:번호]] 1~2개를 섞어서",
                  "none": "본문 이미지는 [[hero]] 하나만"}[ic["blog_inline"]]
        cats = ((site.get("blog") or {}).get("app") or {}).get("categories") or ((site.get("blog") or {}).get("static") or {}).get("categories") or (site.get("blog") or {}).get("categories")
        if cats:
            parts.append(f'"category": "글 분류 — 다음 중 하나만: {" / ".join(cats)}"')
        if blog_kind(site) == "static":
            parts += ['"meta_description": "검색 결과 설명 80~150자"',
                      '"article_md": "짧고 쉬운 글 마크다운. 구조: ## 소제목(질문형, 아주 짧게) 3~4개, 각 2~4문장(쉬운 말, 중학생도 알게, 문장 짧게) → '
                      '(편집자 견해가 주어졌을 때만) ## 편집자 생각 → ## 더 자세히. 더 자세히는 서술형 문단 없이 자료 나열식으로 1,000~1,600자: 표 1~2개(숫자 비교·쟁점 비교), ### 작은 제목 아래 짧은 항목 목록(핵심 사실, 쟁점별 양쪽 근거, 관련 법·제도, 일정, 용어 풀이 중 이슈에 맞는 것), 항목마다 한 줄. '
                      '## 더 자세히 위쪽(핵심) 합계 600~1000자. 첫 소제목 앞 도입 문단 없이 바로 시작. 대표 사진은 프로그램이 넣으니 [[hero]] 쓰지 말 것. 참고 자료 목록은 쓰지 말고 sources 에만"']
        else:
            parts += ['"meta_description": "검색 결과 설명 80~150자"',
                  f'"article_md": "짧고 알아보기 쉬운 글 마크다운 {r.get("min_chars", 1500)}~{r.get("max_chars", 3000)}자. 서술형 긴 문단 금지, 문장은 짧게, 쉬운 말. 구조: '
                  '첫 줄 > 한 줄 결론(바쁜 사람은 여기까지만 읽어도 되게, 1~2문장) → [[hero]] → ## 질문형 소제목 3~5개, 각 2~4문장 또는 항목 나열 → '
                  '## 한눈에 정리 (표 또는 체크리스트로 자료 나열, 서술 금지) → ## 자주 묻는 질문 (Q 2~3개, 답은 1~2문장) → 마지막에 ## 참고 자료 (출처 링크 목록). '
                  f'추가 이미지 자리: {inline}"']
    if need_photos:
        parts.append(f'"photo_prompts": [{{"id": 1, "prompt": "사진 묘사(영어). {ic["photo_style"] or "주제에 맞는 현실적인 장면"}", "alt": "한국어 대체 텍스트"}}] 최대 {ic["photos"]}개')
    if ic["hero"].get("thumb_text"):
        parts += ['"hero_prompt": "대표 사진 묘사(영어). 홈피드 썸네일용: 이 글이 해결하는 문제 장면(고장·틈·실수 등 before 상태)을 한국 아파트 실내에서 '
                  '휴대폰으로 대충 찍은 듯한 현실적인 장면 하나. 물건 1~2개에 초점, 화면 가운데는 비교적 단순하게(글자가 올라감), 사진 속 글자 없음"',
                  '"thumb_text": "대표사진 위에 크게 넣을 후킹 문구. 2줄(줄바꿈 \\n), 줄마다 4~11자. 손해·실수·숫자로 궁금하게, 사실만, 제목과 똑같이 쓰지 말 것. 예: \"이렇게 붙이면\\n바람 그대로 들어와요\""']
    else:
        parts += ['"hero_prompt": "대표 사진 묘사(영어). 글 주제 장면, 사진 속 글자 없음"']
    if blog_kind(site) == "static":
        parts.append('"conclusion": "한 줄 결론: 바쁜 사람이 이것만 읽어도 되는 결론 1~2문장, 70자 안팎, 쉬운 말, 사실만"')
    if needs_cards(site):
        parts.append('"cards": {"slides": [...]}')
    if site.get("instagram", {}).get("enabled"):
        parts.append('"instagram": {"framework": "모음형|실수 바로잡기형|순서형|비교형|논쟁형 중 하나", "cover_hooks": ["표지 후보1", "후보2", "후보3"], '
                     '"caption": "짧고 간결하게. 첫 줄 40자 이내 후킹+핵심어(표지 문구 그대로 반복 말고 다른 각도) → 핵심 2~3줄(한 줄에 한 가지, 짧은 문장, 카드를 안 넘겨도 얻는 요점) '
                     '→ 행동 안내 한 줄(저장 또는 보내기 중 하나, 자세한 글은 프로필 링크) → 맨 끝 해시태그 3~5개(넓은 것 1 + 구체적인 것 2~4). 링크·반응 낚시·대시 금지, 이모지 3개 이하"}')
    if site.get("threads", {}).get("enabled"):
        parts.append('"threads": {"hooks": ["첫 줄 후보1", "후보2", "후보3"], "posts": ["본문: 친근한 반말, 200자 이내 후킹·에피소드, 링크 없음", "댓글: 반말, 핵심 정보 2~4줄", "대댓글: 반말 1~2줄 + {LINK}"], "topic_tag": "주제 태그 1개"}')
    m = site.get("monetization") or {}
    if (m.get("coupang") or {}).get("enabled") and m.get("stage") != "pre_adsense":
        parts.append('"coupang_wish": [{"name": "이 글 독자가 실제로 살 만한 상품(쇼핑몰에서 쓰는 이름)", "search": "쿠팡 검색어", '
                     '"after": "본문에서 이 상품을 넣을 문단의 문장 일부(그대로 복사, 15~30자)"}] 0~2개. 아래 등록된 쿠팡 링크에 없는 상품만')
    parts.append('"sources": [{"title": "출처 제목", "url": "https://..."}]')
    return "{\n  " + ",\n  ".join(parts) + "\n}"


def site_profile(site):
    keys = ["name", "topic", "audience", "tone", "url", "writing_guide"]
    prof = {k: site[k] for k in keys if site.get(k)}
    prof["base"] = {"naver": "네이버 블로그", "wordpress": "워드프레스 블로그", "appblog": "앱 안의 블로그(커먼센스 /blog, 애드센스 목표)",
                    "static": "독립 블로그(자체 도메인, 애드센스·구글 검색·구글 디스커버 목표)",
                    "none": "블로그 없음(SNS → 사이트/앱으로 유입)"}[blog_kind(site)]
    prof["sns"] = [p for p in ("instagram", "threads") if site.get(p, {}).get("enabled")]
    return json.dumps(prof, ensure_ascii=False, indent=1)


def pending_topics(site_id):
    """승인 대기 중인 글(studio/<사이트>/… 가지)의 주제 — 같은 주제를 또 만들지 않게"""
    import subprocess
    try:
        out = subprocess.run(["git", "ls-remote", "--heads", "origin", f"studio/{site_id}/*"], cwd=ROOT,
                             capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line.split(f"studio/{site_id}/", 1)[1][11:].replace("-", " ") for line in out.splitlines() if f"studio/{site_id}/" in line]


def published_posts(site_id):
    out = []
    legacy_dir = load_site(site_id).get("legacy_posts_dir")
    if legacy_dir:  # 예전 방식으로 쓴 글도 '최근 글'·내부 링크 후보로
        for f in sorted((ROOT / legacy_dir).glob("*/post.json")):
            p = load_json(f, {})
            out.append({"title": p.get("title", ""), "url": (p.get("naver") or {}).get("url")})
    for d in post_dirs(site_id):
        p = load_json(d / "post.json", {})
        url = (p.get("published") or {}).get("blog_url")
        out.append({"title": p.get("title", ""), "url": url})
    return out


def keyword_data(site):
    if site.get("keywords") is False or blog_kind(site) == "static":
        return ""  # 정치처럼 그날 뉴스로 고르는 사이트는 네이버 검색량 표를 쓰지 않아요
    own = SITES / site["id"] / "keywords.json"
    kw = load_json(own) or load_json(ROOT / "topics/keywords.json") or {}
    rows = []
    for k, v in (kw.get("keywords") or {}).items():
        if own.exists() or not site.get("seeds") or any(s.replace(" ", "") in k or k in s.replace(" ", "") for s in site.get("seeds", [])):
            rows.append(f"{k}: 월 {v.get('total')}회 ({v.get('checked')})")
    return "\n".join(rows[:60])


def coupang_items(site):
    m = site.get("monetization") or {}
    c = m.get("coupang") or {}
    if not c.get("enabled") or m.get("stage") == "pre_adsense":
        return []
    data = load_json(ROOT / c.get("links_file", f"sites/{site['id']}/coupang.json"), {})
    return [i for i in data.get("items", []) if i.get("url")]


def experiences(site):
    f = ROOT / site.get("experience_file", f"sites/{site['id']}/experience.md")
    if not f.exists():
        return ""
    blocks = re.split(r"\n(?=## )", f.read_text(encoding="utf-8"))
    ok = [b.strip() for b in blocks if re.search(r"^- 확인: 사장님", b, re.M)]
    return "\n\n".join(ok)[:4000]


def build_prompt(site, topic, notes, view=None):
    blog = blog_kind(site) != "none"
    m = site.get("monetization") or {}
    posts = published_posts(site["id"])
    p = [f"[사이트]\n{site_profile(site)}",
         f"[오늘] {now_kst():%Y-%m-%d (%a)}",
         "[최근에 쓴 제목 — 겹치지 않게]\n" + "\n".join([x["title"] for x in posts][-30:] or ["(없음)"]),
         "[승인 대기 중인 글 주제(영문 요약) — 이 주제들과도 겹치지 않게, 다른 주제로]\n" + "\n".join(pending_topics(site["id"]) or ["(없음)"])]
    if blog:
        p.append(STAGE_GUIDE.get(m.get("stage", "pre_adsense" if blog_kind(site) == "wordpress" else "adpost"), ""))
        links = [x for x in posts if x["url"]][-40:]
        if m.get("internal_links", True) and links:
            p.append("[내부 링크 후보 — 관련 있는 글만 본문에 2~3개 자연스럽게 [제목](주소)로]\n" + "\n".join(f"- {x['title']}: {x['url']}" for x in links))
        cp = coupang_items(site)
        if cp:
            p.append("[쿠팡 파트너스 링크 — 독자에게 실제로 필요한 문단에만 최대 2개, 아래 주소만 그대로 사용, 다른 쇼핑 링크 금지. "
                     "대가성 문구는 프로그램이 글 맨 위에 한 번 넣으니 본문·링크 옆에는 쓰지 마세요. "
                     "링크는 문장 안에 [상품 이름](주소)로만 넣으면 프로그램이 상품 이미지 카드로 바꿔요]\n"
                     + "\n".join(f"- {i['name']} ({i.get('note', '')}): {i['url']}" for i in cp))
    exp = experiences(site)
    if exp:
        p.append("[운영자 경험 — 사장님이 확인한 것만, 필요할 때 이 범위 안에서]\n" + exp)
    kd = keyword_data(site)
    if kd:
        p.append("[네이버 월간 검색량 (검색광고 키워드 도구, 실제 조회값)]\n" + kd)
    if topic:
        p.append(f"[주제/제목 지정]\n{topic}\n(이 주제로 쓰되 제목은 검색 키워드와 후킹을 살려 다듬어도 됩니다)")
    else:
        p.append("[주제 고르기]\n사이트 주제 안에서, 지금 시기에 검색이 많고 최근 글과 겹치지 않는 주제를 웹 검색으로 확인해 하나 고르세요. "
                 "검색량 자료가 있으면 우선 참고하고 근거를 why_this_topic 에 적으세요.\n후보 키워드: " + ", ".join(site.get("seeds", [])))
    extra = []
    if (site.get("app") or {}).get("kind") == "commonsense":
        import commonsense
        extra = commonsense.recent_inserted(site["id"])
    if extra:
        p.append("[앱에 새로 들어간 카드 — 주제로 쓰기 좋아요]\n" + "\n".join(extra[-10:]))
    if view:
        p.append("[편집자 견해 — 사장님이 직접 쓴 원문. 글의 관점과 '## 편집자 생각' 칸의 바탕]\n" + view + "\n\n"
                 "규칙: 1) 본문(사실 정리)은 견해와 상관없이 사실과 양쪽 입장을 공정하게 써요. "
                 "2) '## 편집자 생각' 칸은 이 견해를 쉬운 말로 줄여 써요. 입장·주장 방향은 절대 바꾸거나 누그러뜨리지 말고, 짧은 문단 3개 이내(합쳐서 400자 안팎). "
                 "3) 견해 속 사실(숫자·날짜·사건)은 웹 검색으로 확인해 틀리면 바로잡고, 확인 안 되면 빼요. 특정인 비방·확인 안 된 의혹 단정은 빼요. "
                 "4) 견해의 문장을 그대로 길게 옮기지 말고 사장님 말투로 다시 써요.")
    if notes:
        p.append(f"[사장님이 고쳐 달라고 한 점 — 반드시 반영]\n{notes}")
    if blog_kind(site) == "naver":
        p.append(skills.block("naver-woodenjoy-post"))
    if needs_cards(site):
        p.append(CARD_GUIDE)
        p.append(skills.block("instagram-kr"))
    if site.get("threads", {}).get("enabled"):
        p.append(THREADS_GUIDE)
        p.append(skills.block("threads-kr"))
    if img_cfg(site)["instagram"] == "photo_cards":
        p.append(PHOTO_CARD_GUIDE)
    p.append("[출력 JSON 형식]\n" + schema(site))
    return "\n\n".join(x for x in p if x)


# ---------- 파일·이미지 ----------
def brand_file(site):
    b = site.get("brand", {})
    data = {"cardLabel": b.get("cardLabel", site.get("name", "")), "handle": b.get("handle", ""), "colors": b.get("colors", {})}
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, f, ensure_ascii=False)
    f.close()
    return f.name


def render_cards(site, d):
    env = {**os.environ, "BRAND_FILE": brand_file(site)}
    tf = SITES / site["id"] / "terms.json"
    if tf.exists():
        env["TERMS_FILE"] = str(tf)
    r = subprocess.run(["node", str(ROOT / "tools/render_cards.js"), str(d)], capture_output=True, text=True, env=env)
    log("  " + (r.stdout.strip() or r.stderr.strip()).replace("\n", "\n  "))
    qa = load_json(d / "cards/qa.json", {"ok": False, "issues": [r.stderr.strip()[:300]]})
    return qa.get("issues", []) if r.returncode else []


CARD_REVIEW = """카드뉴스 이미지 눈 검사 (card-image-check 스킬 규칙). 코드 검사는 이미 통과했어요. 사람 눈으로만 잡히는 것만 보세요.
A. 내용: 1) 그림이 제목·라벨과 같은 것을 말하는가(그림을 말로 다시 설명해 보고 제목과 맞는지) 2) 부품·물건 모양이 실제와 맞는가
   3) 카드 내용이 블로그 글·캡션과 어긋나지 않는가(예: '자세한 건 블로그에'라고 했는데 글에 그 내용이 없음) 4) 표지에 약속한 개수와 실제 장 수가 맞는가
B. 글자: 5) 오타·띄어쓰기(한 자씩 읽기) 6) 글자가 그림·다른 글자와 겹치거나 잘림
C. 구성: 7) 같거나 비슷한 내용·그림이 반복되는 장 8) 표지만 보고 주제가 보이는가, 마지막 장에 행동 안내(저장·보내기·블로그)가 있는가
확실한 문제만 적으세요. 취향 의견, 애매한 것은 적지 마세요.
출력: {"issues": ["3장: 그림은 인도어인데 제목은 아웃도어", ...]} 문제가 없으면 {"issues": []}"""


def review_cards(site, d, res):
    """렌더링된 카드를 Claude가 직접 보고 내용·오타·반복을 점검해요 (코드로 못 잡는 것)"""
    import base64
    import io
    from PIL import Image
    files = sorted((d / "cards").glob("[0-9][0-9].jpg"))
    if not files or os.environ.get("MOCK_LLM"):
        return []
    blocks = []
    for i, f in enumerate(files[:12], 1):
        im = Image.open(f).convert("RGB")
        im.thumbnail((540, 675))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=80)
        blocks += [{"type": "text", "text": f"{i}장"},
                   {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]
    ctx = {"title": res.get("title"), "caption": (res.get("instagram") or {}).get("caption", ""), "article": (res.get("article_md") or "")[:6000]}
    blocks.append({"type": "text", "text": CARD_REVIEW + "\n\n" + skills.block("card-image-check") + "\n\n[글·캡션]\n" + json.dumps(ctx, ensure_ascii=False)})
    try:
        out = llm.ask_json("당신은 꼼꼼한 카드뉴스 검수자입니다. 출력은 설명 없이 JSON 한 덩어리입니다.", blocks,
                           model=(site.get("llm") or {}).get("model"), web_search=False, max_tokens=2000, mock_name="card_review")
    except Exception as e:  # noqa: BLE001  눈 검사가 실패해도 글 만들기는 계속
        log(f"  카드 눈 검사 건너뜀: {str(e)[:120]}")
        return []
    issues = [str(x) for x in (out.get("issues") or []) if str(x).strip()][:8]
    if issues:
        log("  카드 눈 검사:\n   - " + "\n   - ".join(issues))
    return issues


def make_thumb(d, text):
    """대표사진(hero.jpg) 위에 후킹 문구를 크게 얹어 네이버 홈피드 썸네일로 만들어요. 원본은 hero_raw.jpg"""
    import shutil
    raw = d / "hero_raw.jpg"
    if not raw.exists():
        shutil.copy(d / "hero.jpg", raw)
    r = subprocess.run(["node", str(ROOT / "tools/render_thumb.js"), str(raw), str(d / "hero.jpg"), text],
                       capture_output=True, text=True)
    log("  " + (r.stdout.strip() or r.stderr.strip()[:300]))


def remake_thumb(site_id, dir_, text=None):
    """이미 만든 글의 대표사진을 사실적인 사진+후킹 문구 썸네일로 다시 만들어요"""
    site = load_site(site_id)
    d = (ROOT / dir_).resolve()
    post = load_json(d / "post.json", {})
    ic = img_cfg(site)
    text = (text or post.get("thumb_text") or "").replace("\\n", "\n")
    for f in ("hero.jpg", "hero_raw.jpg"):
        (d / f).unlink(missing_ok=True)
    size = (1080, 1080) if ic["hero"].get("thumb_text") else (1200, 675)
    imagegen.generate(post["hero_prompt"] + (" " + ic["photo_style"] if ic["photo_style"] else ""), d / "hero.jpg", ic["hero"], size=size)
    if text and ic["hero"].get("thumb_text") and (d / "hero.jpg").exists():
        make_thumb(d, text)
        post["thumb_text"] = text
    for ph in post.get("photos", []):  # 빠진 본문 사진도 같이 (이미지 키가 없을 때 만든 글)
        f = d / ph["file"]
        if not f.exists():
            try:
                imagegen.generate((ph.get("prompt") or f"Photo of: {ph.get('alt', '')}") + (" " + ic["photo_style"] if ic["photo_style"] else ""), f, ic["hero"], size=(1200, 800))
            except Exception as e:  # noqa: BLE001
                log(f"  사진 {ph['file']} 실패: {e}")
    md = (d / "article.md").read_text(encoding="utf-8")
    if "[[hero]]" not in md:  # 대표사진 자리가 없으면 첫 문단 뒤에
        parts = md.split("\n\n", 2)
        md = "\n\n".join(parts[:2] + ["[[hero]]"] + parts[2:]) if len(parts) > 2 else md + "\n\n[[hero]]"
        (d / "article.md").write_text(md, encoding="utf-8")
    post.setdefault("cost", {})
    save_json(d / "post.json", post)
    preview_html(site, post, d)
    log(f"대표사진 다시 만들기 끝: {d.name} (이미지 {sum(imagegen.IMAGES.values())}장)")


OPINION_SYS = ("당신은 정치 블로그 편집자의 문장을 다듬는 교정자예요. 편집자의 입장과 주장 방향은 절대 바꾸거나 누그러뜨리거나 반대 입장을 섞지 않아요. "
               "맞춤법·문장만 자연스러운 해요체로 다듬고, 사실 주장은 본문과 출처에 있는 범위에서만. 본문과 다른 사실(숫자, 날짜)이 있으면 본문 기준으로 고치고 notes 에 적어요. "
               "특정인에 대한 욕설·모욕·확인 안 된 의혹 단정은 빼고 notes 에 적어요. 출력은 JSON 한 덩어리.")


def add_opinion(site_id, dir_, notes):
    """사장님 의견(notes)을 다듬어 글 끝 '## 편집자 생각'으로 붙여요 (출처 앞). 다시 넣으면 바꿔요."""
    site = load_site(site_id)
    d = (ROOT / dir_).resolve()
    post = load_json(d / "post.json", {})
    md = (d / "article.md").read_text(encoding="utf-8")
    md = re.sub(r"\n## 편집자 생각\n.*?(?=\n## |\Z)", "\n", md, flags=re.S).rstrip() + "\n"
    if not (notes or "").strip():
        log("의견이 비어 있어요 → 편집자 생각 칸을 뺐어요")
        post["opinion"] = ""
    else:
        res = llm.ask_json(OPINION_SYS, f"[본문]\n{md[:9000]}\n\n[편집자 의견 원문]\n{notes}\n\n"
                           '[출력 JSON]\n{"opinion_md": "다듬은 편집자 생각 2~6문단 마크다운(소제목 없이)", "notes": "바꾼 점·뺀 점(없으면 빈 문자열)"}',
                           model=site.get("llm", {}).get("model"), web_search=False, mock_name=f"{site_id}_opinion")
        op = (res.get("opinion_md") or "").strip()
        block = f"## 편집자 생각\n\n> 아래는 시시비비노트 편집자의 개인 의견이에요. 위 사실 정리와 구분해서 읽어 주세요.\n\n{op}\n"
        m = re.search(r"\n## (참고 자료|출처|참고)\b", md)
        md = (md[:m.start()] + "\n" + block + md[m.start():]) if m else md.rstrip() + "\n\n" + block
        post["opinion"] = notes
        post["opinion_edit_notes"] = res.get("notes", "")
        log(f"편집자 생각 넣음 ({len(op)}자){' · ' + res['notes'] if res.get('notes') else ''}")
    (d / "article.md").write_text(md, encoding="utf-8")
    prev = post.get("cost")
    post["cost"] = usage_cost(prev)
    save_json(d / "post.json", post)
    preview_html(site, post, d)


def make_images(site, res, d):
    d.mkdir(parents=True, exist_ok=True)
    ic = img_cfg(site)
    if ic["hero"].get("provider") != "none" and not (d / "hero.jpg").exists() and res.get("hero_prompt"):
        try:
            size = (1080, 1080) if ic["hero"].get("thumb_text") else (1200, 675)
            imagegen.generate(res["hero_prompt"] + (" " + ic["photo_style"] if ic["photo_style"] else ""), d / "hero.jpg", ic["hero"], size=size)
            if ic["hero"].get("thumb_text") and res.get("thumb_text") and (d / "hero.jpg").exists():
                make_thumb(d, res["thumb_text"])
        except Exception as e:  # noqa: BLE001
            log(f"  대표 이미지 실패: {e}")
    for ph in (res.get("photo_prompts") or [])[:ic["photos"]]:
        f = d / f"photo{ph['id']}.jpg"
        if f.exists():
            continue
        size = (1080, 1350) if ic["instagram"] == "photo_cards" else (1200, 800)
        try:
            imagegen.generate(ph["prompt"] + (" " + ic["photo_style"] if ic["photo_style"] else ""), f, ic["hero"], size=size)
        except Exception as e:  # noqa: BLE001
            log(f"  사진 {ph['id']} 실패: {e}")
    # 없는 사진을 가리키는 카드는 정리해요
    for s in (res.get("cards") or {}).get("slides", []):
        b = s.get("body") or {}
        if b.get("kind") == "image" and b.get("src", "hero.jpg") == "hero.jpg" and (d / "hero_raw.jpg").exists():
            b["src"] = "hero_raw.jpg"
        if b.get("kind") == "image" and not (d / b.get("src", "hero.jpg")).exists():
            s.pop("body")
        if s.get("photo") and not (d / s["photo"]).exists():
            s.pop("photo")


def write_post(site, res, d, topic):
    d.mkdir(parents=True, exist_ok=True)
    platforms = []
    if blog_kind(site) != "none":
        platforms.append("blog")
    platforms += [p for p in ("threads", "instagram") if site.get(p, {}).get("enabled")]
    old = load_json(d / "post.json", {})
    post = {
        "id": f"{site['id']}/{d.name}", "site": site["id"], "title": res["title"], "status": "draft",
        "created_at": now_kst().isoformat(timespec="minutes"), "requested_topic": topic or "",
        "keywords": res.get("keywords", {}), "brief": res.get("brief", {}), "why_this_topic": res.get("why_this_topic", ""),
        "meta_description": res.get("meta_description", ""), "hero_prompt": res.get("hero_prompt", ""), "thumb_text": res.get("thumb_text", ""),
        "category": res.get("category", ""), "summary": res.get("summary") or old.get("summary") or [],
        "conclusion": res.get("conclusion") or old.get("conclusion", ""),
        "opinion": old.get("opinion", ""),
        "photos": [{"file": f"photo{p['id']}.jpg", "alt": p.get("alt", ""), "prompt": p.get("prompt", "")} for p in res.get("photo_prompts") or []],
        "sources": res.get("sources", []), "platforms": platforms, "blog_platform": blog_kind(site),
        "instagram": res.get("instagram") if "instagram" in platforms else None,
        "threads": res.get("threads") if "threads" in platforms else None,
        "revision": old.get("revision", 0) + (1 if old else 0),
    }
    md = res.get("article_md")
    if md:
        cp = coupang_items(site)
        disclosure = (site.get("monetization") or {}).get("coupang", {}).get(
            "disclosure", "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.")
        # 대가성 문구는 맨 위 한 번만 (공정위 지침: 본문 첫 부분) → 링크 옆 중복 문구 제거
        md = re.sub(r"\s*[*_]?\(?이 링크는 쿠팡 파트너스[^)\n]*\)?[*_]?", "", md)
        if cp and "link.coupang.com" in md and disclosure not in md:
            md = disclosure + "\n\n" + md
            post["coupang"] = True
        (d / "article.md").write_text(md, encoding="utf-8")
        res["article_md"] = md
    wish = [w for w in (res.get("coupang_wish") or []) if w.get("name")]
    if wish:
        post["coupang_wish"] = wish
        add_coupang_wish(site, wish, d, post["title"])
    save_json(d / "post.json", post)
    if res.get("cards"):
        save_json(d / "cards.json", res["cards"])
    return post


def add_coupang_wish(site, wish, d, title):
    """링크가 필요한 상품을 쿠팡 링크 목록에 '링크 필요'로 올려요 → 관리화면 '쿠팡 링크'에 보여요"""
    c = (site.get("monetization") or {}).get("coupang") or {}
    f = ROOT / c.get("links_file", f"sites/{site['id']}/coupang.json")
    data = load_json(f, {"items": []})
    have = {(i.get("search") or i.get("name") or "").replace(" ", "") for i in data.get("items", [])}
    for w in wish:
        k = (w.get("search") or w["name"]).replace(" ", "")
        if k in have:
            continue
        data.setdefault("items", []).append({
            "key": slugify(w.get("search") or w["name"])[:40] or f"item-{len(data['items']) + 1}",
            "name": w["name"], "search": w.get("search", ""), "url": "",
            "status": f"링크 필요 ({now_kst():%m/%d}, {title[:30]})",
            "post_dir": d.relative_to(ROOT).as_posix(), "after": w.get("after", ""), "site": site["id"]})
        have.add(k)
    save_json(f, data)


def preview_html(site, post, d):
    f = d / "article.md"
    if not f.exists():
        return
    alts = {p["file"]: p["alt"] for p in post.get("photos", [])}

    def img(name):
        if name == "hero":
            return ("hero.jpg", post["title"]) if (d / "hero.jpg").exists() else (None, None)
        kind, n = name.split(":")
        if kind == "photo":
            fn = f"photo{n}.jpg"
            return (fn, alts.get(fn, "")) if (d / fn).exists() else (None, None)
        fn = f"cards/{int(n):02d}.jpg"
        return (fn, f"카드 {n}") if (d / fn).exists() else (None, None)
    (d / "article.html").write_text(mdhtml.convert(f.read_text(encoding="utf-8"), img), encoding="utf-8")


# ---------- AI 티 다듬기 (im-not-ai 규칙) ----------
def humanize(site, md):
    if not md or not (site.get("monetization") or {}).get("humanize", True) or os.environ.get("MOCK_LLM"):
        return md
    rules = skills.text("humanize-korean", 14000) or (ROOT / "tools/humanize/quick-rules.md").read_text(encoding="utf-8")[:14000]
    res = llm.ask_json(
        "당신은 한국어 윤문가입니다. 사실·숫자·고유명사·링크·[[...]] 표시·표·제목 구조는 그대로 두고 AI 티가 나는 문장만 고칩니다. 출력은 JSON 한 덩어리.",
        "아래 규칙으로 블로그 글에서 AI 티가 나는 문장만 찾아 고쳐 주세요. 고칠 게 없으면 빈 목록. 후킹(첫 문단의 강한 말)은 살리세요.\n"
        "비용 절약을 위해 전체 글을 다시 쓰지 말고, 바꿀 문장만 원문 그대로(from)와 고친 문장(to)으로 주세요. 최대 25개.\n\n[규칙]\n" + rules
        + '\n\n[글]\n' + md + '\n\n출력: {"edits": [{"from": "원문 문장 그대로", "to": "고친 문장"}]}',
        model=(site.get("llm") or {}).get("model"), web_search=False, mock_name="humanize")
    new = md
    if res.get("article_md"):
        new = res["article_md"]
    for e in (res.get("edits") or [])[:25]:
        f, t = (e.get("from") or "").strip(), (e.get("to") or "").strip()
        if f and t and new.count(f) == 1:
            new = new.replace(f, t)
    keep = re.findall(r"\[\[[^\]]+\]\]|https?://[^\s)]+|\d[\d,.]*", md)
    lost = [k for k in set(keep) if k not in new]
    ratio = 1 - difflib.SequenceMatcher(None, md, new).ratio()
    if lost or ratio > 0.35:
        log(f"  AI 티 다듬기 취소 (바뀐 비율 {ratio:.0%}, 빠진 표시·숫자 {len(lost)}개)")
        return md
    log(f"  AI 티 다듬기 완료 (바뀐 비율 {ratio:.0%})")
    return new


# ---------- 실행 ----------
def usage_cost(prev=None):
    """이번 실행에서 쓴 Claude 토큰·웹 검색·사진 수와 추정 비용. 다시 만들기를 하면 누적해요."""
    pr = load_json(ROOT / "engine/prices.json", {})
    c = {"claude": {}, "images": {}, "usd": 0.0}
    for m, u in llm.USAGE.items():
        p = (pr.get("claude") or {}).get(m) or (pr.get("claude") or {}).get("default") or {}
        usd = u["input_tokens"] / 1e6 * p.get("input_per_m", 0) + u["output_tokens"] / 1e6 * p.get("output_per_m", 0) \
            + u["web_searches"] / 1000 * pr.get("web_search_per_1000", 0)
        c["claude"][m] = {**u, "usd": round(usd, 4)}
        c["usd"] += usd
    for m, n in imagegen.IMAGES.items():
        each = (pr.get("image_per_each") or {}).get(m, (pr.get("image_per_each") or {}).get("default", 0))
        c["images"][m] = {"count": n, "usd": round(n * each, 4)}
        c["usd"] += n * each
    if prev and prev.get("total_usd"):
        c["previous_usd"] = round(prev["total_usd"], 4)
    total = c["usd"] + c.get("previous_usd", 0)
    c["usd"] = round(c["usd"], 4)
    c["total_usd"] = round(total, 4)
    c["total_krw"] = int(round(total * pr.get("usd_krw", 1400), -1))
    c["note"] = "추정치 (engine/prices.json 단가 기준). 실제 청구액은 Anthropic 콘솔·Google 결제 화면 기준"
    log(f"  비용 추정: Claude+사진 약 {c['total_krw']:,}원 (${total:.3f})")
    return c

def season_candidates(site, n=8):
    """계절 달력 + 구글 트렌드로 주제 후보를 만들고 네이버 월간 검색 수로 순위를 매겨요 (건강 블로그처럼 시기에 따라 검색이 바뀌는 사이트)."""
    import trends
    now = now_kst()
    cal = load_json(SITES / site["id"] / "season.json", {})
    nxt = (now.month % 12) + 1
    hints = cal.get(str(now.month), []) + ([f"(다음 달) {x}" for x in cal.get(str(nxt), [])] if now.day >= 20 else [])
    tr = trends.google_trends()
    tr_txt = "\n".join(f"- {t['keyword']} (검색 {t['traffic_label']})" for t in tr[:25])
    cats = (site.get("blog") or {}).get("categories") or []
    prompt = "\n\n".join([
        f"[사이트]\n{site_profile(site)}", f"[오늘] {now:%Y-%m-%d (%a)}",
        "[이 시기 건강 주제 힌트 — 사실이 아니라 후보]\n" + "\n".join(f"- {h}" for h in hints),
        "[구글 트렌드 한국 실시간 인기 검색어 — 건강과 관련 있는 것만 참고]\n" + (tr_txt or "(못 읽음)"),
        "[최근에 쓴 제목 — 겹치지 않게]\n" + "\n".join([x["title"] for x in published_posts(site["id"])][-60:] or ["(없음)"]),
        "[승인 대기 중인 글 주제]\n" + "\n".join(pending_topics(site["id"]) or ["(없음)"]),
        f"이 블로그에 쓸 주제 후보 {n}개를 골라 주세요. 지금 시기에 사람들이 실제로 검색할 만한 것, 최근 제목과 겹치지 않는 것. "
        f"카테고리는 {' / '.join(cats)} 중 하나이고 셋이 고르게 섞이게 해요. 계절 건강만 몰리지 않게 건강 루틴·증상 관리도 2개 이상. "
        "keyword 는 네이버에서 사람들이 실제로 치는 검색어(띄어쓰기 없이 2~12자, 예: 독감예방접종, 수면부족증상). "
        'JSON: {"ideas": [{"title": "제목안(핵심 키워드 앞쪽, 과장 없이 사실만)", "keyword": "네이버 검색어", "category": "카테고리", '
        '"trend_keyword": "관련 있는 구글 트렌드 검색어(없으면 빈 문자열)", "angle": "이 글이 답할 질문 한 줄"}]}'])
    res = llm.ask_json(SYSTEM, prompt, model="claude-sonnet-5-5", web_search=False, max_tokens=3000, mock_name=f"{site['id']}_ideas")
    out = []
    for x in (res.get("ideas") or [])[:n]:
        nv = trends.naver_volume(x.get("keyword") or "")
        t = next((t for t in tr if x.get("trend_keyword") and t["keyword"] == x["trend_keyword"]), None)
        x["metrics"] = {"naver_month": nv, "trend": t["keyword"] if t else "", "trend_label": t["traffic_label"] if t else ""}
        x["why"] = (f"네이버 월간 검색 {nv:,}회" if nv else "네이버 검색 수 확인 못 함") + (f", 구글 검색 급증 '{t['keyword']}' {t['traffic_label']}" if t else "") + f", {now.month}월 시기 주제"
        x["score"] = (nv or 0) + (t["traffic"] if t else 0)
        out.append(x)
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def pick_topic(site):
    c = season_candidates(site)
    if not c:
        return None
    x = c[0]
    log(f"  주제 자동 선택: {x['title']} ({x['why']}) · 다른 후보: " + " | ".join(y["title"] for y in c[1:4]))
    return (f"{x['title']}\n카테고리: {x.get('category', '')}\n이 글이 답할 질문: {x.get('angle', '')}\n"
            f"고른 근거(why_this_topic 에 그대로 적기): {x['why']}")


def generate(site_id, topic=None, notes=None, out=None, view=None):
    site = load_site(site_id)
    llm_cfg = site.get("llm", {})
    if not topic and not out and site.get("topic_picker") == "season_trend" and not os.environ.get("MOCK_LLM"):
        topic = pick_topic(site)
    log(f"[{site['name']}] 글 만들기 시작 · 주제: {topic or '자동 선택'}")
    res = llm.ask_json(SYSTEM, build_prompt(site, topic, notes, view), model=llm_cfg.get("model"),
                       web_search=llm_cfg.get("web_search", True), mock_name=f"{site_id}_post")
    d = (ROOT / out).resolve() if out else CONTENT / site_id / f"{now_kst():%Y-%m-%d}-{slugify(res.get('slug') or res['title'])}"
    prev_cost = load_json(d / "post.json", {}).get("cost") if out else None
    issues = []
    for attempt in range(3):
        make_images(site, res, d)
        post = write_post(site, res, d, topic)
        card_issues = render_cards(site, d) if needs_cards(site) else []
        if needs_cards(site) and not card_issues:
            card_issues = review_cards(site, d, res)
        issues = checks.check(site, post, res.get("article_md")) + [f"카드: {x}" for x in card_issues]
        cp_urls = {i["url"] for i in coupang_items(site)}
        for u in re.findall(r"https?://link\.coupang\.com/\S+?(?=[)\s])", res.get("article_md") or ""):
            if u not in cp_urls:
                issues.append(f"블로그: 등록되지 않은 쿠팡 링크 {u[:40]}")
        if not issues:
            break
        log("  점검에 걸림 → 고치기:\n   - " + "\n   - ".join(issues))
        if attempt == 2 or os.environ.get("MOCK_LLM"):
            break
        # 비용 절약: 걸린 항목(최상위 키)만 다시 받아서 합쳐요 (전체를 다시 쓰지 않음)
        need = sorted({"cards" if x.startswith("카드") else "instagram" if x.startswith("인스타") else
                       "threads" if x.startswith("스레드") else "article_md" for x in issues})
        if any("결론" in x for x in issues):
            need.append("conclusion")
        if any("출처(sources)" in x for x in issues):
            need.append("sources")
        part = {k: res.get(k) for k in need}
        if "article_md" in need:
            part["meta_description"] = res.get("meta_description")
        fix = llm.ask_json(SYSTEM, "점검에 걸린 부분만 고쳐 주세요. 사실과 후킹은 유지하세요. "
                           f"출력은 이 키들만 담은 JSON 한 덩어리: {list(part.keys())}\n\n"
                           f"[점검 결과]\n- " + "\n- ".join(issues) + "\n\n[고칠 부분]\n" + json.dumps(part, ensure_ascii=False),
                           model=llm_cfg.get("model"), web_search=False, mock_name=f"{site_id}_post")
        res = {**res, **{k: v for k, v in fix.items() if k in part and v}}
    if res.get("article_md") and not os.environ.get("MOCK_LLM"):
        import sources
        md2, dead = sources.verify_article((d / "article.md").read_text(encoding="utf-8"))
        if dead:
            log(f"  열리지 않는 출처·링크 {len(dead)}개 뺌: " + ", ".join(dead[:5]))
            (d / "article.md").write_text(md2, encoding="utf-8")
            res["article_md"] = md2
            p_ = load_json(d / "post.json")
            p_["sources"] = [x for x in p_.get("sources", []) if x.get("url") not in dead]
            p_["dead_links_removed"] = dead
            save_json(d / "post.json", p_)
    if not issues and res.get("article_md"):
        new = humanize(site, res["article_md"])
        if new != res["article_md"] and not checks.check(site, load_json(d / "post.json"), new):
            (d / "article.md").write_text(new, encoding="utf-8")
    post = load_json(d / "post.json")
    post["checks"] = {"ok": not issues, "issues": issues, "at": now_kst().isoformat(timespec="minutes")}
    if view:
        post["opinion"] = view
    post["cost"] = usage_cost(prev_cost)
    save_json(d / "post.json", post)
    preview_html(site, post, d)
    log(f"완료: {d.relative_to(ROOT)} · 점검 {'통과' if not issues else '실패 ' + str(len(issues)) + '건'}")
    print(f"::set-output-dir::{d.relative_to(ROOT)}")
    return d, issues


def ideas(site_id):
    site = load_site(site_id)
    if site.get("topic_picker") == "season_trend":
        c = season_candidates(site, 10)
        save_json(SITES / site_id / "ideas.json", {"ideas": c[:6], "updated": now_kst().isoformat(timespec="minutes"),
                  "basis": "이달의 건강 주제 달력 + 구글 트렌드 한국 실시간 인기 검색어 + 네이버 월간 검색 수(검색광고 키워드 도구)", "cost": usage_cost()})
        log("글감 저장: " + " | ".join(f"{x['title']} ({x['why']})" for x in c[:6]))
        return
    if site.get("opinion"):  # 정치처럼 사장님이 주제를 고르고 견해를 쓰는 사이트 → 숫자(검색 급증·기사 수)로 고르기
        import trends
        tr = trends.google_trends()
        pool = trends.news_pool()
        log(f"  구글 트렌드 {len(tr)}개, {trends.source_name()} 정치 헤드라인 {len(pool)}개")
        tr_txt = "\n".join(f"- {t['keyword']} (검색 {t['traffic_label']}) 관련 기사: " + " / ".join(n["title"] for n in t["news"]) for t in tr[:20])
        pool_txt = "\n".join(f"- {x['title']} :: {x['desc']}" for x in pool[:120])
        prompt = "\n\n".join([
            f"[사이트]\n{site_profile(site)}", f"[지금] {now_kst():%Y-%m-%d %H:%M}",
            "[최근 쓴 제목 — 겹치지 않게]\n" + "\n".join([x["title"] for x in published_posts(site_id)][-30:] or ["(없음)"]),
            "[구글 트렌드 한국 실시간 인기 검색어]\n" + (tr_txt or "(못 읽음)"),
            f"[{trends.source_name()} 최근 24시간 정치 헤드라인]\n" + (pool_txt or "(못 읽음)"),
            "위 자료만 보고(웹 검색 없이) 지금 사람들이 가장 많이 보는 정치 이슈 후보 6개를 골라 주세요. 연예·스포츠·사건사고는 정치와 직접 관련 없으면 빼요. "
            "헤드라인이 여러 개 겹치는 이슈일수록 좋아요. 사실은 위 헤드라인에 있는 것만 쓰고 지어내지 마세요. "
            "한쪽 진영만 쓰는 이름은 피하거나 두 이름을 같이 써요. "
            'JSON: {"ideas": [{"title": "후킹 있는 제목안(사실만)", "keyword": "네이버 뉴스 검색어(2~3단어, 이 이슈 기사만 걸리게)", '
            '"trend_keyword": "관련 있는 구글 트렌드 검색어(없으면 빈 문자열)", "facts": "핵심 사실 2문장(쉬운 말)", '
            '"sides": "찬성 측 한 줄 / 반대 측 한 줄", "question": "사장님께 묻는 질문 한 줄(견해 쓰기 쉽게)"}]}'])
        res = llm.ask_json(SYSTEM, prompt, model=site.get("llm", {}).get("model"), web_search=False, mock_name=f"{site_id}_ideas", max_tokens=5000)
        ranked = []
        for x in (res.get("ideas") or [])[:6]:
            n, top = trends.count_24h(x.get("keyword") or x.get("title", ""))
            t = next((t for t in tr if x.get("trend_keyword") and t["keyword"] == x["trend_keyword"]), None) or trends.trend_match(x.get("keyword", ""), tr)
            n6 = trends.count_6h(x.get("keyword") or x.get("title", "")) if n >= 100 else 0
            x["metrics"] = {"news_24h": n, "news_6h": n6, "news_capped": n >= 100, "trend": t["keyword"] if t else "", "trend_traffic": t["traffic"] if t else 0,
                            "trend_label": t["traffic_label"] if t else ""}
            nv = trends.naver_volume(x.get("keyword") or "")
            x["metrics"]["naver_month"] = nv
            x["links"] = top
            x["why"] = f"{trends.source_name()} 24시간 기사 {n}{'+' if n >= 100 else ''}건" + (f" (최근 6시간 {n6}건)" if n >= 100 else "") + (f", 구글 검색 급증 '{t['keyword']}' {t['traffic_label']}" if t else "") + (f", 네이버 월간 검색 {nv:,}회" if nv else "")
            x["score"] = n + n6 + (t["traffic"] / 100 if t else 0) + ((nv or 0) / 100)
            ranked.append(x)
        ranked.sort(key=lambda x: x["score"], reverse=True)
        out = {"ideas": ranked[:3], "updated": now_kst().isoformat(timespec="minutes"),
               "basis": f"구글 트렌드 한국 실시간 인기 검색어 + {trends.source_name()} 최근 24시간 기사 수 + 네이버 월간 검색 수(검색광고 키워드 도구)", "cost": usage_cost()}
        save_json(SITES / site_id / "ideas.json", out)
        log("이슈 후보 3개 저장: " + " | ".join(f"{x['title']} ({x['why']})" for x in out["ideas"]))
        return
    prompt = "\n\n".join([
        f"[사이트]\n{site_profile(site)}", f"[오늘] {now_kst():%Y-%m-%d}",
        "[최근 제목]\n" + "\n".join([x["title"] for x in published_posts(site_id)][-30:] or ["(없음)"]),
        "[검색량]\n" + (keyword_data(site) or "(자료 없음)"),
        "웹 검색으로 지금 시기에 검색 수요가 있고 수익(애드센스·애드포스트 단가, 제휴)에도 유리한 주제를 확인해 글감 10개를 추천하세요. 최근 제목과 겹치지 않게. "
        'JSON: {"ideas": [{"title": "후킹 있는 제목안", "keyword": "핵심 키워드", "why": "근거(검색량/시기/이슈/수익성)", "angle": "다른 글과 다른 점"}]}'])
    res = llm.ask_json(SYSTEM, prompt, model=site.get("llm", {}).get("model"), web_search=True, mock_name=f"{site_id}_ideas")
    res["updated"] = now_kst().isoformat(timespec="minutes")
    save_json(SITES / site_id / "ideas.json", res)
    log(f"글감 {len(res.get('ideas', []))}개 저장 → sites/{site_id}/ideas.json")


def th_problems(posts, topic_tag=None):
    """반말·길이·AI 티·반응 낚시·주제 태그 점검"""
    out = []
    jon = sum(len(re.findall(r"(요|니다|세요)[.!?]?(\s|$)", t)) for t in posts)
    if jon:
        out.append(f"존댓말 문장 {jon}개 → 전부 반말로")
    if posts and len(posts[0]) > 200:
        out.append(f"본문 {len(posts[0])}자 → 200자 이내로 줄이기")
    return out + checks.threads_style(posts, topic_tag)


def rewrite_threads(site_id, dir_):
    """이미 만든 글의 스레드 문구만 새 규칙으로 다시 써요 (글·카드는 그대로)"""
    site = load_site(site_id)
    d = (ROOT / dir_).resolve()
    post = load_json(d / "post.json")
    md = (d / "article.md").read_text(encoding="utf-8") if (d / "article.md").exists() else ""
    exp = experiences(site) if "experiences" in globals() else ""
    res = llm.ask_json(SYSTEM, THREADS_GUIDE + "\n" + skills.block("threads-kr") + "\n[글 제목] " + post["title"] + "\n[운영자 경험]\n" + (exp or "(없음)")
                       + "\n[블로그 글]\n" + md[:9000] + '\n\n출력: {"hooks": ["첫 줄 후보1", "후보2", "후보3"], "posts": ["본문", "댓글", "대댓글 + {LINK}"], "topic_tag": "주제 태그 1개"}',
                       model=(site.get("llm") or {}).get("model"), web_search=False, mock_name="threads")
    posts = [x for x in (res.get("posts") or []) if x]
    hooks, tag = res.get("hooks") or [], res.get("topic_tag")
    bad = th_problems(posts, tag)
    if bad:
        res = llm.ask_json(SYSTEM, THREADS_GUIDE + "\n아래 스레드 글을 고쳐 주세요: " + " / ".join(bad) + "\n\n" + json.dumps({"posts": posts, "topic_tag": tag}, ensure_ascii=False)
                           + '\n\n출력: {"posts": [...], "topic_tag": "..."}', model=(site.get("llm") or {}).get("model"), web_search=False, mock_name="threads")
        posts = [x for x in (res.get("posts") or []) if x] or posts
        tag = res.get("topic_tag") or tag
    if len(posts) < 2:
        raise SystemExit("스레드 문구를 못 받았어요")
    if "{LINK}" not in posts[-1]:
        posts[-1] += "\n{LINK}"
    post["threads"] = {"posts": posts, "hooks": hooks, "topic_tag": tag}
    post.setdefault("cost", {})
    save_json(d / "post.json", post)
    log(f"스레드 다시 씀: {post['title']}\n  " + "\n  ---\n  ".join(posts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--topic")
    ap.add_argument("--notes")
    ap.add_argument("--view", help="편집자 견해(사장님 의견) — 이 견해를 바탕으로 글을 써요")
    ap.add_argument("--out")
    ap.add_argument("--ideas", action="store_true")
    ap.add_argument("--threads", help="이 글 폴더의 스레드 문구만 다시 쓰기")
    ap.add_argument("--thumb", help="이 글 폴더의 대표사진+홈피드 썸네일만 다시 만들기 (--notes = 썸네일 문구, 줄바꿈은 \\n)")
    ap.add_argument("--opinion", help="이 글 폴더에 편집자 생각(--notes)을 붙이기")
    a = ap.parse_args()
    if a.opinion:
        add_opinion(a.site, a.opinion, a.notes)
    elif a.thumb:
        remake_thumb(a.site, a.thumb, a.notes)
    elif a.threads:
        rewrite_threads(a.site, a.threads)
    elif a.ideas:
        ideas(a.site)
    else:
        _, iss = generate(a.site, a.topic, a.notes, a.out, a.view)
        sys.exit(1 if iss else 0)
