// 글 만들기·글감 추천 실행, 최근 실행 상태
const { REPO, MOCK, gh, guard, send, body } = require('./_lib');

const NAMES = { 'studio-generate.yml': '글 만들기', 'studio-publish.yml': '업로드' };
module.exports = guard(async (req, res) => {
  if (req.method === 'POST') {
    const b = await body(req);
    if (b.upload) {  // 사진으로 글쓰기: 브라우저에서 줄인 사진 한 장씩 저장소 uploads/ 에 올려요
      const { batch, name, data } = b.upload;
      if (!/^[0-9a-z-]{6,40}$/.test(batch || '') || !/^[0-9]{2}\.jpg$/.test(name || '')) return send(res, 400, { error: '사진 정보가 이상해요' });
      if (!data || data.length > 3_000_000) return send(res, 400, { error: '사진이 너무 커요' });
      if (!MOCK) await gh('PUT', `/repos/${REPO}/contents/uploads/${batch}/${name}`, { message: `사진 올리기 ${batch}/${name}`, content: data, branch: 'main' });
      return send(res, 200, { ok: true, path: `uploads/${batch}` });
    }
    const { site, topic = '', notes = '', mode = 'post', view = '', photos = '' } = b;
    if (!site) return send(res, 400, { error: '사이트를 고르세요' });
    if (!MOCK) await gh('POST', `/repos/${REPO}/actions/workflows/studio-generate.yml/dispatches`, { ref: 'main', inputs: { site, topic, notes, mode, redo_branch: '', view, photos: /^uploads\/[0-9a-z-]+$/.test(photos) ? photos : '' } });
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
