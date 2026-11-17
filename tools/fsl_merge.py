"""forsmartlife 겹치는 글 합치기 (2026-11-17, 사장님 승인)

  python3 tools/fsl_merge.py redirect-test     첫 묶음으로 301 이동만 시험
  python3 tools/fsl_merge.py --apply           전부 합치기

묶음마다: 대표 글에 합친 글의 '대표 글에 없는 정보'만 녹여 넣기(Claude) → 합친 글 주소를 대표 글로 301 (Rank Math)
→ 합친 글은 비공개(되돌릴 수 있음) → 다른 글 안의 링크를 대표 글 주소로 바꾸기. 기록: status/audit/fsl_merge.json
"""
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "tools"))
from fsl_fix import BASE, H, req  # noqa: E402

SITE = "https://forsmartlife.com"
GROUPS = [
    ("fine-dust-skin-trouble", ["fine-dust-cleansing-routine"]),
    ("fine-dust-detox-routine", ["fine-dust-scalp-care"]),
    ("fine-dust-ventilation-air-purifier-tips", ["fine-dust-wash-ventilation-timing"]),
    ("sleep-debt-dementia-brain-glymphatic", ["deep-sleep-brain-cleaning-dementia-prevention"]),
    ("sleep-quality-habits", ["melatonin-evening-habit"]),
    ("spring-allergy-prevention", ["spring-allergy-immunity", "pollen-allergy-symptoms-care"]),
    ("health-checkup-preparation", ["spring-health-checklist"]),
    ("seasonal-health-warning-signs", ["spring-risk-diseases"]),
    ("allergy-medicine-no-drowsiness-guide-2026", ["antihistamine-no-tolerance-correct-dosage-guide"]),
    ("dry-eye-care-routine", ["meibomian-gland-cleaning"]),
    ("spring-conjunctivitis-symptoms", ["cherry-blossom-eye-care-conjunctivitis"]),
    ("slow-aging-lifestyle-habits", ["slow-aging-diet-principles-look-younger"]),
    ("diabetes-early-symptoms", ["diabetes-symptoms-thirst-urination"]),
    ("blood-sugar-spike-meal-order-guide", ["postmeal-drowsiness-blood-sugar-spike-prediabetes"]),
    ("daily-water-intake", ["summer-dehydration-prevention"]),
    ("seasonal-cough-care", ["seasonal-sore-throat-care"]),
    ("nasal-congestion-home-care", ["dry-nasal-mucosa-care"]),
    ("norovirus-symptoms-prevention-disinfection", ["norovirus-dishes-family-habits"]),
    ("heat-illness-heatstroke-symptoms-treatment", ["early-summer-health-tips"]),
    ("daily-protein-intake-calculator-by-age-weight", ["high-protein-foods-sarcopenia-prevention-4050"]),
]
LOG = ROOT / "status/audit/fsl_merge.json"


def by_slug(slug, status="publish,private"):
    r = req("GET", f"/posts?slug={slug}&status={status}&context=edit&_fields=id,slug,status,title,content,link")
    j = r.json()
    return j[0] if j else None


def clear_cache():
    r = requests.post(f"{SITE}/wp-json/wp-super-cache/v1/cache", headers=H, json={"wp_delete_cache": True}, timeout=60)
    return r.status_code


def check_redirect(src_link, to_url):
    chk = requests.get(src_link, allow_redirects=False, timeout=30, headers={"User-Agent": "Mozilla/5.0", "Cache-Control": "no-cache"})
    loc = chk.headers.get("location", "")
    return chk.status_code in (301, 308) and to_url.rstrip("/") in loc.rstrip("/"), f"{chk.status_code} {loc}"


def redirect(src_post, to_url):
    """Rank Math 301 만들기 (모듈 켜져 있어야 해요)"""
    r = requests.post(f"{SITE}/wp-json/rankmath/v1/updateRedirection", headers=H, timeout=60, json={
        "objectID": src_post["id"], "objectType": "post", "hasRedirect": True, "redirectionID": "", "redirectionUrl": to_url, "redirectionType": "301"})
    ok = r.status_code == 200 and '"new"' in r.text or "update" in r.text
    print(f"  이동 설정 {r.status_code} {json.loads(r.text).get('message', '')[:40] if r.text.startswith('{') else r.text[:80]}")
    return ok


def merge_text(target, sources):
    """대표 글 본문은 한 글자도 다시 쓰지 않고, 빠진 정보만 소제목 아래에 끼워 넣어요"""
    import llm
    tr = target["content"]["raw"]
    heads = re.findall(r"<h[23][^>]*>(.*?)</h[23]>", tr)
    prompt = "\n\n".join([
        "건강 블로그의 비슷한 글을 대표 글 하나로 합쳐요. 대표 글은 그대로 두고, 합칠 글에만 있는 쓸모 있는 정보를 끼워 넣을 조각으로 주세요.",
        "규칙: 1) 대표 글에 이미 있는 내용은 빼요. 2) 원문들에 없는 사실·숫자는 절대 새로 쓰지 않아요. 3) 해요체, 과장 표현(충격, 완벽, 필독, 폭발, 비법)과 줄표(—, –) 금지. "
        "4) 조각은 워드프레스 블록 HTML(<!-- wp:paragraph --><p>…</p><!-- /wp:paragraph -->, 목록은 wp:list)로. 조각마다 2~6문장 또는 목록. 새 소제목이 필요하면 <!-- wp:heading --><h2>…</h2><!-- /wp:heading --> 포함. "
        "5) after 는 아래 대표 글 소제목 중 하나를 그대로(그 소제목 섹션 끝에 들어가요). 6) 합칠 글의 참고 자료 링크 중 대표 글에 없는 것은 links 에.",
        "[대표 글 소제목]\n" + "\n".join(f"- {re.sub(r'<[^>]+>', '', h)}" for h in heads),
        f"[대표 글 제목] {target['title']['raw']}\n[대표 글 본문]\n{re.sub(r'<!--.*?-->', '', tr)[:30000]}",
        *[f"[합칠 글 제목] {s['title']['raw']}\n[합칠 글 본문]\n{re.sub(r'<!--.*?-->', '', s['content']['raw'])[:15000]}" for s in sources],
        'JSON: {"inserts": [{"after": "대표 글 소제목 그대로", "html": "끼워 넣을 HTML"}], "links": [{"title": "기관명, 자료 제목", "url": "https://..."}], "added": "새로 들어간 정보 한 줄 요약"}'])
    x = llm.ask_json("당신은 건강 정보 편집자예요. JSON만 답해요.", prompt, model="claude-sonnet-5-5", max_tokens=8000)
    nums = lambda t: set(re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"<[^>]+>|https?://\S+", " ", t)))  # noqa: E731
    src_nums = nums(tr).union(*[nums(s["content"]["raw"]) for s in sources])
    plain_heads = [(m, re.sub(r"<[^>]+>", "", m.group(1)).strip()) for m in re.finditer(r"<h[23][^>]*>(.*?)</h[23]>", tr)]
    ref = tr.find("참고 자료</h2>")
    tail = tr.rfind("<!-- wp:heading", 0, ref) if ref > 0 else (tr.find('<p class="ai-image-note"') if 'ai-image-note' in tr else len(tr))
    tail = tail if tail > 0 else len(tr)
    spots = []
    for ins in x.get("inserts") or []:
        frag = ins.get("html") or ""
        if not frag or nums(frag) - src_nums or "—" in frag or "–" in frag:
            print(f"  조각 버림(새 숫자·줄표): {frag[:60]}")
            continue
        hit = [i for i, (m, h) in enumerate(plain_heads) if h == (ins.get("after") or "").strip()]
        if not hit:
            continue
        i = hit[0]
        if i + 1 < len(plain_heads):
            pos = tr.rfind("<!-- wp:heading", plain_heads[i][0].end(), plain_heads[i + 1][0].start())
            pos = pos if pos > 0 else plain_heads[i + 1][0].start()
        else:
            pos = tail
        pos = min(pos, tail) if pos > plain_heads[i][0].end() else tail
        spots.append((pos, frag))
    html, last = "", 0
    for pos, frag in sorted(spots, key=lambda z: z[0]):
        html += tr[last:pos].rstrip() + "\n\n" + frag + "\n\n"
        last = pos
    html += tr[last:]
    done = len(spots)
    import sources as srcmod
    links = [l for l in (x.get("links") or []) if l.get("url") and l["url"] not in html and srcmod.alive(l["url"])]
    if links:
        li = "".join(f'<li><a href="{l["url"]}" target="_blank" rel="noopener">{l["title"]}</a></li>' for l in links)
        if "참고 자료</h2>" in html and "</ul>" in html[html.index("참고 자료</h2>"):]:
            k = html.index("</ul>", html.index("참고 자료</h2>"))
            html = html[:k] + li + html[k:]
    if done == 0 and not links:
        raise RuntimeError("끼워 넣을 정보가 없어요")
    return html, f"조각 {done}개, 링크 {len(links)}개: " + (x.get("added") or "")


def relink(old_new):
    page = 1
    while True:
        r = req("GET", f"/posts?status=publish&per_page=20&page={page}&context=edit&_fields=id,content")
        for p in r.json():
            raw = new = p["content"]["raw"]
            for old, to in old_new.items():
                new = re.sub(rf'https?://forsmartlife\.com/{re.escape(old)}/?(?=["#?])', to, new)
            if new != raw:
                req("POST", f"/posts/{p['id']}", json={"content": new})
                print(f"  링크 교체: 글 {p['id']}")
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            return
        page += 1


def main():
    log = json.loads(LOG.read_text()) if LOG.exists() else {}
    test = "redirect-test" in sys.argv
    moved = {}
    for tslug, sslugs in (GROUPS[:1] if (test or "--first" in sys.argv) else GROUPS):
        if tslug in log and log[tslug].get("done"):
            moved.update({s: log[tslug]["to"] for s in sslugs})
            continue
        t = by_slug(tslug)
        srcs = [by_slug(s) for s in sslugs]
        if not t or not all(srcs):
            print(f"건너뜀 {tslug}: 글을 못 찾음")
            continue
        print(f"[{t['title']['raw']}] ← {', '.join(s['title']['raw'] for s in srcs)}")
        if test:
            print("  301 시험:", redirect(srcs[0], t["link"]), "캐시", clear_cache(), check_redirect(srcs[0]["link"], t["link"]))
            return
        try:
            html, added = merge_text(t, srcs)
        except Exception as e:  # noqa: BLE001
            print(f"  합치기 건너뜀: {e}")
            continue
        req("POST", f"/posts/{t['id']}", json={"content": html})
        ok = all(redirect(s, t["link"]) for s in srcs)
        for s in srcs:
            req("POST", f"/posts/{s['id']}", json={"status": "private"})
            moved[s["slug"]] = t["link"]
        clear_cache()
        checks = [check_redirect(s["link"], t["link"]) for s in srcs]
        ok = ok and all(c[0] for c in checks)
        print("  이동 확인:", [c[1] for c in checks])
        log[tslug] = {"to": t["link"], "merged": sslugs, "added": added, "redirect_ok": ok, "done": True}
        LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1))
        print(f"  완료 (301 {'정상' if ok else '확인 필요'}): {added}")
    if moved and not test:
        relink(moved)
    print(f"합친 묶음 {sum(1 for v in log.values() if v.get('done'))} / 이동 확인 실패 {[k for k, v in log.items() if not v.get('redirect_ok')]}")


if __name__ == "__main__":
    main()
