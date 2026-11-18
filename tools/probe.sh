#!/bin/bash
pip install -q cryptography >/dev/null 2>&1
python3 tools/sec_scan.py > /dev/null 2>&1; echo "점검 종료 $?"
mkdir -p status/audit && python3 tools/seal.py /tmp/sec_scan.json status/audit/sec_scan.enc && rm -f /tmp/sec_scan.json
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status/audit/sec_scan.enc && git commit -qm "보안 점검 결과(잠금)" && git pull -q --rebase && git push -q
