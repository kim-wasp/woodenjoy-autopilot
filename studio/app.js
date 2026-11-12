// 콘텐츠 스튜디오 화면 (프레임워크 없이 동작)
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const PF = { blog: '블로그', instagram: '인스타', threads: '스레드' };
const DAYS = [['mon', '월'], ['tue', '화'], ['wed', '수'], ['thu', '목'], ['fri', '금'], ['sat', '토'], ['sun', '일']];
const app = $('#app');
let SITES = null;

function toast(msg) { const t = $('#toast'); t.textContent = msg; t.classList.add('on'); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), 3200); }
async function api(path, opts = {}) {
  const r = await fetch('/api/' + path, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401) { renderLogin(); throw new Error('login'); }
  if (!r.ok) throw new Error(j.error || `오류 ${r.status}`);
  return j;
}
const fmt = (iso) => { if (!iso) return ''; const d = new Date(iso); return `${d.getMonth() + 1}/${d.getDate()}(${'일월화수목금토'[d.getDay()]}) ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
async function sites(force) { if (!SITES || force) SITES = (await api('sites')).sites; return SITES; }
const siteName = (id) => (SITES || []).find((s) => s.id === id)?.name || id;

// ---------- 로그인 ----------
function renderLogin() {
  app.innerHTML = `<div class="login"><div class="card"><h1>콘텐츠 스튜디오</h1><p class="muted small">블로그·인스타·스레드 자동화 관리화면</p>
  <form id="lf"><label class="f"><span>비밀번호</span><input type="password" id="pw" autocomplete="current-password" autofocus></label>
  <button class="btn primary" style="width:100%">들어가기</button><p id="le" class="small" style="color:var(--bad);min-height:20px"></p></form></div></div>`;
  $('#lf').onsubmit = async (e) => {
    e.preventDefault();
    const r = await fetch('/api/auth', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password: $('#pw').value }) });
    if (r.ok) { location.hash = '#/home'; route(); } else $('#le').textContent = (await r.json()).error || '로그인 실패';
  };
}

// ---------- 틀 ----------
const NAV = [['home', '홈'], ['review', '승인 대기'], ['create', '만들기'], ['ideas', '글감'], ['trends', '트렌드'], ['schedule', '일정'], ['cards', '앱 카드'], ['coupang', '쿠팡 링크'], ['sites', '사이트'], ['guide', '연결 가이드']];
function shell(active, inner) {
  app.innerHTML = `<header class="top"><div class="in"><div class="logo">콘텐츠 스튜디오</div>
    <nav class="tabs">${NAV.map(([k, v]) => `<a href="#/${k}" class="${k === active ? 'on' : ''}">${v}</a>`).join('')}</nav>
    <div class="spacer"></div><button class="ghost small" id="out">로그아웃</button></div></header>
    <main class="wrap" id="main">${inner}</main>`;
  $('#out').onclick = async () => { await fetch('/api/auth', { method: 'DELETE' }); renderLogin(); };
}
const loading = (t) => `<div class="empty">${t || '불러오는 중…'}</div>`;

// ---------- 홈 ----------
async function viewHome() {
  shell('home', loading());
  const [rv, sc, rn, st, cp] = await Promise.all([api('reviews'), api('schedule'), api('run'), sites(), api('coupang').catch(() => ({ items: [] }))]);
  const need = (cp.items || []).filter((x) => !x.url), have = (cp.items || []).filter((x) => x.url);
  const planned = (sc.items || []).filter((x) => x.state === 'planned').slice(0, 6);
  $('#main').innerHTML = `<div class="page-h"><h1>오늘 할 일</h1></div>
  <div class="grid g2">
    <a class="card" href="#/coupang" style="color:inherit"><h2>쿠팡 링크</h2><div class="stat">${need.length}<span class="small muted"> 개 필요</span></div><p class="muted small">${need.length ? '글에 넣을 상품 링크를 만들어 주세요 · ' : ''}등록된 링크 ${have.length}개</p></a>
    <a class="card" href="#/review" style="color:inherit"><h2>승인 대기</h2><div class="stat">${rv.items.length}<span class="small muted"> 편</span></div><p class="muted small">확인하고 승인하면 정해진 시간에 올라가요</p></a>
    <div class="card"><h2>다음 업로드</h2><div class="list">${planned.map((x) => `<div class="item"><span class="pf">${PF[x.platform]}</span><div class="t"><b>${esc(x.title)}</b><span class="small muted">${esc(x.site_name)} · ${fmt(x.at)}</span></div></div>`).join('') || '<p class="muted small">예정된 업로드가 없어요</p>'}</div></div>
    <div class="card"><h2>최근 실행</h2><div class="list">${rn.runs.map((r) => `<a class="item" href="${esc(r.url)}" target="_blank" rel="noopener"><div class="t"><b>${esc(r.name)}</b><span class="small muted">${fmt(r.created)}</span></div>${runChip(r)}</a>`).join('') || '<p class="muted small">기록 없음</p>'}</div></div>
    <div class="card"><h2>사이트</h2><div class="list">${st.filter((s) => !s.id.startsWith('_')).map((s) => `<a class="item" href="#/sites/${s.id}" style="color:inherit"><div class="t"><b>${esc(s.name)}</b><span class="small muted">${platforms(s).join(' · ') || '연결 없음'}</span></div>${s.legacy ? '<span class="chip warn">기존 방식</span>' : s.enabled ? '<span class="chip ok">사용</span>' : '<span class="chip">꺼짐</span>'}</a>`).join('')}</div></div>
  </div>`;
}
const runChip = (r) => r.status !== 'completed' ? '<span class="chip warn">진행 중</span>' : r.conclusion === 'success' ? '<span class="chip ok">성공</span>' : `<span class="chip bad">${esc(r.conclusion || '실패')}</span>`;
const platforms = (s) => [s.blog?.platform && s.blog.platform !== 'none' ? ({ naver: '네이버', wordpress: '워드프레스', appblog: '앱 블로그', static: '독립 블로그' }[s.blog.platform]) : null, s.instagram?.enabled ? '인스타' : null, s.threads?.enabled ? '스레드' : null].filter(Boolean);

// ---------- 승인 대기 ----------
async function viewReviewList() {
  shell('review', loading());
  await sites();
  const { items } = await api('reviews');
  $('#main').innerHTML = `<div class="page-h"><h1>승인 대기</h1><a class="btn" href="#/create">새로 만들기</a></div>
  <div class="card"><div class="list">${items.map((x) => `<a class="item" href="#/review/${encodeURIComponent(x.n)}" style="color:inherit">
    <div class="t"><b>${esc(x.title)}</b><span class="small muted">${esc(siteName(x.site))} · ${fmt(x.created)}</span></div>
    ${x.ok ? '<span class="chip ok">점검 통과</span>' : '<span class="chip bad">점검 실패</span>'}</a>`).join('') || '<div class="empty">승인을 기다리는 글이 없어요</div>'}</div></div>`;
}

async function viewReview(n) {
  shell('review', loading());
  await sites();
  const d = await api('reviews?n=' + encodeURIComponent(n));
  const p = d.post, site = SITES.find((s) => s.id === p.site) || {};
  const tabs = [];
  if (d.html) tabs.push(['blog', '블로그']);
  if (p.instagram) tabs.push(['ig', '인스타']);
  if (p.threads) tabs.push(['th', '스레드']);
  tabs.push(['qa', '점검·근거']);
  const link = site.url || '';
  const panes = {
    blog: () => `<div class="card"><div class="article"><h1 style="font-size:26px;margin-bottom:6px">${esc(p.title)}</h1><p class="muted small">${esc(p.meta_description || '')}</p>${p.conclusion ? `<div class="card" style="margin:12px 0"><b class="small">한 줄 결론</b><p style="margin-top:4px">${esc(p.conclusion)}</p></div>` : ''}${d.html}</div></div>`,
    ig: () => `<div class="card"><div class="carousel">${d.cards.map((u, i) => `<img src="${esc(u)}" alt="카드 ${i + 1}">`).join('')}</div><div class="caption">${esc(p.instagram.caption)}</div>${p.instagram.framework || (p.instagram.cover_hooks || []).length ? `<p class="small muted" style="margin-top:10px">${p.instagram.framework ? `구성: ${esc(p.instagram.framework)}<br>` : ''}${(p.instagram.cover_hooks || []).length ? `표지 후보: ${p.instagram.cover_hooks.map(esc).join(' / ')}<br>다른 후보로 바꾸려면 아래 '고칠 점'에 적고 다시 만들기를 눌러 주세요.` : ''}</p>` : ''}</div>`,
    th: () => `<div class="card"><div class="thread">${p.threads.posts.map((t, i) => `${i ? '<div class="tline"></div>' : ''}<div class="tpost"><div class="av">${esc((site.threads?.handle || 'T')[0].toUpperCase())}</div><div class="tx"><b class="small">@${esc(site.threads?.handle || '')}</b><br>${esc(t).replace('{LINK}', `<span class="lk">${esc(link)}</span>`)}${i === 0 && p.threads.topic_tag ? `<br><span class="small muted">주제 태그: ${esc(p.threads.topic_tag)}</span>` : ''}</div></div>`).join('')}</div>${(p.threads.hooks || []).length ? `<p class="small muted" style="margin-top:10px">첫 줄 후보: ${p.threads.hooks.map(esc).join(' / ')}<br>다른 후보로 바꾸려면 아래 '고칠 점'에 적고 다시 만들기를 눌러 주세요.</p>` : ''}</div>`,
    qa: () => `<div class="grid g2"><div class="card"><h2>점검 결과</h2>${(p.checks?.issues || []).length ? `<ul class="issues">${p.checks.issues.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : '<p><span class="chip ok">모두 통과</span></p>'}</div>
      <div class="card"><h2>이 주제를 고른 이유</h2><p>${esc(p.why_this_topic || '-')}</p><p class="small muted">핵심 키워드: ${esc(p.keywords?.main || '-')} · ${esc((p.keywords?.sub || []).join(', '))}</p>
      ${p.cost ? `<p class="small" style="margin-top:10px"><b>만드는 데 든 비용(추정)</b> 약 ${Number(p.cost.total_krw || 0).toLocaleString()}원 · ${Object.entries(p.cost.claude || {}).map(([m, u]) => `Claude 입력 ${Number(u.input_tokens).toLocaleString()} / 출력 ${Number(u.output_tokens).toLocaleString()} 토큰, 웹 검색 ${u.web_searches}회`).join(' · ')}${Object.entries(p.cost.images || {}).map(([m, u]) => ` · 사진 ${u.count}장(${esc(m)})`).join('')}</p>` : ''}</div>
      <div class="card"><h2>브리프</h2><p class="small">독자: ${esc(p.brief?.reader)}<br>질문: ${esc(p.brief?.question)}<br>핵심 답: ${esc(p.brief?.answer)}<br>다루지 않음: ${esc(p.brief?.out_of_scope)}</p></div>
      <div class="card"><h2>출처</h2>${(p.sources || []).length ? `<ul>${p.sources.map((s) => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.title)}</a></li>`).join('')}</ul>` : '<p class="muted small">출처 없음 (숫자·통계가 없는 글이어야 해요)</p>'}</div></div>`,
  };
  $('#main').innerHTML = `<div class="page-h"><div><p class="muted small">${esc(site.name || p.site)}${d.pr ? ` · <a href="${esc(d.pr.url)}" target="_blank" rel="noopener">GitHub에서 보기</a>` : ''}</p><h1>${esc(p.title)}</h1></div></div>
  <div class="seg" id="seg">${tabs.map(([k, v], i) => `<button data-k="${k}" class="${i ? '' : 'on'}">${v}</button>`).join('')}</div>
  <div id="pane">${panes[tabs[0][0]]()}</div>
  ${site.opinion ? `<div class="actions"><label class="f" style="margin-bottom:10px"><span>편집자 생각 (사장님 의견, 글 끝에 '편집자 생각'으로 붙어요. 비우고 누르면 칸을 빼요)</span><textarea id="opinion" rows="5" placeholder="예: 이 법안은 취지는 좋지만 재원 대책이 없어서 반대해요. 특히 ...">${esc(p.opinion || '')}</textarea></label>
  <div class="btns"><button class="btn" id="op">의견 넣기</button></div></div>` : ''}
  <div class="actions"><label class="f" style="margin-bottom:10px"><span>고칠 점 (다시 만들기 때 반영)</span><textarea id="notes" placeholder="예: 첫 줄을 더 세게, 3번 카드 문구를 짧게"></textarea></label>
  <div class="btns"><button class="btn primary" id="ok">승인하기</button><button class="btn" id="redo">다시 만들기</button><button class="btn danger" id="no">버리기</button></div></div>`;
  $('#seg').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; [...$('#seg').children].forEach((x) => x.classList.toggle('on', x === b)); $('#pane').innerHTML = panes[b.dataset.k](); };
  const act = async (action, msg) => {
    try {
      const r = await api('reviews', { method: 'POST', body: { n: d.pr ? d.pr.n : n, action, notes: $('#notes').value, topic: p.requested_topic || p.title } });
      if (r && r.next_ideas) { toast('승인했어요. 다음 글 이슈 후보를 받는 중이에요 (2~3분). 글감에서 골라 견해를 써 주세요'); location.hash = '#/ideas/' + r.next_ideas; return; }
      toast(msg); location.hash = '#/review';
    } catch (e) { if (e.message !== 'login') toast(e.message); }
  };
  $('#ok').onclick = () => { if (p.checks && !p.checks.ok && !confirm('점검에 실패한 글이에요. 그래도 승인할까요?')) return; act('approve', '승인했어요. 정해진 시간에 올라가요'); };
  if ($('#op')) $('#op').onclick = async () => {
    try { await api('reviews', { method: 'POST', body: { n: d.pr ? d.pr.n : n, action: 'opinion', notes: $('#opinion').value, topic: p.title } }); toast('의견을 넣는 중이에요. 2~3분 뒤 블로그 탭 맨 아래에서 볼 수 있어요'); location.hash = '#/review'; } catch (e) { if (e.message !== 'login') toast(e.message); }
  };
  $('#redo').onclick = () => act('redo', '다시 만드는 중이에요. 5~10분 뒤 이 화면에서 바뀐 내용을 볼 수 있어요');
  $('#no').onclick = () => { if (confirm('이 글을 버릴까요?')) act('reject', '버렸어요'); };
}

// ---------- 만들기 ----------
async function viewCreate(pre = {}) {
  shell('create', loading());
  const st = (await sites()).filter((s) => s.enabled && !s.legacy && !s.id.startsWith('_'));
  const { runs } = await api('run');
  $('#main').innerHTML = `<div class="page-h"><h1>글 만들기</h1></div>
  <div class="grid g2"><form class="card" id="cf">
    <label class="f"><span>사이트</span><select id="site">${st.map((s) => `<option value="${s.id}" ${pre.site === s.id ? 'selected' : ''}>${esc(s.name)}</option>`).join('')}</select></label>
    <label class="f"><span>주제나 제목 (비우면 검색량·시기를 보고 자동으로 골라요)</span><input type="text" id="topic" value="${esc(pre.topic || '')}" placeholder="예: 축의금 얼마가 적당할까"></label>
    <div id="viewbox"></div>
    <label class="f"><span>추가 요청 (선택)</span><textarea id="cnotes" placeholder="예: 20대 사회초년생 눈높이로"></textarea></label>
    <button class="btn primary" ${st.length ? '' : 'disabled'}>만들기 시작</button>
    <p class="small muted" style="margin-top:10px">글 → 대표 사진 → 카드 → 인스타·스레드 → 점검까지 5~10분 걸려요. 끝나면 <a href="#/review">승인 대기</a>에 올라와요.</p>
  </form>
  <div class="card"><h2>최근 실행</h2><div class="list">${runs.map((r) => `<a class="item" href="${esc(r.url)}" target="_blank" rel="noopener"><div class="t"><b>${esc(r.name)}</b><span class="small muted">${fmt(r.created)} · ${r.event === 'schedule' ? '예약' : '직접'}</span></div>${runChip(r)}</a>`).join('') || '<p class="muted small">기록 없음</p>'}</div></div></div>`;
  const viewBox = () => {
    const s = st.find((x) => x.id === $('#site').value) || {};
    $('#viewbox').innerHTML = s.opinion ? `${pre.idea ? `<div class="card" style="margin-bottom:12px"><p class="small"><b>핵심 사실</b> ${esc(pre.idea.facts || '')}</p><p class="small" style="margin-top:6px"><b>양쪽 입장</b> ${esc(pre.idea.sides || '')}</p>${pre.idea.question ? `<p class="small" style="margin-top:6px"><b>생각해 볼 질문</b> ${esc(pre.idea.question)}</p>` : ''}</div>` : ''}
      <label class="f"><span>내 견해 (이걸 바탕으로 글을 써요. 글 끝 '편집자 생각'에 쉬운 말로 줄여 들어가요)</span><textarea id="view" rows="8" placeholder="이 이슈에 대한 사장님 생각을 편하게 적어 주세요. 길어도 괜찮아요.">${esc(pre.view || '')}</textarea></label>` : '';
  };
  viewBox();
  $('#site').onchange = viewBox;
  $('#cf').onsubmit = async (e) => {
    e.preventDefault();
    const s = st.find((x) => x.id === $('#site').value) || {};
    if (s.opinion && !($('#view')?.value || '').trim() && !confirm('견해 없이 만들까요? (편집자 생각 칸 없이 사실 정리만 나와요)')) return;
    try { await api('run', { method: 'POST', body: { site: $('#site').value, topic: $('#topic').value, notes: $('#cnotes').value, view: $('#view')?.value || '' } }); toast('만들기 시작! 5~10분 뒤 승인 대기를 확인하세요'); setTimeout(() => viewCreate(), 4000); } catch (e2) { if (e2.message !== 'login') toast(e2.message); }
  };
}

// ---------- 글감 ----------
async function viewIdeas(siteId) {
  shell('ideas', loading());
  const st = (await sites()).filter((s) => s.enabled && !s.legacy && !s.id.startsWith('_'));
  siteId = siteId || st[0]?.id;
  const one = siteId ? (await api(`sites?ideas=1&id=${siteId}`)).sites.find((s) => s.id === siteId) : null;
  const ideas = one?._ideas?.ideas || [];
  $('#main').innerHTML = `<div class="page-h"><h1>글감</h1><button class="btn" id="more">새로 추천받기</button></div>
  <div class="seg">${st.map((s) => `<button class="${s.id === siteId ? 'on' : ''}" data-id="${s.id}">${esc(s.name)}</button>`).join('')}</div>
  <div class="card"><p class="small muted">${one?._ideas?.updated ? `추천 시각 ${fmt(one._ideas.updated)} · ${one.opinion ? `${esc(one._ideas.basis || '최근 보도')} 기준으로 골랐어요${one._ideas.cost ? ` (비용 약 ${Number(one._ideas.cost.total_krw || 0).toLocaleString()}원)` : ''}. 하나 골라 견해를 쓰면 그걸 바탕으로 글을 만들어요` : '웹 검색과 네이버 검색량을 보고 골랐어요'}` : '아직 추천받은 글감이 없어요. [새로 추천받기]를 눌러 주세요 (2~3분).'}</p>
  ${one?.opinion ? `<form class="card" id="myf" style="margin-bottom:12px"><label class="f"><span>내 글감으로 조사받기 (주제나 이슈를 한 줄로 적으면 관련 기사와 근거를 찾아 아래 목록 맨 위에 넣어요, 2~4분)</span><input type="text" id="mytopic" placeholder="예: 의대 정원 다시 늘린다는데 이번엔 뭐가 다른가"></label><button class="btn primary">근거 찾아오기</button></form>` : ''}
  <div class="list">${ideas.map((x, i) => `<div class="item"><div class="t"><b>${x.mine ? '<span class="chip ok">내 글감</span> ' : ''}${esc(x.title)}</b><span class="small muted">${esc(x.keyword)} · ${esc(x.why)}</span>${x.facts ? `<span class="small" style="margin-top:4px">${esc(x.facts)}</span><span class="small muted">${esc(x.sides || '')}</span>` : ''}${(x.links || []).length ? `<span class="small">${x.links.map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a>`).join('<br>')}</span>` : ''}</div><button class="btn" data-i="${i}">${one?.opinion ? '고르고 견해 쓰기' : '이걸로 만들기'}</button></div>`).join('')}</div></div>`;
  $('.seg').onclick = (e) => { const b = e.target.closest('button'); if (b) viewIdeas(b.dataset.id); };
  $('#main').querySelectorAll('[data-i]').forEach((b) => { b.onclick = () => viewCreate({ site: siteId, topic: ideas[b.dataset.i].title, idea: ideas[b.dataset.i] }); });
  if ($('#myf')) $('#myf').onsubmit = async (e) => { e.preventDefault(); const t = $('#mytopic').value.trim(); if (!t) return; try { await api('run', { method: 'POST', body: { site: siteId, mode: 'ideas', topic: t } }); toast('근거 찾는 중이에요. 2~4분 뒤 새로고침하세요'); $('#mytopic').value = ''; } catch (e2) { if (e2.message !== 'login') toast(e2.message); } };
  $('#more').onclick = async () => { try { await api('run', { method: 'POST', body: { site: siteId, mode: 'ideas' } }); toast('추천 받는 중이에요. 2~3분 뒤 새로고침하세요'); } catch (e) { if (e.message !== 'login') toast(e.message); } };
}

// ---------- 트렌드 메모 (네이버 크리에이터 어드바이저) ----------
async function viewTrends() {
  shell('trends', loading());
  const d = await api('trends');
  const fresh = (e) => (Date.now() - new Date(e.at)) / 864e5 <= 7;
  const st = await sites();
  const name = (id) => (st.find((x) => x.id === id) || {}).name || id;
  const a = d.auto;
  const autoHtml = a ? `<div class="card"><h2>자동 감지 (매일 아침 5시)</h2><p class="small muted">${fmt(a.updated)} 기준 · 네이버 검색광고 키워드 도구로 사이트별 분야 검색어의 최근 30일 검색 수를 매일 재서 7일 전보다 크게 는 것, 그리고 구글 실시간 인기 검색어예요. 글감 추천과 글쓰기에 자동으로 들어가요. 기록이 7일 쌓이기 전에는 쌓인 날짜끼리 비교해요.</p>
    ${Object.entries(a.sites || {}).map(([id, v]) => `<h3 style="margin-top:14px">${esc(name(id))}</h3><p class="small">${(v.rising || []).length ? v.rising.slice(0, 12).map((x) => `<b>${esc(x.keyword)}</b> ${x.before ? `${x.before.toLocaleString()}→${x.now.toLocaleString()} (+${Math.round(x.change * 100)}%)` : `${x.now.toLocaleString()} (새로 등장)`}`).join(' / ') : '<span class="muted">아직 급등 없음 (기록 ' + (v.days || 1) + '일째)</span>'}</p><p class="small muted">검색 많은 말: ${(v.top || []).slice(0, 10).map((x) => esc(x.keyword) + ' ' + x.now.toLocaleString()).join(', ')}</p>`).join('')}
    <h3 style="margin-top:14px">구글 실시간 인기 검색어</h3><p class="small">${(a.google || []).slice(0, 15).map((x) => `${esc(x.keyword)} <span class="muted">${esc(x.traffic)}</span>`).join(' / ') || '<span class="muted">못 읽음</span>'}</p></div>` : '<div class="card"><p class="small muted">자동 감지 결과가 아직 없어요. 매일 아침 5시에 만들어져요.</p></div>';
  $('#main').innerHTML = `<div class="page-h"><h1>트렌드</h1></div>${autoHtml}
  <div class="grid g2"><form class="card" id="tf"><h2>직접 추가 (선택)</h2>
    <p class="small muted">크리에이터 어드바이저에서 눈에 띄는 검색어가 있을 때만 붙여넣어 주세요. 자동 감지와 함께 참고해요. 한 줄에 하나, 순위 숫자는 있어도 괜찮아요. 최근 7일 안에 넣은 검색어를 모든 사이트의 글감 고르기와 글쓰기에 참고해요 (글과 관련 있을 때만 자연스럽게).</p>
    <label class="f"><span>어디서 본 검색어인지 (선택)</span><input type="text" id="tlabel" placeholder="예: 생활·건강 인기유입 / 급등"></label>
    <label class="f"><span>검색어</span><textarea id="ttext" rows="10" placeholder="1 독감 예방접종\n2 수능 도시락\n3 김장 김치"></textarea></label>
    <button class="btn primary">저장</button>
  </form>
  <div class="card"><h2>저장된 검색어</h2><div class="list">${(d.entries || []).map((e) => `<div class="item"><div class="t"><b>${fmt(e.at)}${e.label ? ' · ' + esc(e.label) : ''}</b><span class="small ${fresh(e) ? '' : 'muted'}">${e.keywords.map(esc).join(', ')}</span>${fresh(e) ? '' : '<span class="small muted">7일 지나서 이제 참고하지 않아요</span>'}</div><button class="btn" data-at="${esc(e.at)}">지우기</button></div>`).join('') || '<p class="muted small">아직 없어요</p>'}</div></div></div>`;
  $('#tf').onsubmit = async (e) => { e.preventDefault(); try { const r = await api('trends', { method: 'POST', body: { text: $('#ttext').value, label: $('#tlabel').value } }); toast(`검색어 ${r.count}개 저장했어요`); viewTrends(); } catch (e2) { if (e2.message !== 'login') toast(e2.message); } };
  $('#main').querySelectorAll('[data-at]').forEach((b) => { b.onclick = async () => { try { await api('trends', { method: 'DELETE', body: { at: b.dataset.at } }); viewTrends(); } catch (e2) { if (e2.message !== 'login') toast(e2.message); } }; });
}

// ---------- 일정 ----------
async function viewSchedule() {
  shell('schedule', loading());
  const sc = await api('schedule');
  const pad = (n) => String(n).padStart(2, '0');
  const dkey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const today = dkey(new Date());
  const by = {};
  (sc.items || []).forEach((x) => { const k = dkey(new Date(x.at)); (by[k] = by[k] || []).push(x); });
  Object.values(by).forEach((l) => l.sort((a, b) => a.at.localeCompare(b.at)));
  const row = (x) => `<div class="item"><span class="pf">${PF[x.platform]}</span><div class="t"><b>${esc(x.title)}</b><span class="small muted">${esc(x.site_name)} · ${fmt(x.at).split(' ')[1]}</span></div>${x.state === 'done' ? (x.url ? `<a class="chip ok" href="${esc(x.url)}" target="_blank" rel="noopener">올라감 ↗</a>` : '<span class="chip ok">올라감</span>') : '<span class="chip brand">예정</span>'}</div>`;
  const day = (k) => `<div class="day-h">${fmt(k + 'T00:00').split(' ')[0]}${k === today ? ' 오늘' : ''}</div><div class="list">${by[k].map(row).join('')}</div>`;
  // 지난 날짜는 주(월~일) 단위로 묶어 접어 둬요. 'n주차'는 그 주 목요일이 속한 달 기준
  const weekOf = (k) => {
    const d = new Date(k + 'T00:00'); const mon = new Date(d); mon.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const thu = new Date(mon); thu.setDate(mon.getDate() + 3); const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    return { id: dkey(mon), label: `${thu.getFullYear()}년 ${thu.getMonth() + 1}월 ${Math.ceil(thu.getDate() / 7)}주차`, range: `${mon.getMonth() + 1}/${mon.getDate()}~${sun.getMonth() + 1}/${sun.getDate()}` };
  };
  const keys = Object.keys(by).sort();
  const upcoming = keys.filter((k) => k >= today);
  const weeks = {};
  keys.filter((k) => k < today).forEach((k) => { const w = weekOf(k); (weeks[w.id] = weeks[w.id] || { ...w, days: [] }).days.push(k); });
  const past = Object.values(weeks).sort((a, b) => b.id.localeCompare(a.id));
  const count = (ds) => ds.reduce((n, k) => n + by[k].length, 0);
  $('#main').innerHTML = `<div class="page-h"><h1>일정</h1><span class="small muted">${sc.updated ? '갱신 ' + fmt(sc.updated) : ''}</span></div>
  <div class="card"><div class="sec">오늘과 다가오는 일정</div>${upcoming.map(day).join('') || '<p class="muted small">예정된 일정이 없어요. 글을 승인하면 여기에 보여요.</p>'}</div>
  ${past.length ? `<div class="card"><div class="sec">지난 일정</div>${past.map((w) => `<details class="week"><summary><b>${w.label}</b><span class="small muted">${w.range} · ${count(w.days)}건</span></summary>${w.days.slice().reverse().map(day).join('')}</details>`).join('')}</div>` : ''}`;
}

// ---------- 사이트 ----------
async function viewSites() {
  shell('sites', loading());
  const st = await sites(true);
  $('#main').innerHTML = `<div class="page-h"><h1>사이트</h1><a class="btn" href="#/sites/_new">사이트 추가</a></div>
  <div class="grid g2">${st.filter((s) => !s.id.startsWith('_')).map((s) => `<a class="card" href="#/sites/${s.id}" style="color:inherit"><div class="btns" style="justify-content:space-between"><h2>${esc(s.name)}</h2>${s.legacy ? '<span class="chip warn">기존 방식</span>' : s.enabled ? '<span class="chip ok">사용</span>' : '<span class="chip">꺼짐</span>'}</div>
    <p class="small muted">${esc(s.url || '')}</p><p class="small">${platforms(s).map((x) => `<span class="chip">${x}</span>`).join(' ')}</p>
    <p class="small muted">글 만들기: ${daysText(s.schedule?.generate)}</p></a>`).join('')}</div>`;
}
const daysText = (g) => g ? `${g.days.map((d) => DAYS.find((x) => x[0] === d)?.[1]).join('·')} ${g.time}` : '-';
const daysPicker = (name, sel = []) => `<div class="days">${DAYS.map(([k, v]) => `<label class="${sel.includes(k) ? 'on' : ''}"><input type="checkbox" name="${name}" value="${k}" ${sel.includes(k) ? 'checked' : ''}>${v}</label>`).join('')}</div>`;

async function viewSite(id) {
  shell('sites', loading());
  const st = await sites(true);
  const isNew = id === '_new';
  const s = JSON.parse(JSON.stringify(isNew ? st.find((x) => x.id === '_template') || {} : st.find((x) => x.id === id)));
  if (!s) { $('#main').innerHTML = '<div class="empty">없는 사이트예요</div>'; return; }
  s.blog = s.blog || { platform: 'none' }; s.blog.wordpress = s.blog.wordpress || {}; s.instagram = s.instagram || {}; s.threads = s.threads || {};
  s.schedule = s.schedule || {}; s.schedule.generate = s.schedule.generate || { days: [], time: '20:00' }; s.schedule.slots = s.schedule.slots || {};
  ['blog', 'threads', 'instagram'].forEach((p) => { s.schedule.slots[p] = s.schedule.slots[p] || { days: ['mon', 'wed', 'fri'], time: p === 'blog' ? '07:00' : p === 'threads' ? '12:30' : '21:00' }; });
  s.monetization = s.monetization || { coupang: {} }; s.monetization.coupang = s.monetization.coupang || {}; s.app = s.app || {}; s.llm = s.llm || {}; s.images = s.images || { hero: {} }; s.images.hero = s.images.hero || {}; s.brand = s.brand || { colors: {} }; s.brand.colors = s.brand.colors || {}; s.rules = s.rules || {};
  const v = (x) => esc(x ?? '');
  $('#main').innerHTML = `<div class="page-h"><h1>${isNew ? '사이트 추가' : esc(s.name)}</h1>${s.legacy ? '<span class="chip warn">기존 우드엔조이 방식으로 운영 중</span>' : ''}</div>
  <form id="sf" class="grid g2">
  <div class="card"><div class="sec">기본</div>
    ${isNew ? `<label class="f"><span>사이트 id (영문, 예: forsmartlife)</span><input type="text" id="sid" required pattern="[a-z0-9][a-z0-9-]{1,30}"></label>` : ''}
    <label class="f"><span>이름</span><input type="text" data-k="name" value="${v(s.name)}"></label>
    <label class="f"><span><input type="checkbox" data-k="enabled" ${s.enabled ? 'checked' : ''}> 이 사이트 자동화 사용</span></label>
    ${s.legacy !== undefined ? `<label class="f"><span><input type="checkbox" data-k="legacy" ${s.legacy ? 'checked' : ''}> 기존 우드엔조이 자동화로 계속 운영 (체크를 풀면 스튜디오로 전환)</span></label>` : ''}
    <label class="f"><span>사이트 주소 (SNS 링크로도 써요)</span><input type="text" data-k="url" value="${v(s.url)}"></label>
    <label class="f"><span>주제</span><textarea data-k="topic">${v(s.topic)}</textarea></label>
    <label class="f"><span>독자</span><input type="text" data-k="audience" value="${v(s.audience)}"></label>
    <label class="f"><span>말투</span><input type="text" data-k="tone" value="${v(s.tone)}"></label>
    <label class="f"><span>추가 지시 (글쓰기 규칙·운영자 경험 등)</span><textarea data-k="writing_guide">${v(s.writing_guide)}</textarea></label>
    <label class="f"><span>글감 후보 키워드 (쉼표로)</span><input type="text" data-k="seeds" data-type="list" value="${v((s.seeds || []).join(', '))}"></label>
  </div>
  <div class="card"><div class="sec">기본 채널</div>
    <label class="f"><span>기본 채널 (여기에 인스타·스레드를 더할지 아래에서 골라요)</span><select data-k="blog.platform"><option value="none">블로그 없음 (커먼센스처럼 앱·사이트로 유입)</option><option value="wordpress" ${s.blog.platform === 'wordpress' ? 'selected' : ''}>워드프레스</option><option value="naver" ${s.blog.platform === 'naver' ? 'selected' : ''}>네이버 (uplika)</option><option value="appblog" ${s.blog.platform === 'appblog' ? 'selected' : ''}>앱 안의 블로그 (커먼센스 /blog)</option><option value="static" ${s.blog.platform === 'static' ? 'selected' : ''}>독립 블로그 (GitHub → Cloudflare)</option></select></label>
    <label class="f"><span>블로그 주소</span><input type="text" data-k="blog.url" value="${v(s.blog.url)}"></label>
    <div class="row2"><label class="f"><span>워드프레스 사용자명</span><input type="text" data-k="blog.wordpress.user" value="${v(s.blog.wordpress.user)}"></label>
    <label class="f"><span>앱 비밀번호의 비밀키 이름</span><input type="text" data-k="blog.wordpress.app_password_secret" value="${v(s.blog.wordpress.app_password_secret)}"></label></div>
    <div class="row2"><label class="f"><span>카테고리</span><input type="text" data-k="blog.wordpress.category" value="${v(s.blog.wordpress.category)}"></label>
    <label class="f"><span>발행 상태</span><select data-k="blog.wordpress.status"><option value="publish">바로 공개</option><option value="draft" ${s.blog.wordpress.status === 'draft' ? 'selected' : ''}>임시글로</option></select></label></div>
    <div class="row2"><label class="f"><span>최소 글자</span><input type="number" data-k="rules.min_chars" data-type="num" value="${v(s.rules.min_chars)}"></label><label class="f"><span>최대 글자</span><input type="number" data-k="rules.max_chars" data-type="num" value="${v(s.rules.max_chars)}"></label></div>
    <div class="sec">더할 SNS (선택)</div>
    <label class="f"><span><input type="checkbox" data-k="instagram.enabled" ${s.instagram.enabled ? 'checked' : ''}> 인스타 사용</span></label>
    <div class="row2"><label class="f"><span>인스타 계정</span><input type="text" data-k="instagram.handle" value="${v(s.instagram.handle)}"></label><label class="f"><span>토큰 비밀키 이름</span><input type="text" data-k="instagram.token_secret" value="${v(s.instagram.token_secret)}"></label></div>
    <label class="f"><span><input type="checkbox" data-k="threads.enabled" ${s.threads.enabled ? 'checked' : ''}> 스레드 사용</span></label>
    <div class="row2"><label class="f"><span>스레드 계정</span><input type="text" data-k="threads.handle" value="${v(s.threads.handle)}"></label><label class="f"><span>토큰 비밀키 이름</span><input type="text" data-k="threads.token_secret" value="${v(s.threads.token_secret)}"></label></div>
  </div>
  <div class="card"><div class="sec">일정 (한국 시간)</div>
    <label class="f"><span>글 만들기 (만들어서 승인 요청)</span>${daysPicker('g', s.schedule.generate.days)}<input type="time" id="gt" value="${v(s.schedule.generate.time)}" style="margin-top:8px;max-width:140px"></label>
    ${['blog', 'threads', 'instagram'].map((p) => `<label class="f"><span>${PF[p]} 업로드</span>${daysPicker('d_' + p, s.schedule.slots[p].days)}<input type="time" id="t_${p}" value="${v(s.schedule.slots[p].time)}" style="margin-top:8px;max-width:140px"></label>`).join('')}
    <label class="f"><span><input type="checkbox" data-k="approval" ${s.approval !== false ? 'checked' : ''}> 올리기 전에 승인 받기</span></label>
  </div>
  <div class="card"><div class="sec">글·이미지 엔진</div>
    <label class="f"><span>글 모델</span><select data-k="llm.model"><option value="claude-opus-5-5">Claude Opus 5.5 (품질 우선)</option><option value="claude-sonnet-5-5" ${s.llm.model === 'claude-sonnet-5-5' ? 'selected' : ''}>Claude Sonnet 5.5 (빠르고 저렴)</option></select></label>
    <label class="f"><span><input type="checkbox" data-k="llm.web_search" ${s.llm.web_search !== false ? 'checked' : ''}> 쓰기 전에 웹 검색으로 최신 자료 확인</span></label>
    <label class="f"><span>대표 사진 만들기</span><select data-k="images.hero.provider"><option value="openai">OpenAI 이미지</option><option value="gemini" ${s.images.hero.provider === 'gemini' ? 'selected' : ''}>Google Gemini 이미지</option><option value="none" ${s.images.hero.provider === 'none' ? 'selected' : ''}>만들지 않음</option></select></label>
    <div class="sec">카드 디자인</div>
    <div class="row2"><label class="f"><span>카드 위쪽 문구</span><input type="text" data-k="brand.cardLabel" value="${v(s.brand.cardLabel)}"></label><label class="f"><span>카드 아래 계정</span><input type="text" data-k="brand.handle" value="${v(s.brand.handle)}"></label></div>
    <div class="row2"><label class="f"><span>배경색</span><input type="text" data-k="brand.colors.bg" value="${v(s.brand.colors.bg)}" placeholder="#EEF3FB"></label><label class="f"><span>강조색</span><input type="text" data-k="brand.colors.pine" value="${v(s.brand.colors.pine)}" placeholder="#3182F6"></label></div>
    <div class="row2"><label class="f"><span>제목색</span><input type="text" data-k="brand.colors.deep" value="${v(s.brand.colors.deep)}"></label><label class="f"><span>배지색</span><input type="text" data-k="brand.colors.amber" value="${v(s.brand.colors.amber)}"></label></div>
  </div>
  <div class="card"><div class="sec">수익화</div>
    <label class="f"><span>단계</span><select data-k="monetization.stage">
      <option value="pre_adsense">애드센스 승인 전 (신뢰·독창성 우선, 제휴 링크 없음)</option>
      <option value="adsense" ${s.monetization.stage === 'adsense' ? 'selected' : ''}>애드센스 운영 중 (클릭률·체류시간·내부 링크)</option>
      <option value="adpost" ${s.monetization.stage === 'adpost' ? 'selected' : ''}>네이버 애드포스트 (훅·체류·이미지 많이)</option></select></label>
    <label class="f"><span><input type="checkbox" data-k="monetization.internal_links" ${s.monetization.internal_links !== false ? 'checked' : ''}> 관련 글 내부 링크 넣기</span></label>
    <label class="f"><span><input type="checkbox" data-k="monetization.humanize" ${s.monetization.humanize !== false ? 'checked' : ''}> AI 티 다듬기 (im-not-ai 규칙으로 한 번 더 윤문)</span></label>
    <label class="f"><span><input type="checkbox" data-k="monetization.coupang.enabled" ${s.monetization.coupang?.enabled ? 'checked' : ''}> 쿠팡 파트너스 링크 넣기 (승인 전 단계에서는 자동으로 빠져요)</span></label>
    <label class="f"><span>쿠팡 링크 목록 파일</span><input type="text" data-k="monetization.coupang.links_file" value="${v(s.monetization.coupang?.links_file)}" placeholder="sites/아이디/coupang.json"></label>
  </div>
  <div class="card"><div class="sec">이미지</div>
    <label class="f"><span>블로그 본문 이미지</span><select data-k="images.blog_inline">
      <option value="cards">정보 카드 (코드로 그린 도표·단계)</option>
      <option value="photos" ${s.images.blog_inline === 'photos' ? 'selected' : ''}>AI 사진 (사람·현실 장면)</option>
      <option value="mixed" ${s.images.blog_inline === 'mixed' ? 'selected' : ''}>섞어서 (카드 + 사진)</option>
      <option value="none" ${s.images.blog_inline === 'none' ? 'selected' : ''}>대표 사진만</option></select></label>
    <label class="f"><span>인스타 이미지</span><select data-k="images.instagram">
      <option value="cards">정보 카드뉴스 (지금 방식)</option>
      <option value="photo_cards" ${s.images.instagram === 'photo_cards' ? 'selected' : ''}>사진 카드뉴스 (사진 위에 글자 + 정보 카드 섞기)</option></select></label>
    <label class="f"><span>사진 스타일 (영어로 쓰면 더 정확해요)</span><textarea data-k="images.photo_style" placeholder="예: Realistic documentary photo of Korean adults in everyday life, natural light">${v(s.images.photo_style)}</textarea></label>
    <label class="f"><span>글 한 편당 사진 수</span><input type="number" data-k="images.photos" data-type="num" value="${v(s.images.photos ?? 3)}" min="0" max="6"></label>
  </div>
  <div class="card"><div class="sec">앱 카드 (커먼센스)</div>
    <label class="f"><span>앱 종류</span><select data-k="app.kind"><option value="">없음</option><option value="commonsense" ${s.app.kind === 'commonsense' ? 'selected' : ''}>커먼센스 (사회 이슈로 투표 카드 늘리기)</option></select></label>
    <div class="row2"><label class="f"><span>DB 주소 비밀키 이름</span><input type="text" data-k="app.supabase_url_secret" value="${v(s.app.supabase_url_secret || 'SUPABASE_URL')}"></label>
    <label class="f"><span>DB 키 비밀키 이름</span><input type="text" data-k="app.supabase_key_secret" value="${v(s.app.supabase_key_secret || 'SUPABASE_SERVICE_KEY')}"></label></div>
    <div class="row2"><label class="f"><span>카드 표 이름</span><input type="text" data-k="app.table" value="${v(s.app.table || 'cards')}"></label>
    <label class="f"><span>한 번에 만들 후보 수</span><input type="number" data-k="app.count" data-type="num" value="${v(s.app.count || 10)}"></label></div>
    <details><summary class="small muted">고급: 설정 JSON 직접 고치기</summary><textarea id="raw" style="min-height:220px;font-family:monospace;font-size:12px">${esc(JSON.stringify(s, null, 2))}</textarea><button type="button" class="btn" id="rawsave" style="margin-top:8px">JSON으로 저장</button></details>
  </div>
  <div class="sticky-actions" style="grid-column:1/-1"><div class="btns"><button class="btn primary">저장</button><a class="btn" href="#/sites">취소</a></div></div>
  </form>`;
  $('#sf').querySelectorAll('.days input').forEach((i) => { i.onchange = () => i.parentElement.classList.toggle('on', i.checked); });
  const save = async (obj, sid) => { try { await api('sites', { method: 'PUT', body: { id: sid, site: obj } }); SITES = null; toast('저장했어요'); location.hash = '#/sites'; } catch (e) { if (e.message !== 'login') toast(e.message); } };
  $('#rawsave').onclick = () => { try { save(JSON.parse($('#raw').value), isNew ? $('#sid').value : id); } catch { toast('JSON 형식이 잘못됐어요'); } };
  $('#sf').onsubmit = (e) => {
    e.preventDefault();
    $('#sf').querySelectorAll('[data-k]').forEach((el) => {
      const keys = el.dataset.k.split('.');
      let o = s; keys.slice(0, -1).forEach((k) => { o = o[k] = o[k] || {}; });
      const last = keys[keys.length - 1];
      o[last] = el.type === 'checkbox' ? el.checked : el.dataset.type === 'list' ? el.value.split(',').map((x) => x.trim()).filter(Boolean) : el.dataset.type === 'num' ? Number(el.value) || undefined : el.value;
    });
    const picked = (name) => [...$('#sf').querySelectorAll(`input[name="${name}"]:checked`)].map((x) => x.value);
    s.schedule.generate = { days: picked('g'), time: $('#gt').value };
    ['blog', 'threads', 'instagram'].forEach((p) => { s.schedule.slots[p] = { days: picked('d_' + p), time: $('#t_' + p).value }; });
    if (isNew) delete s.id;
    save(s, isNew ? $('#sid').value : id);
  };
}


// ---------- 쿠팡 링크 ----------
async function viewCoupang() {
  shell('coupang', loading());
  const { items } = await api('coupang');
  const need = items.filter((x) => !x.url), have = items.filter((x) => x.url);
  $('#main').innerHTML = `<div class="page-h"><h1>쿠팡 파트너스 링크</h1></div>
  <p class="muted small">쿠팡 파트너스 → <b>링크 생성</b>(상품 주소 붙여넣기)으로 만든 <b>https://link.coupang.com/…</b> 주소를 넣어 주세요. 링크가 필요한 상품은 글을 만들 때 프로그램이 골라서 여기에 올려요. 아직 안 올라간 글이면 링크를 넣는 순간 그 글 본문에도 들어가요.</p>
  <div class="card"><h2>링크 필요 (${need.length})</h2><div class="list">${need.map((x) => `<div class="item" style="align-items:flex-start;flex-wrap:wrap"><div class="t"><b>${esc(x.name)}</b><span class="small muted">쿠팡 검색어: ${esc(x.search || x.name)} · ${esc(x.status || '')}</span></div>
    <div style="display:flex;gap:6px;width:100%;margin-top:6px"><input type="url" placeholder="https://link.coupang.com/a/..." data-key="${esc(x.key)}" style="flex:1"><button class="btn primary small" data-save="${esc(x.key)}">넣기</button><a class="btn small" href="https://www.coupang.com/np/search?q=${encodeURIComponent(x.search || x.name)}" target="_blank" rel="noopener">쿠팡에서 찾기</a></div></div>`).join('') || '<p class="muted small">지금은 필요한 링크가 없어요</p>'}</div></div>
  <div class="card" style="margin-top:14px"><h2>상품 직접 추가</h2><div class="row2"><label class="f"><span>상품 이름(쇼핑몰 이름 그대로)</span><input id="nn"></label><label class="f"><span>쿠팡 파트너스 링크</span><input id="nu" type="url" placeholder="https://link.coupang.com/a/..."></label></div><div class="btns"><button class="btn primary" id="add">추가</button></div></div>
  <div class="card" style="margin-top:14px"><h2>등록된 링크 (${have.length})</h2><div class="list">${have.map((x) => `<div class="item"><div class="t"><b>${esc(x.name)}</b><span class="small muted">${esc(x.url)}</span></div><button class="ghost small" data-del="${esc(x.key)}">빼기</button></div>`).join('')}</div></div>`;
  const post = async (b) => { try { const r = await api('coupang', { method: 'POST', body: b }); toast(r.message || '저장했어요'); setTimeout(viewCoupang, 1200); } catch (e) { if (e.message !== 'login') toast(e.message); } };
  $('#main').querySelectorAll('[data-save]').forEach((b) => { b.onclick = () => { const v = $(`input[data-key="${b.dataset.save}"]`).value.trim(); if (!v) return toast('링크를 넣어 주세요'); post({ action: 'set', key: b.dataset.save, url: v }); }; });
  $('#main').querySelectorAll('[data-del]').forEach((b) => { b.onclick = () => { if (confirm('목록에서 뺄까요?')) post({ action: 'remove', key: b.dataset.del }); }; });
  $('#add').onclick = () => post({ action: 'add', name: $('#nn').value.trim(), url: $('#nu').value.trim() });
}

// ---------- 앱 카드 (커먼센스) ----------
async function viewCards(siteId) {
  shell('cards', loading());
  const st = (await sites()).filter((s) => s.app?.kind === 'commonsense');
  if (!st.length) { $('#main').innerHTML = '<div class="empty">앱 카드를 쓰는 사이트가 없어요 (사이트 설정 → 앱 카드)</div>'; return; }
  siteId = siteId || st[0].id;
  const { files } = await api('cards?site=' + siteId);
  const pend = files.flatMap((f) => f.items.map((it, i) => ({ ...it, file: f.name, i }))).filter((x) => x.status === 'pending');
  const done = files.flatMap((f) => f.items).filter((x) => x.status !== 'pending').slice(-20).reverse();
  const txt = (row) => Object.entries(row).map(([k, v]) => `<span class="small muted">${esc(k)}</span> ${esc(v)}`).join('<br>');
  $('#main').innerHTML = `<div class="page-h"><h1>앱 카드 후보</h1><button class="btn" id="collect">이슈 모아서 새 후보 만들기</button></div>
  <p class="muted small">최근 사회 이슈에서 의견이 갈릴 만한 생활 상황을 골라 카드 후보로 만들어요 (월·목 오전 자동). 승인한 카드만 앱에 추가돼요.</p>
  <div class="card"><div class="list">${pend.map((x, k) => `<div class="item" style="align-items:flex-start"><div class="t">${txt(x.row)}<br><span class="small muted">이슈: ${esc(x.issue)} ${x.source?.url ? `· <a href="${esc(x.source.url)}" target="_blank" rel="noopener">출처</a>` : ''} · ${esc(x.why)}</span></div>
    <div class="seg" style="margin:0" data-k="${k}"><button type="button" data-v="approved">추가</button><button type="button" data-v="rejected">빼기</button></div></div>`).join('') || '<div class="empty">승인 기다리는 후보가 없어요</div>'}</div>
    ${pend.length ? '<div class="btns" style="margin-top:12px"><button class="btn" id="allAdd">모두 추가</button><button class="btn primary" id="save">고른 대로 앱에 반영</button></div>' : ''}</div>
  <div class="card" style="margin-top:14px"><h2>최근 처리</h2><div class="list">${done.map((x) => `<div class="item"><div class="t small">${txt(x.row)}</div>${x.status === 'inserted' ? '<span class="chip ok">앱에 추가됨</span>' : x.status === 'approved' ? '<span class="chip brand">추가 대기</span>' : x.status === 'error' ? `<span class="chip bad" title="${esc(x.error)}">오류</span>` : '<span class="chip">뺌</span>'}</div>`).join('') || '<p class="muted small">없음</p>'}</div></div>`;
  const pick = {};
  $('#main').querySelectorAll('.seg[data-k]').forEach((sg) => { sg.onclick = (e) => { const b = e.target.closest('button'); if (!b) return; [...sg.children].forEach((c) => c.classList.toggle('on', c === b)); pick[sg.dataset.k] = b.dataset.v; }; });
  if ($('#allAdd')) $('#allAdd').onclick = () => {
    $('#main').querySelectorAll('.seg[data-k]').forEach((sg) => { [...sg.children].forEach((c) => c.classList.toggle('on', c.dataset.v === 'approved')); pick[sg.dataset.k] = 'approved'; });
    toast(`${pend.length}개 모두 '추가'로 골랐어요. 뺄 것만 '빼기'로 바꾸고 '고른 대로 앱에 반영'을 눌러 주세요`);
  };
  if ($('#save')) $('#save').onclick = async () => {
    const decisions = Object.entries(pick).map(([k, v]) => ({ file: pend[k].file, i: pend[k].i, status: v }));
    if (!decisions.length) return toast('추가/빼기를 골라 주세요');
    try { await api('cards', { method: 'POST', body: { site: siteId, decisions } }); toast('반영 중이에요. 1~2분 뒤 앱에 추가돼요'); setTimeout(() => viewCards(siteId), 2500); } catch (e) { if (e.message !== 'login') toast(e.message); }
  };
  $('#collect').onclick = async () => { try { await api('cards', { method: 'POST', body: { site: siteId, mode: 'collect' } }); toast('이슈를 모으는 중이에요. 3~5분 뒤 새로고침하세요'); } catch (e) { if (e.message !== 'login') toast(e.message); } };
}

// ---------- 연결 가이드 ----------
function viewGuide() {
  shell('guide', `<div class="page-h"><h1>연결 가이드</h1></div><div class="grid g2 guide">
  <div class="card"><h2>0. 비밀키 넣는 곳</h2><ol><li>GitHub 저장소 → <b>Settings</b> → <b>Secrets and variables</b> → <b>Actions</b></li><li><b>New repository secret</b> → 이름(Name)과 값(Secret) 넣고 <b>Add secret</b></li><li>사이트 설정에는 <b>비밀키 이름</b>만 적어요. 값은 GitHub에만 있어요</li></ol></div>
  <div class="card"><h2>1. Claude API 키 (글쓰기)</h2><ol><li>console.anthropic.com 가입 → <b>Billing</b>에서 결제 수단 등록</li><li><b>API Keys</b> → <b>Create Key</b> → 복사</li><li>GitHub 비밀키 이름 <code>ANTHROPIC_API_KEY</code></li></ol><p class="small muted">글 한 편에 대략 수십~수백 원 (모델·웹 검색 횟수에 따라)</p></div>
  <div class="card"><h2>2. 이미지 API 키 (대표 사진)</h2><ol><li><b>OpenAI</b>: platform.openai.com → Billing 등록 → API keys → 비밀키 이름 <code>OPENAI_API_KEY</code></li><li>또는 <b>Gemini</b>: aistudio.google.com → Get API key → 비밀키 이름 <code>GEMINI_API_KEY</code></li><li>사이트 설정 → 글·이미지 엔진에서 고르기</li></ol></div>
  <div class="card"><h2>3. 워드프레스 연결</h2><ol><li>워드프레스 관리자 → <b>사용자 → 프로필</b> 맨 아래 <b>애플리케이션 비밀번호</b></li><li>이름에 <code>studio</code> 입력 → <b>새 애플리케이션 비밀번호 추가</b> → 나온 비밀번호 복사 (띄어쓰기 포함 그대로)</li><li>GitHub 비밀키 이름 예: <code>WP_FORSMARTLIFE_PASS</code></li><li>사이트 설정 → 블로그: 종류 워드프레스, 사용자명(로그인 아이디), 비밀키 이름 적기</li></ol><p class="small muted">보안 플러그인이 REST API를 막으면 연결이 안 돼요. 그때 화면을 캡처해 주세요.</p></div>
  <div class="card"><h2>4. 인스타 토큰 (계정마다)</h2><ol><li>developers.facebook.com → 내 앱 → 인스타용 앱 → <b>앱 역할 → 역할</b> → <b>Instagram 테스터</b>로 계정 추가</li><li>instagram.com 그 계정 로그인 → 설정 → 앱 및 웹사이트 → 테스터 초대 수락</li><li>앱 → Instagram API 설정 → <b>계정 추가</b> → <b>토큰 생성</b> → 복사</li><li>GitHub 비밀키 이름 예: <code>IG_TOKEN_INFOBAY</code> (사이트 설정의 이름과 같게)</li></ol></div>
  <div class="card"><h2>5. 스레드 토큰 (계정마다)</h2><ol><li>스레드용 앱 → 앱 역할 → <b>Threads 테스터</b>로 계정 추가 → threads.com 설정 → 웹사이트 권한 → 초대 수락</li><li>GitHub Actions → <b>스레드 토큰 발급</b> 순서대로 (code 붙여넣기)</li><li>계정이 여러 개면 비밀키 이름을 계정별로: 예 <code>THREADS_TOKEN_INFOBAY</code></li></ol><p class="small muted">토큰은 60일마다 자동 연장돼요 (토큰 연장 작업)</p></div>
  <div class="card"><h2>6. 네이버 블로그 (uplika)</h2><ol><li>uplika.com → 연결 → Naver Blog → 크롬 확장 설치</li><li>API 키 → GitHub 비밀키 <code>UPLIKA_API_KEY</code></li><li>네이버 글은 크롬이 켜져 있을 때 올라가요</li></ol></div>
  <div class="card"><h2>7. 이 관리화면 (Vercel)</h2><ol><li>vercel.com → <b>Add New → Project</b> → GitHub 저장소 선택</li><li><b>Root Directory</b>를 <code>studio</code>로</li><li><b>Environment Variables</b>: <code>ADMIN_PASSWORD</code>(로그인 비밀번호), <code>GITHUB_TOKEN</code>(저장소 권한 토큰), <code>GITHUB_REPO</code></li><li>Deploy</li></ol></div>
  <div class="card"><h2>9. 커먼센스 앱 DB (카드 늘리기)</h2><ol><li>supabase.com → 커먼센스 프로젝트 → <b>Project Settings → API</b></li><li><b>Project URL</b> → GitHub 비밀키 <code>SUPABASE_URL</code></li><li><b>service_role</b> 키 → 비밀키 <code>SUPABASE_SERVICE_KEY</code> (이 키는 절대 다른 곳에 붙여넣지 마세요)</li></ol></div>
  <div class="card"><h2>8. GitHub 설정 한 가지</h2><ol><li>저장소 → Settings → Actions → General</li><li>맨 아래 <b>Workflow permissions</b> → <b>Allow GitHub Actions to create and approve pull requests</b> 체크 → Save</li></ol><p class="small muted">이게 꺼져 있으면 '승인 대기'가 만들어지지 않아요</p></div>
  </div>`);
}

// ---------- 라우터 ----------
async function route() {
  const h = location.hash.replace(/^#\/?/, '') || 'home';
  const [page, arg] = [h.split('/')[0], decodeURIComponent(h.split('/').slice(1).join('/'))];
  try {
    if (!(await (await fetch('/api/auth')).json()).ok) return renderLogin();
    if (page === 'review') return arg ? viewReview(arg) : viewReviewList();
    if (page === 'create') return viewCreate();
    if (page === 'ideas') return viewIdeas(arg || undefined);
    if (page === 'trends') return viewTrends();
    if (page === 'schedule') return viewSchedule();
    if (page === 'cards') return viewCards(arg);
    if (page === 'coupang') return viewCoupang();
    if (page === 'sites') return arg ? viewSite(arg) : viewSites();
    if (page === 'guide') return viewGuide();
    return viewHome();
  } catch (e) { if (e.message !== 'login') { const m = $('#main'); if (m) m.innerHTML = `<div class="empty">문제가 생겼어요: ${esc(e.message)}</div>`; } }
}
window.addEventListener('hashchange', route);
route();
