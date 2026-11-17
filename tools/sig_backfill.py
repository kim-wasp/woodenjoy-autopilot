"""이미 올린 글에 사이트 고정 형식 붙이기 (2026-11-17)

  python3 tools/sig_backfill.py forsmartlife [--apply] [--limit N]   워드프레스 글마다 '흔히 듣는 말과 공식 기준' 대조표
  python3 tools/sig_backfill.py sisibibi [--apply]                   시시비비 저장소 글마다 판정표(+법안 단계)

글 본문과 이미 달린 참고 자료 안에서만 만들어요(새 사실 금지). 숫자가 본문에 없으면 그 줄은 버려요.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "tools"))
import llm  # noqa: E402
import signature  # noqa: E402
from common import secret  # noqa: E402

APPLY = "--apply" in sys.argv
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 999
CHECKED = f"{datetime.now():%Y년 %-m월}"
nums = lambda t: set(re.findall(r"\d+(?:[.,]\d+)?", t))  # noqa: E731


def text_of(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>|<!--.*?-->", " ", html)).strip()


def refs_of(html):
    return re.findall(r'<a href="(https?://[^"]+)"[^>]*>([^<]+)</a>', html)


def myth_rows(title, body, refs):
    x = llm.ask_json("당신은 건강 정보 편집자예요. JSON만 답해요.", "\n\n".join([
        f"[글 제목] {title}", f"[글 본문]\n{body[:12000]}",
        "[이 글의 참고 자료]\n" + "\n".join(f"- {t}" for _, t in refs[:8]),
        "이 글이 바로잡는 흔한 오해(사람들이 실제로 하는 말)와 공식 기준을 2~4줄로 대조해요. "
        "규칙: 공식 기준(fact)은 반드시 위 본문에 있는 내용만, 숫자도 본문에 있는 것만. source 는 위 참고 자료 이름 중 하나(기관명 자료명)를 짧게. "
        "본문에 오해·속설이라 할 만한 게 없으면 rows 를 빈 목록으로. 말투는 짧게, 해요체 금지(명사형).",
        'JSON: {"rows": [{"myth": "흔히 듣는 말 25자 안팎", "fact": "공식 기준 50자 안팎", "source": "기관명 자료명"}]}']),
        model="claude-sonnet-5-5", max_tokens=1500)
    ok = []
    for r in x.get("rows") or []:
        if nums(r.get("fact", "") + r.get("myth", "")) - nums(body):
            continue
        ok.append(r)
    return ok


def forsmartlife():
    from fsl_fix import req
    page, done = 1, 0
    while done < LIMIT:
        r = req("GET", f"/posts?status=publish&per_page=20&page={page}&context=edit&_fields=id,slug,title,content")
        for p in r.json():
            raw = p["content"]["raw"]
            if "sig-myth" in raw or done >= LIMIT:
                continue
            refs = refs_of(raw)
            rows = myth_rows(p["title"]["raw"], text_of(raw), refs)
            blk = signature.myth_html(rows, CHECKED)
            if not blk:
                print(f"대조표 없음 {p['id']} {p['slug']}")
                continue
            m = re.search(r"<!-- wp:heading", raw) or re.search(r"<h2", raw)
            pos = m.start() if m else 0
            new = raw[:pos] + "<!-- wp:html -->\n" + blk + "\n<!-- /wp:html -->\n\n" + raw[pos:]
            print(f"대조표 {p['id']} {p['slug']}: {len(rows)}줄 · {rows[0]['myth']} → {rows[0]['fact']}")
            if APPLY:
                req("POST", f"/posts/{p['id']}", json={"content": new})
            done += 1
        if page >= int(r.headers.get("X-WP-TotalPages", 1)):
            break
        page += 1
    print(f"대조표 붙인 글 {done}개")


def sisibibi():
    tok = secret("SISIBIBI_TOKEN")
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://x-access-token:{tok}@github.com/kim-wasp/sisibibinote.git", str(tmp)], check=True)
    n = 0
    for f in sorted((tmp / "posts").glob("*/post.md")):
        t = f.read_text(encoding="utf-8")
        if "sig-verdict" in t or n >= LIMIT:
            continue
        fm, body = t.split("---\n", 2)[1], t.split("---\n", 2)[2]
        title = re.search(r"^title:\s*(.+)$", fm, re.M).group(1).strip().strip("'\"")
        plain = re.sub(r"<[^>]+>", " ", body)
        x = llm.ask_json("당신은 균형 잡힌 정치 팩트체크 편집자예요. JSON만 답해요.", "\n\n".join([
            f"[글 제목] {title}", f"[글 본문]\n{plain[:12000]}",
            "이 글의 쟁점 판정표를 만들어요. 규칙: 양쪽 진영(또는 이해관계자) 주장을 같은 수로 균형 있게, 확인된 사실(check)은 본문에 있는 내용만, 숫자도 본문에 있는 것만. "
            "가치 판단은 status '의견'. 본문에 쟁점이 없으면 rows 를 빈 목록으로. "
            "법안을 다루는 글이면 웹 검색으로 지금 단계(발의|위원회 심사|법사위|본회의 통과|정부 이송|공포|폐기)를 확인해 bill 에, 아니면 null.",
            '형식: ' + signature.SCHEMA["verdict"] + ", " + signature.SCHEMA["bill"],
            'JSON: {"verdict": {...}, "bill": {...} 또는 null}']),
            model="claude-sonnet-5-5", web_search=True, max_searches=3, max_tokens=3000)
        v = x.get("verdict") or {}
        v["rows"] = [r for r in v.get("rows") or [] if not (nums(r.get("check", "")) - nums(plain))]
        b = x.get("bill") or None
        if b and b.get("url"):
            import sources
            if not sources.alive(b["url"]):
                b["url"] = ""
        blk = signature.block({"signature": "verdict"}, {"verdict": v, "bill": b}, CHECKED)
        if not blk:
            print(f"판정표 없음 {f.parent.name}")
            continue
        new = "---\n" + fm + "---\n" + signature.insert(body, blk)
        print(f"판정표 {f.parent.name}: {len(v['rows'])}줄, 법안 {bool(x.get('bill'))}")
        f.write_text(new, encoding="utf-8")
        n += 1
    if APPLY and n:
        run = lambda *a: subprocess.run(a, cwd=tmp, check=True)  # noqa: E731
        run("git", "-c", "user.name=studio-bot", "-c", "user.email=bot@users.noreply.github.com", "commit", "-qam", f"판정표·법안 단계 붙이기 ({n}편)")
        run("git", "push", "-q", "origin", "HEAD")
    print(f"판정표 붙인 글 {n}개")


if __name__ == "__main__":
    {"forsmartlife": forsmartlife, "sisibibi": sisibibi}[sys.argv[1]]()
