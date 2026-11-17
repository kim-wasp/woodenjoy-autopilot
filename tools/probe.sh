#!/bin/bash
# 1) 휴대폰 알림 주제 저장 + 시험 알림  2) 릴스 영상 처리 시험(올리지 않음)  3) 스레드 앱 번호(권한 다시 받기 주소용)
export GH_TOKEN="$GH_PAT"
T="studio-$(printf "%s" "ntfy:$THREADS_APP_SECRET" | sha256sum | cut -c1-16)"
echo "알림 주제: $T"
gh secret set NTFY_TOPIC --body "$T" --repo "$GITHUB_REPOSITORY" && echo "알림 주제 저장"
curl -s -o /tmp/n.json -w "ntfy %{http_code}\n" -X POST https://ntfy.sh/ -d '{"topic":"'"$T"'","title":"콘텐츠 스튜디오 알림 시험","message":"이 알림이 보이면 연결 완료예요","tags":["zap"],"click":"https://woodenjoy-studio.vercel.app/#/review","actions":[{"action":"view","label":"관리화면 열기","url":"https://woodenjoy-studio.vercel.app/#/review"}]}'; jq -c '{id,event,title}' /tmp/n.json
echo "앱번호: $(echo "$THREADS_APP_ID" | sed 's/./& /g')"
cd engine && python3 - <<'PY'
import os, time, requests
from pathlib import Path
import publish
from common import secret
d = Path("../content/woodenjoy/2026-11-16-wall-hole-filling-putty-1mm-two-coats").resolve()
url = publish.media_url(publish.make_reel(d))
print("영상 주소", url, requests.head(url).status_code, requests.head(url).headers.get("content-type"))
tok = secret("IG_TOKEN")
c = requests.post(f"{publish.IG}/me/media", data={"media_type": "REELS", "video_url": url, "caption": "시험(올리지 않음)", "share_to_feed": "true", "cover_url": publish.card_urls(d)[0], "access_token": tok}).json()
print("컨테이너", {k: v for k, v in c.items() if k != "access_token"})
for i in range(40):
    st = requests.get(f"{publish.IG}/{c.get('id')}", params={"fields": "status_code,status", "access_token": tok}).json()
    if st.get("status_code") in ("FINISHED", "ERROR", "EXPIRED"): break
    time.sleep(6)
print("처리 결과", st, "(게시는 안 함)")
PY
