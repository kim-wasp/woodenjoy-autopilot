#!/bin/bash
# 시시비비 스레드: 비밀키에 넣은 주소(code)를 장기 토큰으로 바꿔 저장하고 권한 확인
V="$THREADS_TOKEN_SISIBIBI"; APP_ID="$THREADS_APP_ID"; APP_SECRET="$THREADS_APP_SECRET"
export GH_TOKEN="$GH_PAT"
echo "::add-mask::$V"
echo "형태: 길이 ${#V}, code= 포함 $(echo "$V" | grep -c code=)"
if echo "$V" | grep -q code=; then
  CODE="${V%%#*}"; CODE="$(echo "$CODE" | sed 's/^.*code=//; s/&.*$//')"; echo "::add-mask::$CODE"
  short=$(curl -s -X POST https://graph.threads.net/oauth/access_token -F client_id="$APP_ID" -F client_secret="$APP_SECRET" -F grant_type=authorization_code -F redirect_uri="https://example.com/" -F code="$CODE")
  st=$(echo "$short" | jq -r '.access_token // empty'); [ -n "$st" ] || { echo "1단계 실패: $(echo "$short" | jq -c 'del(.access_token)')"; exit 0; }
  echo "::add-mask::$st"
  lt=$(curl -s "https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret=$APP_SECRET&access_token=$st" | jq -r '.access_token // empty')
  [ -n "$lt" ] || { echo "2단계 실패"; exit 0; }
  echo "::add-mask::$lt"
  gh secret set THREADS_TOKEN_SISIBIBI --body "$lt" --repo "$GITHUB_REPOSITORY" && echo "교환 후 저장"
  V="$lt"
fi
echo "계정: $(curl -s "https://graph.threads.net/v1.0/me?fields=username&access_token=$V" | jq -r '.username // .error.message')"
