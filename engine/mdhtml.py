"""간단한 마크다운 → HTML 변환 (워드프레스 본문·미리보기용, 외부 라이브러리 없음).

지원: ## 제목, ### 소제목, 문단, - / 1. 목록, | 표 |, > 인용, **굵게**, [링크](주소), ---
이미지 자리표시: [[card:3]] → 카드 3번 이미지, [[hero]] → 대표 이미지
"""
import html
import re


def _inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', s)
    return s


def convert(md, image_url=None):
    """image_url(name) → 주소. name 은 'hero' 또는 'card:3'"""
    out, i = [], 0
    lines = md.replace("\r\n", "\n").split("\n")
    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        if not s:
            i += 1
            continue
        m = re.fullmatch(r"\[\[(hero|card:\d+)\]\]", s)
        if m:
            if image_url:
                url, alt = image_url(m.group(1))
                if url:
                    out.append(f'<figure><img src="{url}" alt="{html.escape(alt or "")}" loading="lazy"/></figure>')
            i += 1
            continue
        if s.startswith("### "):
            out.append(f"<h3>{_inline(s[4:])}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{_inline(s[3:])}</h2>")
        elif s == "---":
            out.append("<hr/>")
        elif s.startswith(">"):
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(_inline(lines[i].strip()[1:].strip()))
                i += 1
            out.append("<blockquote><p>" + "<br/>".join(q) + "</p></blockquote>")
            continue
        elif s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                head = "".join(f"<th>{_inline(c)}</th>" for c in rows[0])
                body = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in rows[1:])
                out.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
            continue
        elif re.match(r"^(-|\*|\d+\.)\s", s):
            ordered = bool(re.match(r"^\d+\.", s))
            items = []
            while i < len(lines) and re.match(r"^(-|\*|\d+\.)\s", lines[i].strip()):
                items.append(_inline(re.sub(r"^(-|\*|\d+\.)\s+", "", lines[i].strip())))
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{x}</li>" for x in items) + f"</{tag}>")
            continue
        else:
            para = [s]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(#|>|\||-|\*|\d+\.\s|\[\[|---)", lines[i].strip()):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>" + "<br/>".join(_inline(p) for p in para) + "</p>")
            continue
        i += 1
    return "\n".join(out)
