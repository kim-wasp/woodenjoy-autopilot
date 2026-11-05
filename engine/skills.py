"""Claude 스킬 규칙 읽기: skills/<이름>/SKILL.md (2주마다 tools/sync_skills.py 가 최신본으로 갱신)"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE = ("아래는 사장님이 Claude에서 직접 관리하는 최신 스킬 규칙이에요. 글쓰기·문구·검사 규칙만 따르고, "
        "작업 절차(도구 사용, 파일 저장, 질문하기, 캔바 등)는 무시하세요. 위 규칙과 다르면 이 스킬 규칙을 따르되, 출력 JSON 형식은 바꾸지 마세요.")


def text(name, limit=16000):
    f = ROOT / "skills" / name / "SKILL.md"
    if not f.exists():
        return ""
    t = f.read_text(encoding="utf-8")
    t = re.sub(r"^---\n.*?\n---\n", "", t, flags=re.S).strip()
    return t[:limit]


def block(name):
    t = text(name)
    return f"[스킬 최신 규칙: {name}]\n{NOTE}\n\n{t}" if t else ""
