#!/bin/bash
A="gracelyun28:$WP_FORSMARTLIFE_PASS"
curl -s -u "$A" https://forsmartlife.com/wp-json/ | python3 -c "
import json,sys; j=json.load(sys.stdin); print(j.get('namespaces'))
print([r for r in j['routes'] if 'redirect' in r.lower() or 'rankmath' in r.lower()][:60])"
curl -s -u "$A" "https://forsmartlife.com/wp-json/wp/v2/posts/942?context=edit&_fields=meta" | head -c 600; echo
curl -s -u "$A" "https://forsmartlife.com/wp-json/wp/v2/users/me?context=edit&_fields=roles,capabilities" | python3 -c "import json,sys;j=json.load(sys.stdin);print(j.get('roles'), j.get('capabilities',{}).get('unfiltered_html'))"
curl -s -A Mozilla/5.0 "https://forsmartlife.com/tomato-health-benefits-eating-tips/?x=$RANDOM" | grep -o "<title>[^<]*</title>"
