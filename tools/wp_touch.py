"""페이지를 같은 내용으로 다시 저장해서 캐시를 비워요 (WP Super Cache는 글을 저장하면 그 글과 첫 페이지 캐시를 지워요)"""
import base64, os, sys, requests
B = "https://forsmartlife.com/wp-json/wp/v2"
A = {"Authorization": "Basic " + base64.b64encode(f"gracelyun28:{os.environ['WP']}".encode()).decode(), "User-Agent": "Mozilla/5.0"}
for i in sys.argv[1:]:
    p = requests.get(f"{B}/pages/{i}", headers=A, params={"context": "edit"}, timeout=60).json()
    print(i, requests.post(f"{B}/pages/{i}", headers=A, json={"content": p["content"]["raw"]}, timeout=60).status_code)
