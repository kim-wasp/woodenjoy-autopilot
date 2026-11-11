"""경험담 고치기 반영 확인: 실제 공개 페이지에서 고치기 전 문장이 사라졌는지, 1인칭 문장이 남았는지 확인."""
import json, re, html, time, requests
d = json.load(open("status/audit/rewrite-apply.json", encoding="utf-8"))
FP = re.compile(r"[^.!?\n]{0,80}(?<![가-힣])(저도|저는|제가|저희|제 경험|제 주변|내가|나도|해보니|써보니|먹어보니|겪어보니|마셔보니)[^.!?\n]{0,80}")
out = []
for x in d["report"]:
    r = requests.get(x["link"], params={"v": int(time.time())}, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    body = r.text.split("<article", 1)[-1] if "<article" in r.text else r.text
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", body)))
    old = [c["before"][:40] for c in x["changes"] if c["before"][:40] and c["before"][:40] in t]
    fp = [m.group(0).strip()[:160] for m in FP.finditer(t)]
    out.append({"id": x["id"], "status": r.status_code, "old_left": old, "fp": fp})
    print(x["id"], r.status_code, "옛 문장", len(old), "1인칭", len(fp))
json.dump(out, open("status/audit/rewrite-verify.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
