"""사이트마다 '이 사이트다운' 고정 형식 (개성 만들기, 2026-11-17)

- forsmartlife: 흔한 말 vs 공식 기준 대조표 (myth_check)
- sisibibi: 쟁점 판정표 (verdict) + 법안 진행 단계 (bill)
글 본문(마크다운) 첫 문단 뒤에 HTML 블록으로 넣어요. 스타일은 블록 안에 같이 들어가서 어느 블로그 틀에서도 똑같이 보여요.
site.json: "signature": "myth_check" | "verdict"
"""
import html
import re

E = lambda s: html.escape(str(s or ""), quote=True)  # noqa: E731

# 색은 사이트 기본 글자색·배경과 어울리는 차분한 두 가지만 (토큰처럼 한 곳에서)
TOK = {
    "ink": "#1f2a2e", "muted": "#5b6b70", "line": "#d9e2e1", "paper": "#f6f9f8",
    "myth": "#9a3b2f", "fact": "#1f6b57",
    "s_true": "#1f6b57", "s_part": "#8a6a12", "s_open": "#5b6b70", "s_false": "#9a3b2f", "s_opinion": "#3d5a8a",
}

SCHEMA = {
    "myth_check": '"myth_check": [{"myth": "사람들이 실제로 하는 말(따옴표 없이, 25자 안팎)", "fact": "공식 기준·근거 한 줄(숫자 포함, 50자 안팎)", "source": "기관명 자료명(sources 에 있는 것만)"}] 2~4개. '
                  '이 글의 핵심 오해를 고르고, 근거는 반드시 sources 에 넣은 공식 자료에서. "본문", "이 글" 같은 말 금지',
    "verdict": '"verdict": {"issue": "이 글의 쟁점 한 줄(질문형)", "rows": [{"who": "누가(정당·기관·단체 이름)", "claim": "그쪽 주장 한 줄", "check": "확인된 사실 한 줄(근거)", '
               '"status": "사실|일부 사실|확인 중|사실 아님|의견"}] 3~5개(양쪽 진영 주장을 균형 있게, 같은 수로), "unknown": "아직 확인 안 된 것 한 줄"}. '
               '판정은 sources 의 공식 자료·보도로 확인한 것만, 가치 판단은 status "의견". 독자에게 보이는 문장이라 "본문", "글에서", "이 글" 같은 말은 쓰지 말고 근거(기관·보도)를 직접',
    "bill": '"bill": 이 글이 특정 법안을 다루면 {"name": "법안 이름", "number": "의안번호(확인되면)", "stage": "발의|위원회 심사|법사위|본회의 통과|정부 이송|공포|폐기", '
            '"as_of": "YYYY-MM-DD", "url": "의안정보시스템(likms.assembly.go.kr) 해당 의안 주소(확인되면)"} 아니면 null. 웹 검색으로 지금 단계를 확인한 것만',
}
STAGES = ["발의", "위원회 심사", "법사위", "본회의 통과", "정부 이송", "공포"]


def schema_parts(site):
    sig = site.get("signature")
    if sig == "myth_check":
        return [SCHEMA["myth_check"]]
    if sig == "verdict":
        return [SCHEMA["verdict"], SCHEMA["bill"]]
    return []


def myth_html(rows, checked=""):
    rows = [r for r in rows or [] if r.get("myth") and r.get("fact")][:4]
    if len(rows) < 2:
        return ""
    t = TOK
    tr = "".join(
        f'<tr><td style="padding:12px 14px;border-top:1px solid {t["line"]};color:{t["myth"]};vertical-align:top;width:42%">{E(r["myth"])}</td>'
        f'<td style="padding:12px 14px;border-top:1px solid {t["line"]};color:{t["ink"]};vertical-align:top">{E(r["fact"])}'
        f'<span style="display:block;margin-top:4px;font-size:13px;color:{t["muted"]}">{E(r.get("source"))}</span></td></tr>' for r in rows)
    return (f'<div class="sig-myth" style="margin:28px 0;border:1px solid {t["line"]};border-radius:10px;overflow:hidden;background:{t["paper"]}">'
            f'<p style="margin:0;padding:14px 14px 10px;font-weight:700;color:{t["ink"]}">흔히 듣는 말과 공식 기준</p>'
            f'<table style="width:100%;border-collapse:collapse;margin:0;font-size:15px;line-height:1.6;background:#fff">'
            f'<thead><tr><th style="text-align:left;padding:8px 14px;font-size:13px;color:{t["muted"]};font-weight:600">흔히 듣는 말</th>'
            f'<th style="text-align:left;padding:8px 14px;font-size:13px;color:{t["muted"]};font-weight:600">공식 기준</th></tr></thead><tbody>{tr}</tbody></table>'
            + (f'<p style="margin:0;padding:8px 14px 12px;font-size:13px;color:{t["muted"]}">확인: {E(checked)}</p>' if checked else "")
            + "</div>")


STATUS = {"사실": "s_true", "일부 사실": "s_part", "확인 중": "s_open", "사실 아님": "s_false", "의견": "s_opinion"}


def verdict_html(v, checked=""):
    if not v or len(v.get("rows") or []) < 2:
        return ""
    t = TOK
    rows = ""
    for r in v["rows"][:5]:
        c = t[STATUS.get(r.get("status"), "s_open")]
        rows += (f'<div class="sig-row" style="padding:12px 14px;border-top:1px solid {t["line"]};background:#fff">'
                 f'<p class="sig-who" style="margin:0 0 4px;font-size:13px;color:{t["muted"]}">{E(r.get("who"))}</p>'
                 f'<p class="sig-claim" style="margin:0 0 6px;color:{t["ink"]}">{E(r.get("claim"))}</p>'
                 f'<p class="sig-check" style="margin:0;font-size:14px;color:{t["ink"]}"><span class="sig-status sig-{STATUS.get(r.get("status"), "s_open")}" style="display:inline-block;margin-right:8px;padding:1px 8px;border:1px solid {c};border-radius:999px;color:{c};font-size:13px">{E(r.get("status") or "확인 중")}</span>{E(r.get("check"))}</p></div>')
    unk = f'<p class="sig-note" style="margin:0;padding:10px 14px 12px;font-size:14px;color:{t["muted"]}">아직 모르는 것: {E(v.get("unknown"))}</p>' if v.get("unknown") else ""
    return (f'<div class="sig-verdict" style="margin:28px 0;border:1px solid {t["line"]};border-radius:10px;overflow:hidden;background:{t["paper"]}">'
            f'<p class="sig-title" style="margin:0;padding:14px;font-weight:700;color:{t["ink"]}">시시비비 판정표: {E(v.get("issue"))}</p>{rows}{unk}'
            + (f'<p class="sig-note" style="margin:0;padding:0 14px 12px;font-size:13px;color:{t["muted"]}">확인: {E(checked)}</p>' if checked else "") + "</div>")


def bill_html(b):
    if not b or not b.get("name") or b.get("stage") not in STAGES + ["폐기"]:
        return ""
    t = TOK
    cur = STAGES.index(b["stage"]) if b["stage"] in STAGES else -1
    steps = "".join(
        f'<li class="sig-step{" is-done" if i <= cur else ""}{" is-now" if i == cur else ""}" style="flex:1;min-width:0;padding:8px 4px;text-align:center;font-size:13px;border-top:3px solid {t["fact"] if i <= cur else t["line"]};'
        f'color:{t["ink"] if i == cur else t["muted"]};font-weight:{700 if i == cur else 400}">{E(s)}</li>' for i, s in enumerate(STAGES))
    num = f' (의안번호 {E(b["number"])})' if b.get("number") else ""
    link = f' <a href="{E(b["url"])}" target="_blank" rel="noopener">의안정보시스템에서 보기</a>' if str(b.get("url", "")).startswith("http") else ""
    dead = f'<p style="margin:8px 0 0;color:{t["s_false"]};font-size:14px">이 법안은 폐기됐어요.</p>' if b["stage"] == "폐기" else ""
    return (f'<div class="sig-bill" style="margin:28px 0;padding:14px;border:1px solid {t["line"]};border-radius:10px;background:{t["paper"]}">'
            f'<p class="sig-title" style="margin:0 0 8px;font-weight:700;color:{t["ink"]}">법안 지금 어디까지 왔나: {E(b["name"])}{num}</p>'
            f'<ol class="sig-steps" style="display:flex;gap:4px;list-style:none;margin:0;padding:0">{steps}</ol>{dead}'
            f'<p class="sig-note" style="margin:8px 0 0;font-size:13px;color:{t["muted"]}">{E(b.get("as_of"))} 기준.{link}</p></div>')


def block(site, res, checked=""):
    sig = site.get("signature")
    if sig == "myth_check":
        return myth_html(res.get("myth_check"), checked)
    if sig == "verdict":
        return "\n\n".join(x for x in (verdict_html(res.get("verdict"), checked), bill_html(res.get("bill"))) if x)
    return ""


def insert(md, blk):
    """첫 소제목(##) 바로 앞에 넣어요 (도입 문단 다음). 이미 있으면 바꿔요"""
    if not blk:
        return md
    md = re.sub(r'^<div class="sig-[^\n]*\n?', "", md, flags=re.M)
    m = re.search(r"^## ", md, flags=re.M)
    pos = m.start() if m else len(md)
    return md[:pos].rstrip() + "\n\n" + blk.replace("\n", " ") + "\n\n" + md[pos:]
