"""스레드/인스타 게시물별 성과 모으기 → status/social_stats.json"""
import json, os, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
TH, IG = "https://graph.threads.net/v1.0", "https://graph.instagram.com/v23.0"
ACC = [("woodenjoy", "threads", "THREADS_TOKEN"), ("infobay", "threads", "THREADS_TOKEN_INFOBAY"),
       ("sisibibi", "threads", "THREADS_TOKEN_SISIBIBI"), ("woodenjoy", "instagram", "IG_TOKEN"),
       ("infobay", "instagram", "IG_TOKEN_INFOBAY")]


def g(url, **p):
    try:
        return requests.get(url, params=p, timeout=30).json()
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def threads(tok):
    me = g(f"{TH}/me", fields="username", access_token=tok)
    fol = g(f"{TH}/me/threads_insights", metric="followers_count", access_token=tok)
    posts, url, p = [], f"{TH}/me/threads", dict(fields="id,text,timestamp,permalink,media_type,is_quote_post", limit=100, access_token=tok)
    while url and len(posts) < 300:
        r = g(url, **p); p = {}
        posts += r.get("data", []); url = (r.get("paging") or {}).get("next")
    for x in posts:
        ins = g(f"{TH}/{x['id']}/insights", metric="views,likes,replies,reposts,quotes,shares", access_token=tok)
        x["m"] = {d["name"]: (d.get("values") or [{}])[0].get("value", d.get("total_value", {}).get("value")) for d in ins.get("data", [])}
        if "error" in ins: x["m_err"] = ins["error"].get("message")
    return {"user": me.get("username") or me, "followers": fol.get("data", fol), "posts": posts}


def insta(tok):
    me = g(f"{IG}/me", fields="username,followers_count,media_count", access_token=tok)
    r = g(f"{IG}/me/media", fields="id,caption,timestamp,media_type,like_count,comments_count,permalink", limit=100, access_token=tok)
    posts = r.get("data", [])
    for x in posts:
        ins = g(f"{IG}/{x['id']}/insights", metric="reach,views,saved,shares,total_interactions", access_token=tok)
        x["m"] = {d["name"]: (d.get("values") or [{}])[0].get("value") for d in ins.get("data", [])}
        if "error" in ins: x["m_err"] = ins["error"].get("message")
    return {"user": me, "posts": posts, "err": r.get("error")}


out = {}
for site, plat, sec in ACC:
    tok = os.environ.get(sec, "")
    if not tok:
        out[f"{site}_{plat}"] = "토큰 없음"; continue
    out[f"{site}_{plat}"] = threads(tok) if plat == "threads" else insta(tok)
    d = out[f"{site}_{plat}"]
    print(site, plat, d.get("user"), len(d.get("posts", [])))
p = ROOT / "status/social_stats.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
