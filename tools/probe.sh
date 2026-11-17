#!/bin/bash
python3 tools/fsl_pages.py calculators
python3 tools/fsl_pages.py weekly --update
python3 tools/sig_backfill.py forsmartlife --apply
git config user.name studio-bot; git config user.email bot@users.noreply.github.com; git add status && git commit -qm "건강 주간 수치" && git pull -q --rebase && git push -q
python3 - <<'PY'
import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
import fsl_merge as m
s = m.by_slug("fine-dust-cleansing-routine"); t = m.by_slug("fine-dust-skin-trouble")
print("재시험", m.redirect(s, t["link"]), m.clear_cache(), m.check_redirect(s["link"], t["link"]))
PY
