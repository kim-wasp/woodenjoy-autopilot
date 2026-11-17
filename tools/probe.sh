#!/bin/bash
python3 tools/fsl_merge.py --apply --first
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status/audit && git commit -qm merge-log && git pull -q --rebase && git push -q
