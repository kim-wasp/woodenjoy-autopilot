#!/bin/bash
python3 tools/site_audit.py forsmartlife.com > /dev/null 2>&1
mkdir -p status/audit/fsl
for s in tomato-health-benefits-eating-tips sugar-substitute-sweetener-truth spring-immunity-symptoms daily-water-intake wegovy-muscle-loss-prevention; do
  curl -s -A "Mozilla/5.0" "https://forsmartlife.com/$s/" | python3 -c "
import sys,re
from bs4 import BeautifulSoup
s=BeautifulSoup(sys.stdin.read(),'html.parser')
for t in s(['script','style','noscript']): t.decompose()
m=s.find('article') or s.body
print(re.sub(r'\n\s*\n+','\n',m.get_text('\n'))[:5000])" > status/audit/fsl/$s.txt
done
git config user.name studio-bot; git config user.email bot@users.noreply.github.com
git add status/audit && git commit -qm "audit" && git pull -q --rebase && git push -q && echo 저장
