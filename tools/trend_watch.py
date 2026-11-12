"""사이트별 '급등 검색어' 자동 감지 (공식 데이터만).

1) 네이버 검색광고 키워드 도구(공식 API): 사이트별 씨앗 검색어의 연관 검색어와 최근 30일 검색 수를 매일 재서
   7일 전보다 크게 늘어난 검색어를 골라요. (크리에이터 어드바이저처럼 성별/연령 구분은 없어요)
2) 구글 트렌드 한국 실시간 인기 검색어(공개 RSS): 사회적으로 갑자기 뜬 이슈.
결과: status/trends_auto.json (글감·글쓰기 프롬프트에 들어가요), 기록: status/kwtrend/<사이트>.json (15일치)
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "engine"))
import keywords as kt  # noqa: E402

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
MIN_VOL = 100      # 기록에 남길 최소 월간 검색 수
KEEP_DAYS = 15


def measure(seeds):
    vol = {}
    for i in range(0, len(seeds), 5):
        words = [kt.norm(w) for w in seeds[i:i + 5] if w.strip()]
        if not words:
            continue
        for it in kt.ad_request(words, False):
            k = it.get("relKeyword", "")
            v = kt.to_int(it.get("monthlyPcQcCnt", 0)) + kt.to_int(it.get("monthlyMobileQcCnt", 0))
            if k and v >= MIN_VOL:
                vol[k] = v
        time.sleep(1.2)
    return vol


def rising(hist):
    days = sorted(hist)
    if len(days) < 2:
        return []
    now = hist[days[-1]]
    target = (datetime.strptime(days[-1], "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    base_day = max([d for d in days[:-1] if d <= target] or [days[0]])
    base = hist[base_day]
    out = []
    for k, v in now.items():
        p = base.get(k)
        if p is None:
            if v >= 1000:
                out.append({"keyword": k, "now": v, "before": None, "change": None, "since": base_day, "new": True})
            continue
        if v >= 300 and v - p >= 100 and v >= p * 1.3:
            out.append({"keyword": k, "now": v, "before": p, "change": round(v / p - 1, 2), "since": base_day})
    out.sort(key=lambda x: (x["now"] - (x["before"] or 0)), reverse=True)
    return out[:25]


def main():
    out = {"updated": datetime.now(KST).isoformat(timespec="minutes"), "sites": {}, "google": []}
    for f in sorted((ROOT / "sites").glob("*/site.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        if s["id"].startswith("_") or not s.get("enabled") or not s.get("trend_seeds"):
            continue
        hf = ROOT / f"status/kwtrend/{s['id']}.json"
        hist = json.loads(hf.read_text(encoding="utf-8")) if hf.exists() else {}
        try:
            hist[TODAY] = measure(s["trend_seeds"])
        except Exception as e:  # noqa: BLE001
            print(f"{s['id']} 측정 실패: {e}")
            continue
        for d in sorted(hist)[:-KEEP_DAYS]:
            hist.pop(d)
        hf.parent.mkdir(parents=True, exist_ok=True)
        hf.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        top = sorted(hist[TODAY].items(), key=lambda x: -x[1])[:20]
        out["sites"][s["id"]] = {"rising": rising(hist), "top": [{"keyword": k, "now": v} for k, v in top], "days": len(hist)}
        r = out["sites"][s["id"]]["rising"]
        print(f"{s['id']}: 측정 {len(hist[TODAY])}개, 급등 {len(r)}개 " + ", ".join(x["keyword"] for x in r[:5]))
    try:
        import trends
        out["google"] = [{"keyword": t["keyword"], "traffic": t["traffic_label"], "news": [n["title"] for n in t["news"]][:2]} for t in trends.google_trends()[:25]]
    except Exception as e:  # noqa: BLE001
        print("구글 트렌드 실패:", e)
    (ROOT / "status/trends_auto.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
