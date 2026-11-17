#!/bin/bash
for s in daily-water-intake flu-isolation-return-work migraine-aura-before-headache-changes spring-immunity-symptoms; do
 echo "== $s"; curl -s -A "Mozilla/5.0" "https://forsmartlife.com/$s/?v=$RANDOM" | python3 -c "
import sys,re
from bs4 import BeautifulSoup
s=BeautifulSoup(sys.stdin.read(),'html.parser')
print(s.title.get_text())
h=[x for x in s.find_all('h2') if '참고 자료' in x.get_text()]
if h:
  for a in h[0].find_next('ul').find_all('a'): print(' ', a.get_text()[:60], a['href'][:90])
n=s.find(class_='ai-image-note'); print(' AI안내:', bool(n)); print(' 별표 남음:', '**' in s.get_text())"
done
curl -s "https://forsmartlife.com/contact/?v=$RANDOM" | grep -o "오류 제보[^<]*" | head -2
