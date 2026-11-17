#!/bin/bash
# 속보 감지 한 바퀴: 이슈 찾기 → 글 만들기 → 승인 대기(PR) → 휴대폰 알림 → 기록 저장
git fetch -q origin main && git checkout -q -f main && git reset -q --hard origin/main
python3 engine/issue.py watch $SITE 2>&1 | tee issue.log
cp status/issue_seen.json /tmp/issue_seen.json 2>/dev/null || true
for dir in $(grep '::issue-dir::' issue.log | sed 's/.*::issue-dir:://'); do
  site=$(echo "$dir" | cut -d/ -f2); title=$(jq -r .title "$dir/post.json")
  branch="studio/${dir#content/}"
  git checkout -q -b "$branch" origin/main
  git add "$dir" && git commit -qm "속보 준비: $title" && git push -q -u origin "$branch"
  ok=$(jq -r '.checks.ok' "$dir/post.json")
  prefix=$([ "$ok" = true ] && echo "[승인 대기]" || echo "[점검 실패]")
  url=$(gh pr create --base main --head "$branch" --title "$prefix [$site] $title" --body "속보 글이에요. 승인하면 바로 스레드에 올라가요.

폴더: $dir")
  n=$(echo "$url" | grep -o '[0-9]*$')
  python3 engine/issue.py notify "$dir" "$n" || true
  git checkout -q -f main
done
for i in 1 2 3; do
  git fetch -q origin main && git checkout -q -f main && git reset -q --hard origin/main
  cp /tmp/issue_seen.json status/issue_seen.json 2>/dev/null || true
  git add status/issue_seen.json && git commit -qm "속보 감지 기록" && git push -q origin HEAD:main && break
  sleep 5
done
