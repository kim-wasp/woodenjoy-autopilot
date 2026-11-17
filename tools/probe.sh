#!/bin/bash
# 스레드/인스타 성과 모으기
python3 tools/social_stats.py
git config user.name studio-bot; git config user.email bot@users.noreply.github.com
git add status/social_stats.json && git commit -qm "social stats" && git pull -q --rebase && git push -q && echo 저장
