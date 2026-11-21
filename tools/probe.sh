#!/bin/bash
python3 - <<'PY'
import re, requests
US = '''https://forsmartlife.com/yellow-dust-mask-reuse-guide-2026/
https://forsmartlife.com/wp-includes/js/wp-emoji-release.min.js?ver=7.1
https://forsmartlife.com/wp-includes/js/wp-emoji-release.min.js?ver=7.0
https://forsmartlife.com/april-spring-herb-detox-combination/
https://forsmartlife.com/april-temperature-gap-vascular-morning-habits/
https://forsmartlife.com/basal-metabolic-rate-boost-spring/
https://forsmartlife.com/creatine-brain-muscle-guide-over-40/
https://forsmartlife.com/dry-cough-gerd-symptoms/
https://forsmartlife.com/eyelid-twitching-magnesium-vs-brain/
https://forsmartlife.com/fine-dust-cleansing-routine/
https://forsmartlife.com/fine-dust-skin-care-routine/
https://forsmartlife.com/high-protein-foods-sarcopenia-prevention-4050/
https://forsmartlife.com/meibomian-gland-cleaning/
https://forsmartlife.com/morning-lemon-water-liver-detox/
https://forsmartlife.com/scalp-cooling-scaling/
https://forsmartlife.com/seasonal-shingles-immunity-warning/
https://forsmartlife.com/spring-allergic-rhinitis-care/
https://forsmartlife.com/spring-allergy-immunity/
https://forsmartlife.com/spring-blues-sunlight-routine/
https://forsmartlife.com/spring-fatigue-cause/
https://forsmartlife.com/spring-fatigue-causes/
https://forsmartlife.com/spring-hair-loss-cooling-shampoo/
https://forsmartlife.com/spring-immunity-foods/
https://forsmartlife.com/spring-immunity-habits/
https://forsmartlife.com/spring-insomnia-melatonin-fruits/
https://forsmartlife.com/yellow-dust-2026-lung-protection-foods/
https://forsmartlife.com/yellow-dust-lung-foods/'''.split()
sm = requests.get("https://forsmartlife.com/post-sitemap.xml", headers={"User-Agent": "Googlebot"}, timeout=30).text
inmap = set(re.findall(r"<loc>([^<]+)</loc>", sm))
for u in US:
    r = requests.get(u, headers={"User-Agent": "Googlebot"}, timeout=30, allow_redirects=False)
    rob = re.search(r'<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)', r.text)
    n = len(re.sub(r"\s+", "", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", r.text, flags=re.S)))
    print(f"{r.status_code} | {'사이트맵O' if u in inmap else '사이트맵X'} | {(rob.group(1) if rob else '-')[:16]} | len={n} | {r.headers.get('location','')[-60:]} | {u[26:]}")
PY
