#!/bin/bash
python3 tools/sec_scan.py
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status/audit && git commit -qm "보안 점검 결과" && git pull -q --rebase && git push -q
