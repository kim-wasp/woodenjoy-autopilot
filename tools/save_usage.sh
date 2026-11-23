#!/bin/bash
# 이번 실행의 사용량 기록(usage/*.json, 아직 안 올린 것)을 main 에 올리고 요약을 다시 만들어요.
# 각 워크플로 맨 마지막 단계에서 실행 (if: always()). 실패해도 워크플로는 실패로 안 바꿔요.
set +e
new=$(git ls-files --others --exclude-standard usage/ 2>/dev/null)
[ -z "$new" ] && { echo "사용량 기록 없음"; exit 0; }
rm -rf /tmp/usage_new && mkdir -p /tmp/usage_new
for f in $new; do mkdir -p "/tmp/usage_new/$(dirname "$f")"; cp "$f" "/tmp/usage_new/$f"; done
git config user.name studio-bot; git config user.email bot@users.noreply.github.com
for i in 1 2 3 4 5; do
  git fetch -q origin main && git checkout -q -f -B usage-save origin/main
  cp -r /tmp/usage_new/usage . 2>/dev/null
  python3 tools/usage_report.py
  git add usage status/usage_summary.json
  git commit -qm "사용량 기록 ($(echo "$new" | wc -l)건)" || exit 0
  git push -q origin HEAD:main && { echo "사용량 기록 저장"; exit 0; }
  sleep $((i * 4))
done
echo "::warning::사용량 기록 저장 실패"
exit 0
