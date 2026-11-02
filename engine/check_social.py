"""사이트별 인스타·스레드 토큰이 어느 계정에 연결됐는지 확인만 해요 (아무것도 올리지 않음) → status/social-check.txt"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, load_site, now_kst, secret, site_ids  # noqa: E402


def main():
    lines = [f"점검 시각: {now_kst():%Y-%m-%d %H:%M}"]
    for sid in site_ids():
        site = load_site(sid)
        for plat, url in (("instagram", "https://graph.instagram.com/v21.0/me?fields=username,account_type"),
                          ("threads", "https://graph.threads.net/v1.0/me?fields=username")):
            cfg = site.get(plat) or {}
            if not cfg.get("enabled") or site.get("legacy"):
                continue
            name = cfg.get("token_secret", "")
            tok = secret(name, required=False)
            if not tok:
                lines.append(f"없음 {sid} {plat}: 비밀키 {name} 가 아직 없어요")
                continue
            try:
                r = requests.get(url, params={"access_token": tok}, timeout=30)
                j = r.json()
                if r.status_code >= 400:
                    lines.append(f"실패 {sid} {plat}: {str(j.get('error', j))[:200]}")
                else:
                    who = j.get("username", "?")
                    ok = "OK " if who == cfg.get("handle") else "확인필요"
                    lines.append(f"{ok} {sid} {plat}: @{who} (설정 계정 @{cfg.get('handle')}) {j.get('account_type', '')}")
                    if plat == "threads":
                        q = requests.get("https://graph.threads.net/v1.0/me/threads_publishing_limit",
                                         params={"fields": "quota_usage,config", "access_token": tok}, timeout=30)
                        lines.append(f"    올리기 권한 확인: {q.status_code} {q.text[:200]}")
            except Exception as e:  # noqa: BLE001
                lines.append(f"실패 {sid} {plat}: {e}")
    out = ROOT / "status" / "social-check.txt"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
