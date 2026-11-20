#!/bin/bash
# 점검용 (필요할 때 바꿔 써요) — 11/23 올라갈 도어락 글에 쿠팡 링크 채워 넣기 (API 검색 1회)
set -e
D=content/woodenjoy/2026-11-20-front-door-lock-replacement-3-measurements
python3 - "$D" <<'PY'
import sys, json
sys.path.insert(0, "engine")
import generate as g
from pathlib import Path
d = Path(sys.argv[1]); post = json.loads((d/"post.json").read_text())
site = g.load_site("woodenjoy")
got = g.add_coupang_wish(site, post["coupang_wish"], d, post["title"])
md = (d/"article.md").read_text()
md = g.insert_coupang(md, got, site)
note = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
if "link.coupang.com" in md and note not in md:
    md = note + "\n\n" + md
    post["coupang"] = True
(d/"article.md").write_text(md); (d/"post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n")
print("링크 수:", md.count("link.coupang.com"), "/ 문구:", note in md)
PY
git config user.name studio-bot; git config user.email bot@users.noreply.github.com
git add "$D" topics/coupang_links.json && git commit -qm "도어락 글 쿠팡 링크 채움" && git pull -q --rebase && git push -q || true
