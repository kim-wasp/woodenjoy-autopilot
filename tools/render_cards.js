// 카드뉴스 만들기 + 자동 점검
// 사용: node tools/render_cards.js posts/<글폴더>
//  - 입력: <글폴더>/cards.json
//  - 출력: <글폴더>/cards/01.jpg … (인스타용 1080x1350 JPEG), cards/preview.html, cards/qa.json
//  - 점검에 걸리면 종료 코드 1 (업로드 단계로 넘어가지 않음)
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
// 사이트마다 다른 브랜드·용어를 쓸 수 있어요 (BRAND_FILE, TERMS_FILE 환경변수, 없으면 우드엔조이 기본값)
const brand = JSON.parse(fs.readFileSync(process.env.BRAND_FILE || path.join(ROOT, 'config/brand.json'), 'utf8'));
const TERMS_FILE = process.env.TERMS_FILE || path.join(ROOT, 'config/terms.json');
const COLOR_VARS = { bg: '--bg', pine: '--pine', deep: '--deep', ink: '--ink', amber: '--amber2', amberInk: '--amberInk', muted: '--muted' };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const br = (s) => esc(s).replace(/\n/g, '<br>');
// 제목 안에서 *강조* 표시는 초록색으로
const em = (s) => br(s).replace(/\*([^*]+)\*/g, '<span class="hl">$1</span>');

function body(b) {
  if (!b) return '';
  switch (b.kind) {
    case 'svg':
      return `<div class="card" style="height:${b.height || 560}px;${b.transparent ? 'background:transparent' : ''}">${b.svg}</div>`;
    case 'steps':
      b.items = b.items || [];
      return `<div class="steps">${b.items.map((it, i) => `<div class="step"><div class="num">${i + 1}</div><div><p class="d">${br(it.d)}</p>${it.s ? `<p class="s">${br(it.s)}</p>` : ''}</div></div>`).join('')}</div>`
        + (b.tip ? `<p class="tip">${br(b.tip)}</p>` : '');
    case 'chips':
      b.legend = b.legend || []; b.example = b.example || b.legend.map((x) => x[0]);
      return `<div class="pname"><p class="ex">${esc(b.label || '쇼핑몰 상품명 예시')}</p><div class="chips">${b.example.map((c, i) => `<span class="chip c${i % 5}">${esc(c)}</span>`).join('')}</div></div>`
        + `<div class="legend">${b.legend.map(([c, d]) => { const i = b.example.indexOf(c); return `<div class="row"><span class="chip c${(i < 0 ? 1 : i) % 5}">${esc(c)}</span><span class="d">${br(d)}</span></div>`; }).join('')}</div>`;
    case 'image': {
      // 글 폴더 안의 사진(예: hero.jpg)을 카드에 넣어요
      const f = path.join(CUR_DIR, b.src);
      const data = fs.readFileSync(f).toString('base64');
      return `<div class="card" style="height:${b.height || 640}px"><img src="data:image/jpeg;base64,${data}" style="width:100%;height:100%;object-fit:cover" alt=""></div>`;
    }
    case 'grid':
      b.items = b.items || [];
      return `<div class="grid">${b.items.map((it) => `<div class="cell">${it.svg || ''}<span class="l">${esc(it.label)}</span></div>`).join('')}</div>`;
    default:
      throw new Error('알 수 없는 카드 종류: ' + b.kind);
  }
}

// 사진 배경 카드: s.photo = 글 폴더 안 사진 파일 (예: photo1.jpg). 어두운 그라데이션 위에 흰 글자
function photoStyle(s) {
  if (!s.photo) return '';
  const data = fs.readFileSync(path.join(CUR_DIR, s.photo)).toString('base64');
  return ` style="background-image:linear-gradient(180deg,rgba(0,0,0,.62) 0%,rgba(0,0,0,.25) 45%,rgba(0,0,0,.2) 60%,rgba(0,0,0,.7) 100%),url(data:image/jpeg;base64,${data});background-size:cover;background-position:center"`;
}
function slideHtml(s, i, n) {
  return `<section class="slide${s.photo ? ' photo' : ''}" id="s${i + 1}"${photoStyle(s)}>
  <div class="top"><span>${esc(brand.cardLabel)}</span><span>${i + 1} / ${n}</span></div>
  <h1 class="title${s.big ? ' big' : ''}" data-lines="${s.title_lines || (s.title.split('\n').length)}">${em(s.title)}</h1>
  ${s.sub ? `<p class="sub" data-lines="${s.sub_lines || s.sub.split('\n').length}">${br(s.sub)}</p>` : ''}
  ${body(s.body)}
  ${s.badge ? `<div class="badge"${s.badge_center ? ' style="align-self:center"' : ''}>${esc(s.badge)}</div>` : ''}
  <div class="foot">${esc(brand.handle)}</div>
</section>`;
}

const QA = () => {
  const MIN_FONT = 36, FOOT_ZONE = 130, MARGIN = 40;
  const res = [];
  document.querySelectorAll('.slide').forEach((s) => {
    const sr = s.getBoundingClientRect(), issues = [];
    s.querySelectorAll('*').forEach((el) => {
      if (el.closest('svg') && el.tagName.toLowerCase() !== 'text') return;
      const own = Array.from(el.childNodes).some((n) => n.nodeType === 3 && n.textContent.trim());
      if (!own) return;
      const txt = el.textContent.trim().slice(0, 20);
      let size = parseFloat(getComputedStyle(el).fontSize);
      if (el.tagName.toLowerCase() === 'text') {
        const sv = el.ownerSVGElement, vb = sv.viewBox.baseVal;
        size = Math.round(parseFloat(el.getAttribute('font-size') || 16) * (vb && vb.width ? sv.getBoundingClientRect().width / vb.width : 1));
      }
      if (size < MIN_FONT) issues.push(`글자 너무 작음 ${size}px: "${txt}"`);
      const r = el.getBoundingClientRect();
      if (!el.closest('.foot') && (r.left < sr.left + MARGIN - 1 || r.right > sr.right - MARGIN + 1)) issues.push(`좌우 여백 침범: "${txt}"`);
      if (el.tagName.toLowerCase() !== 'text' && el.scrollWidth > el.clientWidth + 1) issues.push(`가로 넘침: "${txt}"`);
      if (!el.closest('.foot') && r.bottom > sr.bottom - FOOT_ZONE) issues.push(`계정명 자리 침범: "${txt}"`);
    });
    s.querySelectorAll('[data-lines]').forEach((el) => {
      const lh = parseFloat(getComputedStyle(el).lineHeight);
      const lines = Math.round(el.getBoundingClientRect().height / lh);
      if (lines !== +el.dataset.lines) issues.push(`줄 수 다름(${lines}줄, 의도 ${el.dataset.lines}줄): "${el.textContent.trim().slice(0, 20)}"`);
    });
    const kids = Array.from(s.children).filter((k) => !k.classList.contains('foot'));
    for (let i = 0; i < kids.length - 1; i++) {
      if (kids[i].getBoundingClientRect().bottom > kids[i + 1].getBoundingClientRect().top + 1) issues.push(`블록 겹침: ${kids[i].className} ↔ ${kids[i + 1].className}`);
    }
    const last = kids[kids.length - 1].getBoundingClientRect();
    if (last.bottom > sr.bottom - FOOT_ZONE) issues.push(`본문이 계정명 자리까지 내려옴`);
    const gap = sr.bottom - FOOT_ZONE - last.bottom;
    if (gap > (s.querySelector('h1.big') ? 380 : 260) && !s.classList.contains('photo')) issues.push(`아래 빈 공간 큼 (${Math.round(gap)}px)`);
    s.querySelectorAll('.card,.cell,.step,.row').forEach((c) => { if (!c.textContent.trim() && !c.querySelector('svg *, img')) issues.push(`빈 칸: ${c.className}`); });
    s.querySelectorAll('svg').forEach((svg) => {
      const vr = svg.getBoundingClientRect();
      svg.querySelectorAll('text').forEach((t) => {
        const r = t.getBoundingClientRect();
        if (r.left < vr.left - 1 || r.right > vr.right + 1 || r.top < vr.top - 1 || r.bottom > vr.bottom + 1) issues.push(`그림 속 글자 잘림: "${t.textContent.slice(0, 15)}"`);
        // 상자·원 안에 있어야 할 글자가 테두리를 넘는지
        const cx = (r.left + r.right) / 2, cy = (r.top + r.bottom) / 2;
        let best = null;
        svg.querySelectorAll('rect,circle,ellipse').forEach((sh) => {
          const bb = sh.getBoundingClientRect();
          if (bb.width < 60 || bb.height < 40) return;
          if (cx > bb.left && cx < bb.right && cy > bb.top && cy < bb.bottom && (!best || bb.width * bb.height < best.width * best.height)) best = bb;
        });
        const vt = r.height * 0.2; // 글꼴 상자 위아래 여유분
        if (best && (r.left < best.left - 2 || r.right > best.right + 2 || r.top < best.top - vt || r.bottom > best.bottom + vt)) issues.push(`글자가 도형 밖으로 삐져나옴: "${t.textContent.slice(0, 15)}"`);
      });
    });
    res.push({ id: s.id, issues, text: s.innerText.replace(/\s+/g, ' ').trim() });
  });
  return res;
};

// 글마다 바뀌는 카드 디자인 (CARD_THEME 번호). 글자 크기·배치는 그대로라 자동 점검 기준은 같아요
const THEMES = [
  { vars: '', css: '' },
  { vars: '--bg:#F7F1E6;--pine:#C2552E;--deep:#3B2A1E;--amber:#FFF6E6;--amber2:#F3D7A6;--amberInk:#8A4B14;--line:#E6D8C3',
    css: '.slide:not(.photo){background-image:linear-gradient(#0000 31px,#3b2a1e10 32px),linear-gradient(90deg,#0000 31px,#3b2a1e10 32px);background-size:32px 32px}.num{border-radius:22px}' },
  { vars: '--bg:#EAF0F8;--pine:#2B5BA8;--deep:#14284A;--amber:#FFF8DD;--amber2:#FFE08A;--amberInk:#7A5A00;--line:#C9D6EA',
    css: '.slide:not(.photo):before{content:"";position:absolute;left:0;right:0;top:0;height:18px;background:var(--pine)}.title{letter-spacing:-3px}' },
  { vars: '--bg:#1E2326;--pine:#F2C14E;--deep:#FFFFFF;--ink:#F2F2F2;--muted:#A9B1B5;--white:#2B3236;--amber:#3A3424;--amber2:#F2C14E;--amberInk:#2A2000;--line:#3A4247',
    css: '.num{color:#1E2326}.c0{background:#3A4247;color:#fff}.c1{background:#2F4A3F;color:#E9FFF4}.tip{color:#F8E7B0}' },
  { vars: '--bg:#F2F2F0;--pine:#E8590C;--deep:#222222;--amber:#FFF1E6;--amber2:#FFD8BA;--amberInk:#8A3A00;--line:#DDDDD8',
    css: '.slide:not(.photo){background-image:radial-gradient(#22222214 2px,transparent 2px);background-size:28px 28px}.num{border-radius:14px;transform:rotate(-4deg)}' },
  { vars: '--bg:#F1EEF8;--pine:#6B4FB3;--deep:#2E2160;--amber:#FFF8E1;--amber2:#FCE7A8;--amberInk:#6E5300;--line:#DCD3EF',
    css: '.slide:not(.photo):before{content:"";position:absolute;right:-180px;top:-180px;width:460px;height:460px;border-radius:50%;background:#6B4FB31A}' },
];
let CUR_DIR = '.';
(async () => {
  const dir = path.resolve(process.argv[2]);
  CUR_DIR = dir;
  const spec = JSON.parse(fs.readFileSync(path.join(dir, 'cards.json'), 'utf8'));
  const slides = spec.slides;
  if (slides.length < 2 || slides.length > 10) throw new Error('카드는 2~10장이어야 해요 (인스타 캐러셀 제한)');
  const css = fs.readFileSync(path.join(__dirname, 'card.css'), 'utf8');
  const vars = Object.entries(brand.colors || {}).filter(([k, v]) => COLOR_VARS[k] && v).map(([k, v]) => `${COLOR_VARS[k]}:${v}`).join(';');
  const th = THEMES[(parseInt(process.env.CARD_THEME || '0', 10) || 0) % THEMES.length];
  const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8"><style>${css}${th.vars ? `:root{${th.vars}}` : ''}${vars ? `:root{${vars}}` : ''}${th.css}</style></head><body>${slides.map((s, i) => slideHtml(s, i, slides.length)).join('\n')}</body></html>`;
  const outDir = path.join(dir, 'cards');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'preview.html'), html);

  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 1500 } });
  await p.setContent(html, { waitUntil: 'load' });
  await p.evaluate(() => document.fonts.ready);
  const report = await p.evaluate(QA);
  const files = [];
  for (let i = 0; i < report.length; i++) {
    const f = path.join(outDir, String(i + 1).padStart(2, '0') + '.jpg');
    await (await p.$('#' + report[i].id)).screenshot({ path: f, type: 'jpeg', quality: 92 });
    files.push(f);
  }
  await b.close();

  const sim = JSON.parse(execFileSync('python3', [path.join(__dirname, 'sim.py'), ...files]).toString());
  // 같은 틀이라 그림은 비슷해 보여도 글이 다르면 통과 (글 내용이 60% 넘게 겹칠 때만 '비슷함')
  const grams = (o) => { const t = JSON.stringify(o).replace(/[^가-힣0-9a-zA-Z]/g, ''); const g = new Set(); for (let i = 0; i < t.length - 1; i++) g.add(t.slice(i, i + 2)); return g; };
  const textSim = (a, b) => { const A = grams(a), B = grams(b); let n = 0; A.forEach((x) => { if (B.has(x)) n++; }); return n / Math.max(1, Math.min(A.size, B.size)); };
  const similar = sim.filter((x) => x[2] < 7 && textSim(slides[x[0]], slides[x[1]]) > 0.6 && !(slides[x[0]].photo && slides[x[1]].photo && slides[x[0]].photo !== slides[x[1]].photo)).map((x) => `${x[0] + 1}장과 ${x[1] + 1}장이 너무 비슷함`);
  const seen = {};
  report.forEach((r, i) => r.text.split(/(?<=[.요다!?])\s/).forEach((t) => { t = t.trim(); if (t.length > 12 && !t.includes(brand.handle) && !(brand.cardLabel && t.includes(brand.cardLabel))) (seen[t] = seen[t] || new Set()).add(i + 1); }));
  const repeated = Object.entries(seen).filter(([, ids]) => ids.size > 1).map(([t, ids]) => `반복 문장 "${t.slice(0, 20)}" (${[...ids].join(',')}장)`);
  // 금지 용어
  const terms = fs.existsSync(TERMS_FILE) ? JSON.parse(fs.readFileSync(TERMS_FILE, 'utf8')) : { banned: [] };
  const banned = [];
  report.forEach((r, i) => terms.banned.forEach((w) => { if (r.text.includes(w.term)) banned.push(`${i + 1}장 금지 용어 "${w.term}" → ${w.use}`); }));

  const all = report.flatMap((r, i) => r.issues.map((x) => `${i + 1}장: ${x}`)).concat(similar, repeated, banned);
  fs.writeFileSync(path.join(outDir, 'qa.json'), JSON.stringify({ ok: all.length === 0, issues: all, files: files.map((f) => path.basename(f)) }, null, 2));
  if (all.length) { console.log('카드 점검 실패:\n- ' + all.join('\n- ')); process.exit(1); }
  console.log(`카드 ${files.length}장 점검 통과 → ${path.relative(ROOT, outDir)}`);
})().catch((e) => { console.error(e.message); process.exit(1); });
