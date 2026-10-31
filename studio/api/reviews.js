// 승인 대기 목록·자세히 보기·승인/다시 만들기/버리기
const { REPO, MOCK, gh, guard, send, body, readJson, readFile, listDir, writeFile, rawUrl } = require('./_lib');

async function openPRs() {
  const prs = await gh('GET', `/repos/${REPO}/pulls?state=open&per_page=50`);
  return prs.filter((p) => p.head.ref.startsWith('studio/'));
}
function dirOfBranch(ref) { return 'content/' + ref.replace(/^studio\//, ''); }

async function detail(dir, ref) {
  const post = await readJson(`${dir}/post.json`, ref);
  if (!post) return null;
  const qa = await readJson(`${dir}/cards/qa.json`, ref);
  const files = await listDir(dir, ref);
  const has = (n) => files.some((f) => f.name === n);
  let html = has('article.html') ? await readFile(`${dir}/article.html`, ref) : null;
  if (html) html = html.replace(/src="(hero\.jpg|cards\/\d+\.jpg)"/g, (_, f) => `src="${rawUrl(`${dir}/${f}`, ref)}"`);
  return {
    dir, post, html,
    hero: has('hero.jpg') ? rawUrl(`${dir}/hero.jpg`, ref) : null,
    cards: (qa && qa.files ? qa.files : []).map((f) => rawUrl(`${dir}/cards/${f}`, ref)),
    article_md: has('article.md') ? await readFile(`${dir}/article.md`, ref) : null,
  };
}

module.exports = guard(async (req, res) => {
  const q = req.query || {};
  if (req.method === 'GET' && !q.n) {
    if (MOCK) {
      const out = [];
      for (const s of await listDir('content')) for (const d of await listDir(`content/${s.name}`)) {
        const p = await readJson(`content/${s.name}/${d.name}/post.json`);
        if (p && p.status === 'draft') out.push({ n: `content/${s.name}/${d.name}`, site: s.name, title: p.title, ok: !!(p.checks && p.checks.ok), issues: (p.checks || {}).issues || [], created: p.created_at });
      }
      return send(res, 200, { items: out });
    }
    const items = (await openPRs()).map((p) => ({ n: p.number, site: p.head.ref.split('/')[1], title: p.title.replace(/^\[[^\]]+\]\s*\[[^\]]+\]\s*/, ''), ok: !p.title.startsWith('[점검 실패]'), created: p.created_at, url: p.html_url }));
    return send(res, 200, { items });
  }
  if (req.method === 'GET') {
    if (MOCK) return send(res, 200, await detail(q.n, 'main'));
    const pr = await gh('GET', `/repos/${REPO}/pulls/${Number(q.n)}`);
    const d = await detail(dirOfBranch(pr.head.ref), pr.head.sha);
    return send(res, 200, { ...d, pr: { n: pr.number, url: pr.html_url, branch: pr.head.ref } });
  }
  // POST: approve | reject | redo
  const { n, action, notes = '', topic = '' } = await body(req);
  if (MOCK) return send(res, 200, { ok: true, mock: true, action });
  const pr = await gh('GET', `/repos/${REPO}/pulls/${Number(n)}`);
  const ref = pr.head.ref, dir = dirOfBranch(ref);
  if (action === 'approve') {
    const post = await readJson(`${dir}/post.json`, ref);
    post.status = 'ready';
    if (notes) post.approve_note = notes;
    await writeFile(`${dir}/post.json`, JSON.stringify(post, null, 2) + '\n', `승인: ${post.title}`, ref);
    await gh('PUT', `/repos/${REPO}/pulls/${pr.number}/merge`, { merge_method: 'squash', commit_title: `승인: ${post.title}` });
    await gh('DELETE', `/repos/${REPO}/git/refs/heads/${ref}`).catch(() => {});
    return send(res, 200, { ok: true });
  }
  if (action === 'reject') {
    await gh('PATCH', `/repos/${REPO}/pulls/${pr.number}`, { state: 'closed' });
    await gh('DELETE', `/repos/${REPO}/git/refs/heads/${ref}`).catch(() => {});
    return send(res, 200, { ok: true });
  }
  if (action === 'redo') {
    const site = ref.split('/')[1];
    await gh('POST', `/repos/${REPO}/actions/workflows/studio-generate.yml/dispatches`, { ref: 'main', inputs: { site, topic, notes, redo_branch: ref, mode: 'post' } });
    return send(res, 200, { ok: true });
  }
  send(res, 400, { error: '알 수 없는 동작' });
});
