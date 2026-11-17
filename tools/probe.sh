#!/bin/bash
python3 - <<'PY'
import sys
sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
from fsl_fix import req
raw = req("GET", "/posts/97/revisions/1600?context=edit&_fields=content").json()["content"]["raw"]
print("되돌림", len(raw)); req("POST", "/posts/97", json={"content": raw})
PY
python3 tools/fsl_merge.py --apply
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status/audit && git commit -qm merge-log && git pull -q --rebase && git push -q
