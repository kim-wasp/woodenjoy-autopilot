# 인수인계 메모 (새 대화를 시작하면 이 파일부터 읽어요)

마지막 갱신: 2026-11-23. 결정이 바뀌면 이 파일을 같이 고쳐요. 공개 저장소라 비밀값, 보안 취약점 세부는 여기에 쓰지 않아요.

## 사이트와 일정
| 사이트 | 플랫폼 | 블로그 발행 | 모델 | 상태 |
|---|---|---|---|---|
| 우드엔조이 (woodenjoy) | 네이버 cafe_peanut, 인스타 woodenjoy00, 스레드 | 주 5편 (월~금 08:00) | Opus | 애드포스트 승인, 쿠팡 파트너스 |
| 시시비비노트 (sisibibi) | sisibibinote.kr (Cloudflare 정적), 스레드 sisibibi.note | 사장님 견해를 쓴 날 (12:00) | Opus | 애드센스 신청 12월 중순 예정 (글 25~30편, 색인 확인 뒤) |
| forsmartlife | WordPress (카페24), WellnessNote | 주 3편 (월수금 07:00) | Opus | 애드센스 신청 12월 초 예정 |
| infobay (커먼센스 블로그) | myinfobay.com /blog (Vercel + Supabase), infobay_kr | 주 3편 | Opus (Sonnet 전환 검토 중) | 애드센스는 블로그 글이 쌓인 뒤 맨 나중 |
| itinfobay | 꺼져 있음 | | | |

## 비용 (2026-11-23 기준)
- 사장님 구독: Claude Max (월 API 크레딧 $100, 남으면 소멸). Ultra는 월 $200 크레딧.
- 정기 추정: Claude 월 약 $173~186, Gemini 이미지 월 약 32,000원 (장당 약 176원)
- 결정: 승인 전 사이트는 품질 우선이라 Opus 유지. infobay만 Sonnet 전환 제안했고 사장님 답 대기.
- 일주일 뒤(11/30 전후) 할 일: 관리화면 사용량과 Console 청구 대조, 캐시 효과 확인, Max 유지 / Ultra 전환 판단 (월 API $180 넘거나 채팅 한도에 자주 걸리면 Ultra)
- 사용량 장부: engine/usage.py → usage/YYYY-MM/*.json → tools/usage_report.py → status/usage_summary.json → 관리화면 '사용량'
- 11/23 고친 것: 웹 검색 입력 토큰 과소 집계, 웹 검색 호출에 프롬프트 캐시, 잘린 JSON 재요청 방식, 글감 찾기는 Sonnet

## 인증과 키
- Claude: GitHub Actions 안에서는 WIF (서비스 계정 woodenjoy-autopilot, 규칙 github-workloads, 주체 repo:kim-wasp@275420324/woodenjoy-autopilot@1423432938:ref:refs/heads/main, ref 클레임 refs/heads/main). 실패하면 ANTHROPIC_API_KEY 로 대체.
- 남은 일: 며칠 WIF로 문제없으면 GitHub Secrets 의 ANTHROPIC_API_KEY 와 Console 키(woodenjoy-key-2) 삭제. 옛 키 woodenjoy-key 는 11/30 만료.
- 쿠팡 파트너스 Open API: COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY (11/18). 글에 필요한 비교 상품 2~3개를 API로 찾아 '어떤 걸 살까' 한 곳에 비교표와 함께. 대가성 문구는 맨 위, 업로드 직전에도 강제.
- Gemini 이미지는 선불 크레딧 (AI Studio). 11/19에 소진돼 대표사진이 빠진 적 있음 → 자동 충전 권장했음.

## 검색 노출 (서치콘솔, 11/21~23)
- forsmartlife: Rank Math 사이트맵 캐시가 11/16부터 굳어 있었음 → Links Per Sitemap 바꿔 저장해서 풀림. 합친 글 21개는 임시글 + 301 유지.
- forsmartlife 색인 안 된 글 10개 색인 요청 부탁드림 (봄·계절 글 위주). 12월 초에 들어갔는지 확인, 안 들어가면 고치거나 합치기.
- myinfobay: 카테고리 페이지 noindex, 사이트맵에서 제외 (11/21). 블로그 글은 새 도메인이라 색인 대기.
- 시시비비: 사이트맵 20개 모두 색인.

## 사장님 원칙 (요약)
- 답은 한국어 존댓말, 결론 먼저, 강한 의견. 안내는 최신 공식 문서로 확인하고 드리기.
- 글·SNS: 후킹은 세게, 사실만. AI 이미지는 고지. 테스트로 API 크레딧 쓰지 말고 다음 정기 글에 바로 적용.
- 비밀값은 채팅에 붙여 넣지 않고 GitHub Secrets 에만. 공개 저장소에 민감한 점검 결과를 평문으로 올리지 않기.
- 무조건 막는 게 답은 아님 (Googlebot, 애드센스 크롤러는 막지 않기).
