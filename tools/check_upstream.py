"""외부 원본 스킬 확인: 원본 저장소(예: im-not-ai)가 바뀌었는지 보고, 규칙 번호가 어떻게 달라졌는지 알려줘요.

  python3 tools/check_upstream.py           확인하고 skills/upstream.json 에 마지막 확인 기록
  python3 tools/check_upstream.py --check   기록하지 않고 보기만
바뀌었으면 원본 규칙 파일을 skills/<이름>/upstream/ 에 받아 둬요. 사장님의 Claude 스킬은 사장님이 승인해야 바뀌어요.
"""
import json, re, subprocess, sys, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "skills" / "upstream.json"
KST = timezone(timedelta(hours=9))
RULE = re.compile(r"\*\*([A-Z]-\d+[a-z]?)\*\*")


def main(check=False):
    reg = json.load(open(REG, encoding="utf-8"))
    for name, u in reg.items():
        if name.startswith("_"):
            continue
        tmp = tempfile.mkdtemp()
        subprocess.run(["git", "clone", "-q", "--depth", "50", f"https://github.com/{u['repo']}.git", tmp], check=True)
        log = subprocess.run(["git", "-C", tmp, "log", "-1", "--format=%h %cd %s", "--date=short", "--", u["path"]], capture_output=True, text=True).stdout.strip()
        commit = log.split(" ")[0] if log else ""
        src = Path(tmp) / u["path"]
        up_rules = set(RULE.findall(src.read_text(encoding="utf-8"))) if src.exists() else set()
        mine_f = ROOT / "skills" / name / "SKILL.md"
        my_rules = set(RULE.findall(mine_f.read_text(encoding="utf-8"))) if mine_f.exists() else set()
        new, gone = sorted(up_rules - my_rules), sorted(my_rules - up_rules)
        changed = bool(u.get("last_commit")) and commit != u["last_commit"]
        print(f"[{name}] 원본 {u['repo']} 마지막 변경: {log or '알 수 없음'}")
        print(f"  원본 규칙 {len(up_rules)}개 / 사장님 스킬 규칙 {len(my_rules)}개")
        if new:
            print("  원본에만 있는 규칙: " + ", ".join(new))
        if gone:
            print("  사장님 스킬에만 있는 규칙: " + ", ".join(gone))
        print("  상태: " + ("원본이 바뀜, 스킬 업데이트 제안 필요" if (changed or new or gone) else "변화 없음"))
        if not check:
            if changed or new or gone:
                dst = ROOT / "skills" / name / "upstream"
                dst.mkdir(parents=True, exist_ok=True)
                (dst / Path(u["path"]).name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            u["last_commit"], u["last_checked"] = commit, datetime.now(KST).isoformat(timespec="minutes")
    if not check:
        json.dump(reg, open(REG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main("--check" in sys.argv)
