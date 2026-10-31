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

## 처음 설정 (한 번만)
1. **GitHub 설정**: 저장소 → Settings → Actions → General → 맨 아래 *Allow GitHub Actions to create and approve pull requests* 체크 → Save
2. **비밀키** (Settings → Secrets and variables → Actions)
   - `ANTHROPIC_API_KEY` — Claude API (글쓰기)
   - `OPENAI_API_KEY` 또는 `GEMINI_API_KEY` — 대표 사진
   - 사이트별: `IG_TOKEN_INFOBAY`, `THREADS_TOKEN_INFOBAY`, `WP_FORSMARTLIFE_PASS` … (사이트 설정에 적은 이름과 같게)
3. **관리화면 토큰**: GitHub → 프로필 → Settings → Developer settings → Fine-grained tokens → 새 토큰
   - 저장소: woodenjoy-autopilot 하나 / 권한: Contents·Pull requests·Actions = Read and write
4. **Vercel**: Add New → Project → 이 저장소 → **Root Directory = `studio`** → Environment Variables
   - `ADMIN_PASSWORD` (관리화면 비밀번호), `GITHUB_TOKEN` (3번 토큰), `GITHUB_REPO` = `kim-wasp/woodenjoy-autopilot`
5. 관리화면 → **연결 가이드**에 플랫폼별 연결 방법이 있어요

## 사이트 현황
| id | 사이트 | 블로그 | SNS | 상태 |
|---|---|---|---|---|
| infobay | 상식 (커먼센스) | 없음 (앱으로 유입) | infobay_kr 인스타·스레드 | 1단계 대상 |
| forsmartlife | 건강 | 워드프레스 | 계정 없음 | 꺼짐 (키 연결 후 켜기) |
| itinfobay | IT | 워드프레스 | 계정 없음 | 꺼짐 |
| myinfobay | 정치 (준비) | 워드프레스 | 계정 없음 | 꺼짐 |
| woodenjoy | 가구·인테리어 | 네이버 | woodenjoy00 | 기존 자동화(posts/, AUTOPILOT.md)로 운영, 나중에 이전 |

## 로컬 시험 (개발용)
```
MOCK_LLM=1 MOCK_IMAGE=1 python3 engine/generate.py infobay      # API 없이 견본으로 전체 흐름
python3 engine/publish.py content/<id>/<폴더> threads --dry-run   # 무엇을 보낼지 출력만
ADMIN_PASSWORD=test node tools/studio_dev.js                      # 관리화면 http://localhost:3000
```
