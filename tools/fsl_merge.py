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
    import llm
    prompt = "\n\n".join([
        "건강 블로그의 비슷한 글 여러 개를 대표 글 하나로 합쳐요. 출력은 대표 글의 새 본문(HTML) 하나.",
        "규칙: 1) 대표 글의 구조·말투(해요체)·이미지 태그·표·링크·참고 자료는 그대로 둬요. 2) 합칠 글에서 대표 글에 없는 쓸모 있는 정보만 알맞은 소제목 아래에 녹여 넣어요(복붙 금지, 중복 빼기). "
        "3) 원문들에 없는 사실·숫자는 절대 새로 쓰지 않아요. 4) 합칠 글의 참고 자료 링크는 대표 글 참고 자료 목록에 합쳐요(중복 제거). "
        "5) 과장 표현(충격, 완벽, 필독, 폭발, 비법)과 줄표(—, –)는 쓰지 않아요. 6) 글 끝의 AI 이미지 안내 문단(class=\"ai-image-note\")은 맨 끝에 하나만.",
        f"[대표 글 제목] {target['title']['raw']}\n[대표 글 본문]\n{target['content']['raw'][:14000]}",
        *[f"[합칠 글 제목] {s['title']['raw']}\n[합칠 글 본문]\n{s['content']['raw'][:9000]}" for s in sources],
        'JSON: {"html": "새 본문 HTML", "added": "대표 글에 새로 들어간 정보 한 줄 요약"}'])
    x = llm.ask_json("당신은 건강 정보 편집자예요. JSON만 답해요.", prompt, model="claude-sonnet-5-5", max_tokens=24000)
    html = x.get("html") or ""
    nums = lambda t: set(re.findall(r"\d+(?:[.,]\d+)?", re.sub(r"<[^>]+>|https?://\S+", " ", t)))  # noqa: E731
    src_nums = nums(target["content"]["raw"]).union(*[nums(s["content"]["raw"]) for s in sources])
    new_nums = nums(html) - src_nums
    if len(html) < len(target["content"]["raw"]) * 0.8 or len(new_nums) > 3:
        raise RuntimeError(f"합친 글 점검 실패: 길이 {len(html)} / 원문에 없던 숫자 {sorted(new_nums)[:10]}")
    return html, x.get("added", "")


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
    for tslug, sslugs in (GROUPS[:1] if test else GROUPS):
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
            print("  301 시험:", redirect(srcs[0], t["link"]), check_redirect(srcs[0]["link"], t["link"]))
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
