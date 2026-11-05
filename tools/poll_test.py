"""스레드 투표 선택지 길이 시험: 글 상자(container)만 만들고 올리지는 않아요."""
import json, os, requests
tok = os.environ["THREADS_TOKEN_INFOBAY"]
cases = {
  "ascii": ("yes", "no"),
  "short_ko": ("인정", "아닌데"),
  "full_ko": ("인정 (내 좌석 내 권리지)", "아닌데 (뒷사람 생각해야지)"),
  "mid_ko": ("인정 (권리지)", "아닌데 (오바)"),
  "ko8": ("내 좌석 내 권리", "뒷사람 생각해야"),
}
for name, (a, b) in cases.items():
    for esc in (False, True):
        r = requests.post("https://graph.threads.net/v1.0/me/threads", data={"media_type": "TEXT", "text": "시험", "access_token": tok,
            "poll_attachment": json.dumps({"option_a": a, "option_b": b}, ensure_ascii=esc)}, timeout=60)
        print(name, "escape" if esc else "raw", len(a), len(a.encode()), r.status_code, (r.json().get("error") or {}).get("error_user_title", "OK"))
