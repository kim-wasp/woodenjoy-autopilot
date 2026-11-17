"""forsmartlife 고유 페이지 (2026-11-17)

  python3 tools/fsl_pages.py calculators   건강 계산기 페이지 만들기/고치기
  python3 tools/fsl_pages.py weekly        이번 주 감염병 수치 페이지 (질병관리청 발표를 모아 직접 그린 그래프)
  python3 tools/fsl_pages.py weekly --update   웹 검색으로 새 주 수치를 모으고 페이지 갱신 (매주 예약 실행)
"""
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "tools"))
from fsl_fix import req  # noqa: E402

KST = timezone(timedelta(hours=9))
DATA = ROOT / "status" / "fsl_weekly.json"
E = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731

STYLE = """<style>
.wn{--ink:#1f2a2e;--muted:#5b6b70;--line:#d9e2e1;--paper:#f6f9f8;--accent:#1f6b57;--warn:#9a3b2f;color:var(--ink);font-size:16px;line-height:1.7}
.wn h2{font-size:22px;margin:36px 0 10px}.wn .card{border:1px solid var(--line);border-radius:10px;background:var(--paper);padding:18px;margin:16px 0}
.wn label{display:block;font-size:14px;color:var(--muted);margin:10px 0 4px}.wn input,.wn select{width:100%;max-width:220px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:16px;background:#fff;color:var(--ink)}
.wn button{margin-top:14px;padding:9px 18px;border:0;border-radius:8px;background:var(--accent);color:#fff;font-size:15px;cursor:pointer}
.wn button:focus-visible,.wn input:focus-visible,.wn select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.wn .out{margin-top:14px;padding:12px 14px;border-radius:8px;background:#fff;border:1px solid var(--line);min-height:24px}
.wn .note{font-size:13px;color:var(--muted)}.wn table{width:100%;border-collapse:collapse;font-size:15px}.wn th,.wn td{padding:8px 10px;border-top:1px solid var(--line);text-align:left}
.wn th{font-size:13px;color:var(--muted);font-weight:600}.wn .big{font-size:28px;font-weight:700;color:var(--accent)}
</style>"""


def upsert_page(slug, title, content, desc):
    found = req("GET", f"/pages?slug={slug}&status=publish,draft,private&_fields=id").json()
    body = {"title": title, "content": content, "status": "publish", "slug": slug}
    p = req("POST", f"/pages/{found[0]['id']}" if found else "/pages", json=body).json()
    import requests
    from fsl_fix import H
    requests.post("https://forsmartlife.com/wp-json/rankmath/v1/updateMeta", headers=H, timeout=60,
                  json={"objectType": "post", "objectID": p["id"], "meta": {"rank_math_description": desc}})
    print(f"페이지 {p['link']}")
    return p


def calculators():
    c = STYLE + """
<div class="wn">
<p>숫자 몇 개만 넣으면 공식 기준과 바로 비교해 볼 수 있게 만든 계산기예요. 결과는 참고용이고 진단이 아니에요. 입력한 값은 이 화면 안에서만 계산하고 어디에도 저장하지 않아요.</p>

<h2>체질량지수(BMI)와 허리둘레</h2>
<div class="card">
<label for="h">키 (cm)</label><input id="h" type="number" inputmode="decimal" min="100" max="230" placeholder="예: 170">
<label for="w">몸무게 (kg)</label><input id="w" type="number" inputmode="decimal" min="20" max="250" placeholder="예: 68">
<label for="sx">성별 (허리둘레 기준이 달라요)</label><select id="sx"><option value="m">남성</option><option value="f">여성</option></select>
<label for="wc">허리둘레 (cm, 모르면 비워 두세요)</label><input id="wc" type="number" inputmode="decimal" min="40" max="200" placeholder="예: 86">
<button type="button" onclick="wnBmi()">계산하기</button>
<div class="out" id="bmiOut" aria-live="polite"></div>
<p class="note">기준: 대한비만학회 비만 진료지침(2022). BMI 23~24.9 비만 전단계, 25~29.9 1단계 비만, 30~34.9 2단계 비만, 35 이상 3단계 비만. 허리둘레 남성 90cm, 여성 85cm 이상이면 복부비만.</p>
</div>

<h2>올해 독감 무료 예방접종 대상일까</h2>
<div class="card">
<label for="age">만 나이</label><input id="age" type="number" inputmode="numeric" min="0" max="120" placeholder="예: 67">
<label for="mo">만 1세 미만이면 개월 수</label><input id="mo" type="number" inputmode="numeric" min="0" max="11" placeholder="예: 7">
<label for="pg">임신 중인가요</label><select id="pg"><option value="n">아니요</option><option value="y">예</option></select>
<button type="button" onclick="wnFlu()">확인하기</button>
<div class="out" id="fluOut" aria-live="polite"></div>
<p class="note">기준: 질병관리청 2026-2027절기 인플루엔자 국가예방접종(65세 이상, 생후 6개월~14세, 임신부). 어린이·임신부는 9월 21일, 65세 이상은 10월 6일부터 접종을 시작했어요. 정확한 출생일 기준과 가까운 지정 의료기관은 질병관리청 예방접종도우미(nip.kdca.go.kr)에서 확인하세요.</p>
</div>
</div>
<script>
function wnBmi(){var h=parseFloat(document.getElementById('h').value)/100,w=parseFloat(document.getElementById('w').value),wc=parseFloat(document.getElementById('wc').value),sx=document.getElementById('sx').value,o=document.getElementById('bmiOut');
if(!h||!w){o.textContent='키와 몸무게를 넣어 주세요.';return}var b=w/(h*h),g=b<18.5?'저체중':b<23?'정상':b<25?'비만 전단계':b<30?'1단계 비만':b<35?'2단계 비만':'3단계 비만';
var t='BMI '+b.toFixed(1)+' : '+g+'.';if(wc){var lim=sx==='m'?90:85;t+=' 허리둘레 '+wc+'cm는 '+(wc>=lim?'복부비만 기준('+lim+'cm 이상)에 해당해요.':'복부비만 기준('+lim+'cm) 아래예요.')}
o.textContent=t}
function wnFlu(){var a=parseInt(document.getElementById('age').value),m=parseInt(document.getElementById('mo').value),p=document.getElementById('pg').value==='y',o=document.getElementById('fluOut');
if(isNaN(a)){o.textContent='만 나이를 넣어 주세요.';return}var r=[];if(a>=65)r.push('65세 이상');if((a>=1&&a<=14)||(a===0&&m>=6))r.push('생후 6개월~14세 어린이');if(a===0&&!(m>=6))r.push('생후 6개월 전에는 접종하지 않아요');if(p)r.push('임신부');
var ok=r.filter(function(x){return x.indexOf('전에는')<0});o.textContent=ok.length?'국가예방접종 대상이에요 ('+ok.join(', ')+'). 지정 의료기관에서 접종할 수 있어요.':(r.length?r.join(' '):'국가예방접종 대상은 아니에요. 고위험군이면 의료기관에 상담해 보세요.')}
</script>"""
    content = "<!-- wp:html -->\n" + c + "\n<!-- /wp:html -->"
    upsert_page("health-calculators", "건강 계산기", content,
                "키·몸무게·허리둘레로 대한비만학회 기준 BMI 단계를 바로 계산하고, 나이로 2026-2027절기 독감 국가예방접종 대상인지 확인해요.")


def svg_chart(rows, threshold=None):
    W, Hh, L, R, T, B = 680, 260, 44, 16, 16, 34
    vals = [r["value"] for r in rows]
    import math
    top = max(5, math.ceil(max(vals + ([threshold] if threshold else [])) * 1.15 / 5) * 5)
    x = lambda i: L + (W - L - R) * (i / max(1, len(rows) - 1))  # noqa: E731
    y = lambda v: T + (Hh - T - B) * (1 - v / top)  # noqa: E731
    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
    g = "".join(f'<line x1="{L}" x2="{W - R}" y1="{y(top * k / 4):.1f}" y2="{y(top * k / 4):.1f}" stroke="#e6ecec"/>'
                f'<text x="{L - 6}" y="{y(top * k / 4) + 4:.1f}" font-size="11" text-anchor="end" fill="#5b6b70">{top * k / 4:.0f}</text>' for k in range(5))
    lab = "".join(f'<text x="{x(i):.1f}" y="{Hh - 12}" font-size="11" text-anchor="middle" fill="#5b6b70">{E(r["week"].split("-W")[-1])}주</text>'
                  for i, r in enumerate(rows) if len(rows) <= 12 or i % 2 == 0 or i == len(rows) - 1)
    th = (f'<line x1="{L}" x2="{W - R}" y1="{y(threshold):.1f}" y2="{y(threshold):.1f}" stroke="#9a3b2f" stroke-dasharray="5 4"/>'
          f'<text x="{W - R}" y="{y(threshold) - 6:.1f}" font-size="12" text-anchor="end" fill="#9a3b2f">유행기준 {threshold}</text>') if threshold else ""
    dots = "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3.5" fill="#1f6b57"/>' for i, v in enumerate(vals))
    last = f'<text x="{x(len(vals) - 1) - 6:.1f}" y="{y(vals[-1]) - 10:.1f}" font-size="13" font-weight="700" text-anchor="end" fill="#1f6b57">{vals[-1]}</text>'
    return (f'<svg viewBox="0 0 {W} {Hh}" role="img" aria-label="주별 인플루엔자 의사환자분율 그래프" style="width:100%;height:auto;display:block">'
            f'{g}{th}<polyline points="{pts}" fill="none" stroke="#1f6b57" stroke-width="2.5"/>{dots}{last}{lab}</svg>')


def update():
    """질병관리청 발표(보도자료·표본감시 주간소식지)에서 주별 수치를 모아요. 출처가 열리는 것만 저장"""
    import llm
    import sources
    d = json.loads(DATA.read_text()) if DATA.exists() else {"ili": {}, "threshold": None, "season": "2026-2027"}
    x = llm.ask_json("당신은 보건 통계 자료를 정확히 옮기는 조사원이에요. JSON만 답해요.",
                     "웹 검색으로 질병관리청이 발표한 2026-2027절기 인플루엔자 의사환자분율(외래환자 1,000명당)을 주차별로 모아 주세요. "
                     "2026년 36주부터 가장 최근 발표 주까지, 확인되는 주만. 질병관리청 보도자료(kdca.go.kr)나 감염병 표본감시 주간소식지에 나온 숫자만, 기사 숫자는 질병관리청 발표를 인용한 것만. "
                     "이번 절기 유행기준(1,000명당 몇 명)도. 이미 아는 값: " + json.dumps(d["ili"], ensure_ascii=False)[:1500] +
                     '\nJSON: {"weeks": [{"week": "2026-W44", "period": "10.25~10.31", "value": 22.8, "source": "https://..."}], "threshold": 9.1, "threshold_source": "https://..."}',
                     model="claude-sonnet-5-5", web_search=True, max_searches=6, max_tokens=4000)
    for w in x.get("weeks") or []:
        if not re.fullmatch(r"\d{4}-W\d{2}", str(w.get("week"))) or not isinstance(w.get("value"), (int, float)):
            continue
        if w["week"] in d["ili"]:
            continue
        if w.get("source") and sources.alive(w["source"]):
            d["ili"][w["week"]] = {k: w.get(k) for k in ("period", "value", "source")}
    if x.get("threshold") and x.get("threshold_source") and sources.alive(x["threshold_source"]):
        d["threshold"], d["threshold_source"] = x["threshold"], x["threshold_source"]
    d["updated"] = datetime.now(KST).isoformat(timespec="minutes")
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(d, ensure_ascii=False, indent=1))
    print(f"주차 {len(d['ili'])}개, 유행기준 {d.get('threshold')}")
    return d


def weekly():
    d = update() if "--update" in sys.argv else json.loads(DATA.read_text())
    rows = [{"week": k, **v} for k, v in sorted(d["ili"].items())]
    if len(rows) < 2:
        print("주차가 2개보다 적어서 페이지를 만들지 않아요")
        return
    last, prev = rows[-1], rows[-2]
    diff = round(last["value"] - prev["value"], 1)
    move = f"전주({prev['value']}명)보다 {abs(diff)}명 {'늘었어요' if diff > 0 else '줄었어요' if diff < 0 else '같아요'}"
    th = d.get("threshold")
    vs = f" 이번 절기 유행기준({th}명)의 {last['value'] / th:.1f}배예요." if th else ""
    table = "".join(f'<tr><td>{E(r["week"].split("-W")[1])}주{" (" + E(r["period"]) + ")" if r.get("period") else ""}</td><td>{E(r["value"])}명</td><td><a href="{E(r["source"])}" target="_blank" rel="noopener">출처</a></td></tr>' for r in reversed(rows[-10:]))
    srcs = sorted({r["source"] for r in rows} | ({d["threshold_source"]} if d.get("threshold_source") else set()))
    c = STYLE + f"""
<div class="wn">
<p>질병관리청이 매주 발표하는 독감(인플루엔자) 수치를 모아 WellnessNote가 직접 그린 그래프예요. 숫자는 질병관리청 발표 그대로이고, 매주 새 발표가 나오면 고쳐요.</p>
<div class="card">
<p style="margin:0" class="note">{E(last['week'].split('-W')[0])}년 {E(last['week'].split('-W')[1])}주{(" (" + E(last["period"]) + ")") if last.get("period") else ""} 인플루엔자 의사환자분율</p>
<p style="margin:4px 0 0"><span class="big">{E(last['value'])}명</span> <span class="note">외래환자 1,000명당</span></p>
<p style="margin:6px 0 0">{move}.{vs}</p>
</div>
<h2>주별 흐름</h2>
<div class="card" style="background:#fff">{svg_chart(rows[-16:], th)}</div>
<h2>최근 10주 수치</h2>
<table><thead><tr><th>주차</th><th>1,000명당</th><th>근거</th></tr></thead><tbody>{table}</tbody></table>
<h2>이 숫자를 볼 때</h2>
<p>의사환자분율은 표본 의료기관을 찾은 외래환자 1,000명 가운데 38℃ 이상 발열과 기침 또는 인후통이 있는 사람 수예요. 실제 확진자 수가 아니라 유행 흐름을 보는 지표라서, 오르내림을 보는 데 쓰는 게 맞아요.</p>
<p>무료 예방접종 대상인지는 <a href="/health-calculators/">건강 계산기</a>에서 바로 확인할 수 있어요.</p>
<h2>출처</h2>
<ul>{''.join(f'<li><a href="{E(u)}" target="_blank" rel="noopener">{E(u)}</a></li>' for u in srcs)}</ul>
<p class="note">마지막 갱신: {E(d.get('updated', '')[:10])}</p>
</div>"""
    upsert_page("flu-weekly", "이번 주 독감 수치", "<!-- wp:html -->\n" + c + "\n<!-- /wp:html -->",
                f"질병관리청이 발표한 인플루엔자 의사환자분율을 주별로 모아 그린 그래프. 최근 {last['week'].split('-W')[1]}주 {last['value']}명(1,000명당).")


HOME_STYLE = """<style>
.wnh{--ink:#1f2a2e;--muted:#5b6b70;--line:#d9e2e1;--paper:#f6f9f8;--accent:#1f6b57;--accent-ink:#ffffff;--myth:#9a3b2f;
--font:inherit;color:var(--ink);font-size:17px;line-height:1.7;overflow-wrap:break-word}
.wnh *{box-sizing:border-box}.wnh h1,.wnh h2,.wnh h3{min-width:0;overflow-wrap:break-word;color:var(--ink)}
.wnh .hero{padding:48px 0 40px;border-bottom:1px solid var(--line)}
.wnh .hero h1{font-size:clamp(30px,4.2vw,46px);line-height:1.25;margin:0 0 14px;font-weight:700;letter-spacing:-0.01em}
.wnh .hero p{margin:0 0 22px;color:var(--muted);font-size:18px;max-width:34em}
.wnh .act{display:flex;flex-wrap:wrap;gap:12px}
.wnh .btn{display:inline-block;padding:11px 20px;border-radius:8px;background:var(--accent);color:var(--accent-ink);text-decoration:none;font-weight:600}
.wnh .btn.ghost{background:transparent;color:var(--accent);border:1px solid var(--accent)}
.wnh a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.wnh .myth{margin:40px 0 8px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.wnh .myth div{padding:18px 20px}.wnh .myth .m{background:var(--paper);color:var(--myth)}.wnh .myth .f{background:#fff}
.wnh .myth small{display:block;font-size:13px;color:var(--muted);margin-bottom:6px}
.wnh .cap{font-size:14px;color:var(--muted);margin:0 0 40px}
.wnh h2{font-size:24px;margin:44px 0 14px}
.wnh .tri{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:0;padding:0;list-style:none}
.wnh .tri li{border-top:2px solid var(--ink);padding-top:12px}.wnh .tri a{color:var(--ink);font-weight:700;text-decoration:none}
.wnh .tri p{margin:6px 0 0;font-size:15px;color:var(--muted)}
.wnh .wp-block-latest-posts{list-style:none;padding:0;margin:0}.wnh .wp-block-latest-posts li{padding:14px 0;border-top:1px solid var(--line)}
.wnh .wp-block-latest-posts a{color:var(--ink);font-weight:600;text-decoration:none}.wnh .wp-block-latest-posts__post-date{display:block;font-size:13px;color:var(--muted)}
.wnh .wp-block-latest-posts__post-excerpt{margin:4px 0 0;font-size:15px;color:var(--muted)}
@media (max-width:640px){.wnh .myth,.wnh .tri{grid-template-columns:minmax(0,1fr)}.wnh .hero{padding:32px 0 28px}}
</style>"""


def home():
    c = HOME_STYLE + """
<div class="wnh">
<section class="hero">
<h1>건강 속설, 공식 기준으로 다시 봐요</h1>
<p>흔히 듣는 말 옆에 질병관리청·학회 기준을 나란히 놓고, 출처를 글마다 남겨요.</p>
<div class="act"><a class="btn" href="/flu-weekly/">이번 주 독감 수치</a><a class="btn ghost" href="/health-calculators/">건강 계산기</a></div>
</section>
<div class="myth"><div class="m"><small>흔히 듣는 말</small>물은 누구나 하루 2리터</div><div class="f"><small>공식 기준</small>필요한 양은 나이·성별·활동량마다 달라요. 음식으로 먹는 물도 포함해서 봐요.</div></div>
<p class="cap">모든 글은 이렇게 시작해요. <a href="/daily-water-intake/">이 예시 글 읽기</a></p>
<h2>새 글</h2>
<!-- wp:latest-posts {"postsToShow":6,"displayPostDate":true,"displayPostContent":true,"excerptLength":28} /-->
<h2>주제별로 보기</h2>
<ul class="tri">
<li><a href="/category/season-health-tips/">계절 건강</a><p>환절기·한파·폭염에 달라지는 몸 관리</p></li>
<li><a href="/category/health-routine/">건강 루틴</a><p>먹고 자고 움직이는 매일의 기준</p></li>
<li><a href="/category/symptom-management/">증상 관리</a><p>병원에 가야 할 신호와 집에서 할 일</p></li>
</ul>
<h2>이렇게 써요</h2>
<ul class="tri">
<li><a href="/editorial-policy/">공식 자료만</a><p>질병관리청, 학회, 대학병원 자료로 확인한 내용만 써요.</p></li>
<li><a href="/medical-disclaimer/">진단은 병원에서</a><p>글은 참고 정보예요. 증상이 있으면 진료를 먼저 받으세요.</p></li>
<li><a href="/contact/">틀리면 고쳐요</a><p>오류를 알려 주시면 확인하고 고친 날짜를 남겨요.</p></li>
</ul>
</div>"""
    found = req("GET", "/pages?slug=%ed%99%88&_fields=id,content&context=edit").json()
    if not found:
        print("홈 페이지를 못 찾았어요")
        return
    import shutil  # noqa: F401
    old = found[0]["content"]["raw"]
    bk = ROOT / "status" / "fsl_home_backup.html"
    if not bk.exists():
        bk.write_text(old, encoding="utf-8")  # 되돌릴 수 있게 처음 것 보관
    req("POST", f"/pages/{found[0]['id']}", json={"content": "<!-- wp:html -->\n" + c.split("<!-- wp:latest-posts")[0] + "\n<!-- /wp:html -->\n"
        + "<!-- wp:latest-posts" + c.split("<!-- wp:latest-posts")[1].split("/-->")[0] + "/-->\n<!-- wp:html -->\n" + c.split("/-->", 1)[1] + "\n<!-- /wp:html -->"})
    print("홈 페이지 고침")


if __name__ == "__main__":
    {"calculators": calculators, "weekly": weekly, "home": home}[sys.argv[1]]()
