// 네이버 홈피드용 썸네일: 사진 위에 후킹 문구를 크게 얹어요
// 사용: node tools/render_thumb.js <원본사진.jpg> <저장할.jpg> "첫 줄\n둘째 줄"
//  - 글자는 가운데 띠 안에 둬요 (홈피드가 정사각형·가로형 어느 쪽으로 잘라도 보이게)
const { chromium } = require('playwright');
const fs = require('fs');

const [src, out, raw] = process.argv.slice(2);
const lines = String(raw || '').replace(/\\n/g, '\n').split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 2);
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const longest = Math.max(...lines.map((l) => l.length), 1);
const size = Math.max(76, Math.min(132, Math.floor(1000 / longest)));
const img = fs.readFileSync(src).toString('base64');
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0}
#t{width:1080px;height:1080px;position:relative;overflow:hidden;font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;
 background:url(data:image/jpeg;base64,${img}) center/cover}
#t:before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 20%,rgba(0,0,0,.45) 38%,rgba(0,0,0,.45) 66%,rgba(0,0,0,0) 84%)}
.box{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;padding:0 60px}
.l{display:block;color:#fff;font-weight:900;font-size:${size}px;line-height:1.22;letter-spacing:-3px;
 text-shadow:0 4px 18px rgba(0,0,0,.55),0 0 2px rgba(0,0,0,.9)}
.l.y{color:#ffe14d}
</style></head><body><div id="t"><div class="box">${lines.map((l, i) => `<span class="l${i === lines.length - 1 ? ' y' : ''}">${esc(l)}</span>`).join('')}</div></div></body></html>`;
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1080 } });
  await p.setContent(html, { waitUntil: 'load' });
  await p.evaluate(() => document.fonts.ready);
  await (await p.$('#t')).screenshot({ path: out, type: 'jpeg', quality: 90 });
  await b.close();
  console.log(`홈피드 썸네일 완성 (${lines.join(' / ')})`);
})().catch((e) => { console.error('썸네일 실패: ' + e.message); process.exit(1); });
