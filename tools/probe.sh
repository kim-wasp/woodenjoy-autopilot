#!/bin/bash
# forsmartlife 사이트맵 새로고침 확인
UA="Mozilla/5.0"; H=https://forsmartlife.com
echo "== index"; curl -s -A "$UA" "$H/sitemap_index.xml?r=$RANDOM" | grep -o "<loc>[^<]*</loc>\|<lastmod>[^<]*</lastmod>"
P=$(curl -s -A "$UA" "$H/post-sitemap.xml?r=$RANDOM")
echo "== post 개수: $(echo "$P" | grep -c '<loc>')"
echo "$P" | tr -d '\n' | grep -o "<url>.*\?</url>" | sed 's#</url>#\n#g' | sed 's#.*<loc>\([^<]*\)</loc>.*<lastmod>\([^<]*\)</lastmod>.*#\2 \1#' | sort -r | head -6
echo "== 404 검사"
for u in $(echo "$P" | grep -o "<loc>[^<]*</loc>" | sed 's#</\?loc>##g'); do c=$(curl -s -o /dev/null -w "%{http_code}" -A "$UA" "$u"); [ "$c" = 200 ] || echo "$c $u"; done | head -40
echo "== 최근 공개글"; curl -s "$H/wp-json/wp/v2/posts?per_page=5&_fields=link,date" | jq -r '.[]|"\(.date) \(.link)"'
