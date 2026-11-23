"""사용량 장부(usage/**/*.json)를 합쳐 status/usage_summary.json 을 만들어요. 관리화면 '사용량'이 이 파일을 읽어요.

장부를 쓰기 전(2026-11-23 이전) 글은 글마다 남겨 둔 비용 기록(post.json 의 cost)으로 채워요 (세부 용도 없이 합계만).
"""
import glob
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
SITE_NAMES = {}
for f in (ROOT / "sites").glob("*/site.json"):
    try:
        SITE_NAMES[f.parent.name] = json.loads(f.read_text(encoding="utf-8")).get("name", f.parent.name)
    except Exception:  # noqa: BLE001
        pass
KEYS = ("usd", "claude_usd", "google_usd", "other_usd", "input", "cache_write", "cache_read", "output", "web_searches", "calls", "images")


def blank():
    return {k: 0 for k in KEYS}


def where(e):
    """청구처: claude(Claude 크레딧) / google(Google AI Studio) / other(OpenAI 등)"""
    if e["kind"] == "claude":
        return "claude"
    return "google" if e.get("provider") == "gemini" or str(e.get("model", "")).startswith("gemini") else "other"


def add(b, e):
    b["usd"] += e.get("usd", 0)
    b[where(e) + "_usd"] += e.get("usd", 0)
    if e["kind"] == "claude":
        for k in ("input", "cache_write", "cache_read", "output", "web_searches"):
            b[k] += e.get(k, 0)
        b["calls"] += 1
    else:
        b["images"] += e.get("count", 1)


def main():
    prices = json.loads((ROOT / "engine/prices.json").read_text(encoding="utf-8"))
    krw = prices.get("usd_krw", 1400)
    entries, runs = [], []
    for f in sorted(glob.glob(str(ROOT / "usage/*/*.json"))):
        try:
            j = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        es = j.get("entries", [])
        entries += es
        if es:
            runs.append({"file": Path(f).name, "workflow": j.get("workflow"), "event": j.get("event"), "t": es[0]["t"],
                         "task": es[0].get("task"), "site": es[0].get("site"), "calls": sum(e["kind"] == "claude" for e in es),
                         "images": sum(e["kind"] == "image" for e in es), "usd": round(sum(e.get("usd", 0) for e in es), 4),
                         "claude_usd": round(sum(e.get("usd", 0) for e in es if where(e) == "claude"), 4),
                         "google_krw": int(round(sum(e.get("usd", 0) for e in es if where(e) == "google") * krw)),
                         "other_usd": round(sum(e.get("usd", 0) for e in es if where(e) == "other"), 4)})
    start = min((e["t"] for e in entries), default=datetime.now(KST).isoformat(timespec="seconds"))
    # 장부 이전 글: post.json 비용 기록으로 채우기
    for f in glob.glob(str(ROOT / "content/*/*/post.json")):
        try:
            p = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        c, t = p.get("cost") or {}, p.get("created_at") or ""
        if not c.get("claude") and not c.get("images") or not t or t >= start:
            continue
        site = Path(f).parent.parent.name
        task = "속보 감지(이전 기록)" if "-issue-" in f else "글 만들기(이전 기록)"
        for m, u in (c.get("claude") or {}).items():
            entries.append({"t": t, "kind": "claude", "site": site, "task": task, "purpose": "글 쓰기 전체(세부 기록 전)", "model": m,
                            "input": u.get("input_tokens", 0), "cache_write": 0, "cache_read": 0, "output": u.get("output_tokens", 0),
                            "web_searches": u.get("web_searches", 0), "usd": u.get("usd", 0), "_calls": u.get("calls", 0)})
        for m, u in (c.get("images") or {}).items():
            entries.append({"t": t, "kind": "image", "site": site, "task": task, "purpose": "사진 만들기", "model": m,
                            "count": u.get("count", 0), "usd": u.get("usd", 0)})
    months = defaultdict(lambda: {"total": blank(), **{k: defaultdict(blank) for k in ("by_site", "by_task", "by_purpose", "by_model", "by_day", "by_site_task")}})
    for e in entries:
        mo = months[e["t"][:7]]
        site = SITE_NAMES.get(e.get("site"), e.get("site") or "공통")
        for b in (mo["total"], mo["by_site"][site], mo["by_task"][e.get("task") or "?"], mo["by_purpose"][e.get("purpose") or "?"],
                  mo["by_model"][e.get("model") or "?"], mo["by_day"][e["t"][:10]], mo["by_site_task"][f"{site} / {e.get('task') or '?'}"]):
            add(b, e)
            if e.get("_calls"):
                b["calls"] += e["_calls"] - 1
    out = {"updated": datetime.now(KST).isoformat(timespec="minutes"), "ledger_start": start, "usd_krw": krw,
           "note": "Claude 는 달러(크레딧에서 빠지는 단위), Google AI Studio 는 원화로 따로 보여 줘요. 비용은 engine/prices.json 단가로 계산한 추정치예요. 실제 청구액은 Claude Console(사용량·비용)과 Google AI Studio(결제) 기준. "
                   f"{start[:16].replace('T', ' ')} 이전은 글마다 남긴 합계만 있어서 용도별 세부가 없어요.",
           "months": {}, "recent_runs": sorted(runs, key=lambda r: r["t"], reverse=True)[:200]}
    for m, mo in sorted(months.items()):
        fin = lambda v: {**{kk: (round(vv, 4) if kk.endswith("usd") else vv) for kk, vv in v.items()}, "google_krw": int(round(v["google_usd"] * krw))}  # noqa: E731
        r = lambda d: {k: fin(v) for k, v in sorted(d.items(), key=lambda kv: -kv[1]["usd"])}  # noqa: E731
        out["months"][m] = {"total": fin(mo["total"]),
                            **{k: r(mo[k]) for k in ("by_site", "by_task", "by_purpose", "by_model", "by_site_task")},
                            "by_day": {k: v for k, v in sorted(r(mo["by_day"]).items())}}
    (ROOT / "status/usage_summary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for m, mo in out["months"].items():
        t = mo["total"]
        print(f"{m}: Claude ${t['claude_usd']:.2f} · Google AI Studio {t['google_krw']:,}원" + (f" · 그 밖 ${t['other_usd']:.2f}" if t["other_usd"] else "") + f" · Claude {t['calls']}회 · 입력 {t['input']:,} · 출력 {t['output']:,} · 검색 {t['web_searches']} · 사진 {t['images']}장")


if __name__ == "__main__":
    main()
