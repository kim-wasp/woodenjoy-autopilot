// 커먼센스 카드 후보: 목록 / 승인·빼기 반영 / 새 후보 만들기
const { REPO, MOCK, gh, guard, send, body, listDir, readJson, writeFile } = require('./_lib');

module.exports = guard(async (req, res) => {
  const q = req.query || {};
  if (req.method === 'GET') {
    const dir = `sites/${q.site}/cards`;
    const names = (await listDir(dir)).filter((f) => f.name.endsWith('.json')).map((f) => f.name).sort().slice(-8);
    const files = [];
    for (const n of names) { const d = await readJson(`${dir}/${n}`); if (d) files.push({ name: n, ...d }); }
    return send(res, 200, { files });
  }
  const { site, decisions, mode } = await body(req);
  if (!/^[a-z0-9-]+$/.test(site || '')) return send(res, 400, { error: '사이트가 잘못됐어요' });
  if (mode === 'collect') {
    if (!MOCK) await gh('POST', `/repos/${REPO}/actions/workflows/studio-cards.yml/dispatches`, { ref: 'main', inputs: { site, mode: 'collect' } });
    return send(res, 200, { ok: true });
  }
  const byFile = {};
  for (const d of decisions || []) (byFile[d.file] = byFile[d.file] || []).push(d);
  for (const [name, ds] of Object.entries(byFile)) {
    if (!/^[\w.-]+\.json$/.test(name)) continue;
    const p = `sites/${site}/cards/${name}`;
    const data = await readJson(p);
    ds.forEach((d) => { if (data.items[d.i] && data.items[d.i].status === 'pending' && ['approved', 'rejected'].includes(d.status)) data.items[d.i].status = d.status; });
    await writeFile(p, JSON.stringify(data, null, 2) + '\n', `앱 카드 후보 검토: ${site}`);
  }
  if (!MOCK) await gh('POST', `/repos/${REPO}/actions/workflows/studio-cards.yml/dispatches`, { ref: 'main', inputs: { site, mode: 'insert' } });
  send(res, 200, { ok: true });
});
