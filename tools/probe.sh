#!/bin/bash
A="gracelyun28:$WP_FORSMARTLIFE_PASS"; B=https://forsmartlife.com/wp-json/rankmath/v1
curl -s -u "$A" -X POST -H "Content-Type: application/json" -d '{"action":"recreate_tables"}' $B/toolsAction | head -c 300; echo
curl -s -u "$A" -X POST -H "Content-Type: application/json" -d '{"module":"redirections","state":"on"}' $B/saveModule; echo
python3 - <<'PY'
import sys; sys.path.insert(0,'tools'); sys.path.insert(0,'engine')
import fsl_merge as m
s = m.by_slug("fine-dust-cleansing-routine"); t = m.by_slug("fine-dust-skin-trouble")
print(s["status"], s["link"])
print(m.redirect(s, t["link"]), m.clear_cache(), m.check_redirect(s["link"], t["link"]))
PY
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" "https://forsmartlife.com/fine-dust-cleansing-routine/"
