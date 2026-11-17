#!/bin/bash
# forsmartlife 애드센스 점검
H=forsmartlife.com; UA="Mozilla/5.0 (compatible; Mediapartners-Google)"
echo "== ads.txt 변형별"
for u in https://$H/ads.txt http://$H/ads.txt https://www.$H/ads.txt http://www.$H/ads.txt; do
  curl -s -o /tmp/a.txt -A "$UA" -L -w "$u → %{http_code} %{content_type} 최종:%{url_effective} 리다이렉트:%{num_redirects}\n" "$u"; head -c 300 /tmp/a.txt | tr '\n' '|'; echo
done
curl -sI -A "$UA" https://$H/ads.txt | head -15
echo "== 구글봇 UA"; curl -s -o /dev/null -w "%{http_code}\n" -A "Googlebot/2.1" https://$H/ads.txt
echo "== DNS"; dig +short $H A; dig +short www.$H; dig +short $H AAAA
echo "== 홈 광고 코드"; curl -s -A "Mozilla/5.0" https://$H/ > /tmp/home.html; grep -o 'ca-pub-[0-9]*' /tmp/home.html | sort | uniq -c; grep -o 'pagead2[^"]*' /tmp/home.html | head -3; grep -io '<meta name="google-adsense-account"[^>]*>' /tmp/home.html
echo "== robots"; curl -s https://$H/robots.txt | head -20
python3 tools/site_audit.py $H > /tmp/audit.txt 2>&1; head -c 6000 /tmp/audit.txt
echo "== WP 글 상태"; A="gracelyun28:$WP"
for st in publish private draft pending future; do n=$(curl -s -u "$A" -I "https://$H/wp-json/wp/v2/posts?status=$st&per_page=1" | grep -i x-wp-total | tr -d '\r'); echo "$st $n"; done
curl -s -u "$A" "https://$H/wp-json/wp/v2/pages?status=publish,private,draft&per_page=50&_fields=id,status,slug,title,link" | jq -r '.[]|"\(.status) \(.slug) \(.title.rendered) \(.link)"'
curl -s -u "$A" "https://$H/wp-json/wp/v2/plugins?_fields=plugin,status,name" | jq -r '.[]?|"\(.status) \(.name)"' | head -40
curl -s -u "$A" "https://$H/wp-json/wp/v2/categories?per_page=50&_fields=name,count,slug" | jq -r '.[]|"\(.count) \(.slug) \(.name)"'
curl -s -u "$A" "https://$H/wp-json/wp/v2/posts?status=publish&per_page=100&_fields=id,date,slug,title,categories,lang" | jq -r '.[]|"\(.date[0:10]) \(.id) \(.lang // "") \(.slug) \(.title.rendered)"' | head -120
curl -s -u "$A" "https://$H/wp-json/wp/v2/users/me?context=edit&_fields=name,slug,description,link" | jq -c .
