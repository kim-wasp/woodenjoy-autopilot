// 글 만들기·글감 추천 실행, 최근 실행 상태
const { REPO, MOCK, gh, guard, send, body } = require('./_lib');

const NAMES = { 'studio-generate.yml': '글 만들기', 'studio-publish.yml': '업로드' };
module.exports = guard(async (req, res) => {
  if (req.method === 'POST') {
    const { site, topic = '', notes = '', mode = 'post' } = await body(req);
    if (!site) return send(res, 400, { error: '사이트를 고르세요' });
    if (!MOCK) await gh('POST', `/repos/${REPO}/actions/workflows/studio-generate.yml/dispatches`, { ref: 'main', inputs: { site, topic, notes, mode, redo_branch: '' } });
    return send(res, 200, { ok: true });
  }
  if (MOCK) return send(res, 200, { runs: [{ name: '글 만들기', status: 'completed', conclusion: 'success', created: new Date().toISOString(), url: '#' }] });
  const out = [];
  for (const wf of Object.keys(NAMES)) {
    const j = await gh('GET', `/repos/${REPO}/actions/workflows/${wf}/runs?per_page=6`).catch(() => ({ workflow_runs: [] }));
    for (const r of j.workflow_runs) out.push({ name: NAMES[wf], event: r.event, status: r.status, conclusion: r.conclusion, created: r.created_at, url: r.html_url });
  }
  out.sort((a, b) => b.created.localeCompare(a.created));
  send(res, 200, { runs: out.slice(0, 10) });
});
