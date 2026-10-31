# 콘텐츠 스튜디오 — 여러 사이트 자동화 프로그램

블로그(워드프레스·네이버) + 인스타 + 스레드를 사이트마다 따로 설정해서
**제목(검색 기반) → 글 → 대표 사진 → 정보 카드 → 인스타 카드뉴스 → 스레드 → 점검 → 승인 → 예약 업로드**까지 하는 프로그램이에요.
명령어 대신 **웹 관리화면**(휴대폰·PC)에서 써요.

## 구성
| 부분 | 위치 | 하는 일 |
|---|---|---|
| 관리화면 | `studio/` (Vercel) | 로그인, 홈, 승인 대기(미리보기), 만들기, 글감, 일정, 사이트 설정, 연결 가이드 |
| 엔진 | `engine/` | `generate.py` 글·이미지·카드 생성 + 점검, `publish.py` 업로드, `scheduler.py` 일정 |
| 사이트 설정 | `sites/<id>/site.json` | 주제·독자·말투·연결 계정·일정·모델·카드 색 (관리화면에서 고쳐요) |
| 글 | `content/<id>/<날짜-슬러그>/` | post.json, article.md/html, hero.jpg, cards/*.jpg |
| 자동 실행 | `.github/workflows/studio-*.yml` | 30분마다 '만들 차례'·'올릴 차례' 확인 |

흐름: 만들기(버튼 또는 예약) → 승인 요청(PR) → 관리화면에서 미리보기·승인 → 사이트별 업로드 시간에 자동 업로드 → 일정·결과 기록

## 사이트마다 고르는 것 (관리화면 → 사이트)
- **기본 채널**: 네이버 블로그 / 워드프레스 블로그 / 앱 안의 블로그(커먼센스 /blog) / 블로그 없음
- **더할 SNS**: 인스타, 스레드 각각 켜고 끄기
- **수익화 단계**: 애드센스 승인 전(신뢰·독창성, 제휴 링크 없음) → 애드센스 운영 중(클릭률·체류·내부 링크) / 네이버 애드포스트
  - 관련 글 내부 링크, AI 티 다듬기(im-not-ai 규칙으로 한 번 더 윤문, 바뀐 비율 35% 넘거나 숫자·링크가 빠지면 취소), 쿠팡 파트너스(등록한 링크만, 대가성 문구 자동)
- **이미지**: 블로그 본문(정보 카드 / AI 사진 / 섞어서 / 대표 사진만), 인스타(정보 카드뉴스 / 사진 카드뉴스), 사진 스타일, 글당 사진 수
- **앱 카드(커먼센스)**: 월·목 오전에 사회 이슈를 모아 투표 카드 후보 10개 → 관리화면 '앱 카드'에서 추가/빼기 → 추가한 것만 앱 DB에 들어가고, 새 카드는 SNS 글감으로도 쓰여요

## 처음 설정 (한 번만)
1. **GitHub 설정**: 저장소 → Settings → Actions → General → 맨 아래 *Allow GitHub Actions to create and approve pull requests* 체크 → Save
2. **비밀키** (Settings → Secrets and variables → Actions)
   - `ANTHROPIC_API_KEY` — Claude API (글쓰기)
   - `OPENAI_API_KEY` 또는 `GEMINI_API_KEY` — 대표 사진
   - 사이트별: `IG_TOKEN_INFOBAY`, `THREADS_TOKEN_INFOBAY`, `WP_FORSMARTLIFE_PASS` … (사이트 설정에 적은 이름과 같게)
   - 커먼센스 카드: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` / 네이버: `UPLIKA_API_KEY`(이미 있음)
3. **관리화면 토큰**: GitHub → 프로필 → Settings → Developer settings → Fine-grained tokens → 새 토큰
   - 저장소: woodenjoy-autopilot 하나 / 권한: Contents·Pull requests·Actions = Read and write
4. **Vercel**: Add New → Project → 이 저장소 → **Root Directory = `studio`** → Environment Variables
   - `ADMIN_PASSWORD` (관리화면 비밀번호), `GITHUB_TOKEN` (3번 토큰), `GITHUB_REPO` = `kim-wasp/woodenjoy-autopilot`
5. 관리화면 → **연결 가이드**에 플랫폼별 연결 방법이 있어요

## 사이트 현황
| id | 사이트 | 블로그 | SNS | 상태 |
|---|---|---|---|---|
| infobay | 상식 (커먼센스) | 앱 안의 블로그 (/blog, Supabase posts 표) | infobay_kr 인스타·스레드 | 1단계 대상. 표 만들기: integrations/commonsense-blog/schema.sql |
| forsmartlife | 건강 | 워드프레스 | 계정 없음 | 꺼짐 (키 연결 후 켜기) |
| itinfobay | IT | 워드프레스 | 계정 없음 | 꺼짐 |
| myinfobay | 정치 (준비) | 워드프레스 | 계정 없음 | 꺼짐 |
| woodenjoy | 가구·인테리어 | 네이버 (uplika) | woodenjoy00 | 설정 준비 완료. 지금은 기존 자동화로 운영 → 사이트 설정에서 '기존 방식' 해제하면 스튜디오로 전환 |

## 로컬 시험 (개발용)
```
MOCK_LLM=1 MOCK_IMAGE=1 python3 engine/generate.py infobay      # API 없이 견본으로 전체 흐름
python3 engine/publish.py content/<id>/<폴더> threads --dry-run   # 무엇을 보낼지 출력만
ADMIN_PASSWORD=test node tools/studio_dev.js                      # 관리화면 http://localhost:3000
```
