// 네이버 홈피드용 썸네일: 사진 위에 후킹 문구를 크게 얹어요
// 사용: node tools/render_thumb.js <원본사진.jpg> <저장할.jpg> "첫 줄\n둘째 줄" [스타일번호]
//  - 스타일 8가지(글자 위치·바탕·색)를 글마다 돌려 써서 썸네일이 매번 같아 보이지 않게 해요
//  - 글자는 가운데 70% 안에 둬요 (홈피드가 정사각형·가로형 어느 쪽으로 잘라도 보이게)
const { chromium } = require('playwright');
const fs = require('fs');

const [src, out, raw, styleArg] = process.argv.slice(2);
const lines = String(raw || '').replace(/\\n/g, '\n').split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 2);
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const longest = Math.max(...lines.map((l) => l.length), 1);
const size = (max) => Math.max(72, Math.min(max, Math.floor(980 / longest)));
const img = fs.readFileSync(src).toString('base64');
const P = [ // 강조색 묶음
  { a: '#ffe14d', b: '#111111', c: '#ffffff' }, { a: '#ff6b3d', b: '#1d1d1d', c: '#ffffff' }, { a: '#5ee0b5', b: '#0f2e26', c: '#ffffff' },
  { a: '#ffd1dc', b: '#3a1022', c: '#ffffff' }, { a: '#9fd3ff', b: '#0b2440', c: '#ffffff' }, { a: '#fff3c4', b: '#5a3200', c: '#ffffff' }];
const n = Number.isFinite(+styleArg) ? +styleArg : Math.floor(Math.random() * 1000);
const st = n % 8, p = P[Math.floor(n / 8) % P.length];
const L = (cls = '') => lines.map((l, i) => `<span class="l ${cls} ${i === lines.length - 1 ? 'last' : 'first'}">${esc(l)}</span>`).join('');
const base = `body{margin:0}#t{width:1080px;height:1080px;position:relative;overflow:hidden;font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;background:url(data:image/jpeg;base64,${img}) center/cover}
.l{display:block;font-weight:900;letter-spacing:-3px;line-height:1.2}`;
const S = [
  // 0 가운데 어두운 띠 (예전 방식)
  [`#t:before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 20%,rgba(0,0,0,.45) 38%,rgba(0,0,0,.45) 66%,rgba(0,0,0,0) 84%)}
   .box{position:absolute;left:0;right:0;top:50%;transform:translateY(-50%);text-align:center;padding:0 60px}
   .l{color:#fff;font-size:${size(130)}px;text-shadow:0 4px 18px rgba(0,0,0,.55),0 0 2px rgba(0,0,0,.9)}.l.last{color:${p.a}}`, L()],
  // 1 아래쪽 단색 띠 (뉴스 자막처럼)
  [`.box{position:absolute;left:0;right:0;bottom:150px;background:${p.b};padding:34px 60px;text-align:left}
   .l{color:#fff;font-size:${size(108)}px}.l.last{color:${p.a}}`, L()],
  // 2 위쪽 왼쪽 큰 스티커 상자
  [`.box{position:absolute;left:120px;top:150px;max-width:820px}
   .l{display:inline-block;background:${p.a};color:${p.b};font-size:${size(112)}px;padding:6px 26px;margin:0 0 14px;transform:rotate(-2deg);box-shadow:8px 8px 0 rgba(0,0,0,.35)}
   .l.last{background:#fff}`, L()],
  // 3 왼쪽 색 판 + 오른쪽 사진 (글자는 판 안에서 단어 단위로 줄바꿈)
  [`#t:before{content:"";position:absolute;left:0;top:0;bottom:0;width:58%;background:${p.b}}
   .box{position:absolute;left:70px;top:50%;transform:translateY(-50%);width:500px}
   .l{color:#fff;font-size:${longest > 9 ? 86 : 100}px;letter-spacing:-2px;word-break:keep-all;line-height:1.18;margin-bottom:18px}.l.last{color:${p.a}}`, L()],
  // 4 형광펜 밑줄 (위쪽)
  [`#t:before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,.88) 0%,rgba(255,255,255,.75) 40%,rgba(255,255,255,0) 62%)}
   .box{position:absolute;left:0;right:0;top:150px;text-align:center}
   .l{display:inline;color:#111;font-size:${size(118)}px;background:linear-gradient(transparent 62%,${p.a} 62%)}
   .l.first:after{content:"";display:block}`, L()],
  // 5 흰 말풍선 카드 (가운데)
  [`#t:before{content:"";position:absolute;inset:0;background:rgba(0,0,0,.18)}
   .box{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:#fff;border-radius:44px;padding:44px 56px;text-align:center;box-shadow:0 18px 50px rgba(0,0,0,.35);max-width:860px}
   .box:after{content:"";position:absolute;left:50%;bottom:-38px;margin-left:-30px;border:30px solid transparent;border-top:40px solid #fff}
   .l{color:#111;font-size:${Math.min(size(104), Math.floor(760 / longest))}px;white-space:nowrap}.l.last{color:${p.b === '#111111' ? '#e5484d' : p.b}}`, L()],
  // 6 굵은 테두리 글씨 (아래쪽, 배경 그라데이션)
  [`#t:before{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 45%,rgba(0,0,0,.6) 100%)}
   .box{position:absolute;left:110px;right:90px;bottom:160px;text-align:left;border-left:22px solid ${p.a};padding-left:40px}
   .l{color:#fff;font-size:${Math.min(size(124), Math.floor(800 / longest))}px;text-shadow:0 5px 0 rgba(0,0,0,.55)}.l.last{color:${p.a}}`, L()],
  // 7 위쪽 단색 띠 + 작은 꼬리표
  [`.box{position:absolute;left:0;right:0;top:150px;background:${p.a};padding:30px 60px;text-align:center}
   .l{color:${p.b};font-size:${size(110)}px}.l.last{color:#111}`, L()],
];
const [css, inner] = S[st];
const html = `<!doctype html><html><head><meta charset="utf-8"><style>${base}${css}</style></head><body><div id="t"><div class="box">${inner}</div></div></body></html>`;
(async () => {
  const b = await chromium.launch();
  const pg = await b.newPage({ viewport: { width: 1080, height: 1080 } });
  await pg.setContent(html, { waitUntil: 'load' });
  await pg.evaluate(() => document.fonts.ready);
  await (await pg.$('#t')).screenshot({ path: out, type: 'jpeg', quality: 90 });
  await b.close();
  console.log(`홈피드 썸네일 완성 (스타일 ${st}, 색 ${Math.floor(n / 8) % P.length}) ${lines.join(' / ')}`);
})().catch((e) => { console.error('썸네일 실패: ' + e.message); process.exit(1); });
