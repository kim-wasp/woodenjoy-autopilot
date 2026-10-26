"""naver.md(우리 원고 표시 형식) → uplika 네이버 블로그 마크다운으로 바꾸기.

  **소제목**              → ## 소제목
  [인용구-요약]…[/인용구]  → > 인용 (요약)
  [인용구-팁]…[/인용구]    → > 인용 (팁)
  [형광]문장[/형광]        → **문장**
  [구분선]                → ---
  | 표 |                  → 마크다운 표 (머리줄 구분선 자동 추가)
  [이미지: 카드 02 + 카드 03 (설명)] → ![설명](media:{card02}) 줄 2개
  [표 서식…] 줄            → 삭제 (uplika가 표 서식은 지정 못 함)
  마지막 #태그 줄          → tags 목록으로 분리
  [쿠팡: 키 | 링크 문구]    → [링크 문구](topics/coupang_links.json 의 그 키 주소)

사용: python3 tools/naver_markdown.py posts/<글폴더>   (변환 결과를 화면에 출력)
"""
import json
import re
import sys
from pathlib import Path

LEFTOVER = re.compile(r"\[(?:/?인용구|/?형광|구분선|표 서식|이미지|사진|쿠팡)")
ROOT = Path(__file__).resolve().parent.parent
COUPANG = re.compile(r"\[쿠팡:\s*([\w-]+)\s*\|\s*([^\]]+?)\s*\]")


def coupang_links():
    """사장님이 쿠팡 파트너스에서 만든 링크 모음 {키: 주소}. 주소가 빈 항목은 빼요."""
    f = ROOT / "topics/coupang_links.json"
    if not f.exists():
        return {}
    items = json.loads(f.read_text(encoding="utf-8")).get("items", [])
    return {i["key"]: i["url"] for i in items if i.get("url")}


def card_captions(post_dir):
    """cards.json 제목으로 이미지 설명(alt)을 만든다."""
    f = Path(post_dir) / "cards.json"
    if not f.exists():
        return {}
    slides = json.loads(f.read_text(encoding="utf-8"))["slides"]
    return {f"card{i + 1:02d}": re.sub(r"[*\n]+", " ", s["title"]).strip() for i, s in enumerate(slides)}


def convert(md, media=None, captions=None, links=None):
    """media: {"card01": "med_…"} 가 주어지면 실제 id로, 없으면 {card01} 자리표시로 둔다.
    captions: {"card01": "설명"} 카드별 이미지 설명."""
    media = media or {}
    captions = captions or {}
    links = coupang_links() if links is None else links
    # 쿠팡 표시 → 링크. 주소가 없는 키는 그대로 남겨서 check()가 잡아요
    md = COUPANG.sub(lambda m: f"[{m.group(2)}]({links[m.group(1)]})" if m.group(1) in links else m.group(0), md)
    lines = md.strip().split("\n")
    out, tags, in_quote, in_table = [], [], False, False

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if re.fullmatch(r"(#[^\s#]+\s*)+", s):
            tags += [t.lstrip("#") for t in s.split()]
            continue
        if s.startswith("[표 서식"):
            continue
        if s.startswith("[인용구-"):
            in_quote = True
            continue
        if s == "[/인용구]":
            in_quote = False
            out.append("")
            continue
        if s == "[구분선]":
            out += ["", "---", ""]
            continue
        m = re.fullmatch(r"\[이미지:\s*(.+)\]", s)
        if m:
            desc = re.search(r"\(([^)]*)\)\s*$", m.group(1))
            desc = desc.group(1) if desc else "카드"
            for n in re.findall(r"카드\s*0?(\d+)", m.group(1)):
                key = f"card{int(n):02d}"
                ref = media.get(key, "{" + key + "}")
                out.append(f"![{captions.get(key, desc)}](media:{ref}){{.ai}}")  # {.ai}: 네이버 'AI 활용' 표시 (uplika 확장 0.7.3 이상)
            out.append("")
            continue
        h = re.fullmatch(r"\*\*(.+?)\*\*", s)
        if h:
            out += ["", f"## {h.group(1)}", ""]
            continue
        line = re.sub(r"\[형광\](.+?)\[/형광\]", r"**\1**", line)
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            out.append("| " + " | ".join(cells) + " |")
            if not in_table:
                out.append("|" + "|".join(" --- " for _ in cells) + "|")
                in_table = True
            continue
        in_table = False
        if in_quote:
            out.append("> " + s if s else ">")
            continue
        out.append(line)

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    return text, tags


def check(text):
    problems = []
    for i, l in enumerate(text.split("\n"), 1):
        if LEFTOVER.search(l):
            problems.append(f"{i}번째 줄에 바꾸지 못한 표시가 남았어요: {l[:30]}")
    return problems


if __name__ == "__main__":
    d = Path(sys.argv[1])
    t, tags = convert((d / "naver.md").read_text(encoding="utf-8"), captions=card_captions(d))
    print(t)
    print("태그:", tags)
    p = check(t)
    if p:
        print("\n".join(p))
        sys.exit(1)
