"""Claude 스킬 → 콘텐츠 스튜디오 동기화 (2주마다 예약 작업이 실행)

  python3 tools/sync_skills.py          바뀐 스킬만 skills/ 에 복사하고 skills/CHANGELOG.md 에 기록
  python3 tools/sync_skills.py --check  복사하지 않고 무엇이 바뀌었는지만 보기
Claude 세션 안에서만 동작해요 (스킬 최신본이 ~/.claude/skills/synced/ 에 있어요).
"""
import difflib, glob, hashlib, json, shutil, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "skills"
KST = timezone(timedelta(hours=9))


def source_dirs():
    out = {}
    for man in sorted(glob.glob(str(Path.home() / ".claude/skills/synced/*/manifest.json"))):
        base = Path(man).parent
        for s in json.load(open(man, encoding="utf-8")).get("skills", []):
            d = base / s["name"]
            if (d / "SKILL.md").exists():
                out[s["name"]] = (d, s.get("updatedAt", ""))
    return out


def digest(d):
    h = hashlib.sha256()
    for f in sorted(p for p in Path(d).rglob("*") if p.is_file()):
        h.update(str(f.relative_to(d)).encode()); h.update(f.read_bytes())
    return h.hexdigest()[:12]


def main(check=False):
    want = json.load(open(DST / "skills.json", encoding="utf-8"))["skills"]
    src = source_dirs()
    if not src:
        sys.exit("Claude 스킬 폴더를 못 찾았어요 (Claude 세션 안에서 실행해야 해요)")
    man_f = DST / "manifest.json"
    man = json.load(open(man_f, encoding="utf-8")) if man_f.exists() else {}
    changes, missing = [], []
    for name in want:
        if name not in src:
            missing.append(name); continue
        d, upd = src[name]
        dg = digest(d)
        if man.get(name, {}).get("hash") == dg:
            continue
        old = (DST / name / "SKILL.md").read_text(encoding="utf-8").splitlines() if (DST / name / "SKILL.md").exists() else []
        new = (d / "SKILL.md").read_text(encoding="utf-8").splitlines()
        diff = list(difflib.unified_diff(old, new, lineterm="", n=0))
        added = [l[1:].strip() for l in diff if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
        removed = [l for l in diff if l.startswith("-") and not l.startswith("---")]
        changes.append((name, upd, len(added), len(removed), added[:5]))
        if not check:
            if (DST / name).exists():
                shutil.rmtree(DST / name)
            shutil.copytree(d, DST / name)
            man[name] = {"updatedAt": upd, "hash": dg, "synced": datetime.now(KST).isoformat(timespec="minutes")}
    if not check:
        json.dump(man, open(man_f, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        if changes:
            log = DST / "CHANGELOG.md"
            prev = log.read_text(encoding="utf-8") if log.exists() else "# 스킬 업데이트 기록\n"
            entry = f"\n## {datetime.now(KST):%Y-%m-%d}\n" + "".join(
                f"- {n} (Claude 수정 {u[:10]}): 줄 +{a} / -{r}\n" for n, u, a, r, _ in changes)
            log.write_text(prev.rstrip() + "\n" + entry, encoding="utf-8")
    print(f"바뀐 스킬 {len(changes)}개" + (" (미리보기)" if check else ""))
    for n, u, a, r, sample in changes:
        print(f"- {n}: Claude 수정 {u[:10]}, 줄 +{a} / -{r}")
        for s in sample:
            print(f"    + {s[:90]}")
    if missing:
        print("Claude에서 못 찾은 스킬: " + ", ".join(missing))


if __name__ == "__main__":
    main("--check" in sys.argv)
