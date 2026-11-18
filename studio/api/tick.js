// Vercel 예약 실행(cron)이 정해진 시간에 GitHub 작업을 깨워요. GitHub 자체 예약은 몇 시간씩 늦거나 건너뛰는 일이 잦아서예요.
// 실제로 만들지·올릴지는 GitHub 쪽 일정(scheduler.py)이 정해요. 그래서 여러 번 불려도 같은 글이 두 번 만들어지거나 올라가지 않아요.
const { REPO, gh, send } = require('./_lib');

module.exports = async (req, res) => {
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.authorization !== `Bearer ${secret}`) return send(res, 401, { error: 'unauthorized' });
  const what = (req.query && req.query.what) || new URL(req.url, 'http://x').searchParams.get('what') || 'both';
  const out = {};
  const run = async (wf) => {
    try {
      // 누가 주소를 알아내 여러 번 불러도 작업이 마구 돌지 않게: 같은 작업을 15분 안에 이미 시작했으면 건너뛰어요
      const last = await gh('GET', `/repos/${REPO}/actions/workflows/${wf}/runs?per_page=1&event=workflow_dispatch`).catch(() => null);
      const t = last && last.workflow_runs && last.workflow_runs[0] ? Date.parse(last.workflow_runs[0].created_at) : 0;
      if (Date.now() - t < 15 * 60 * 1000) { out[wf] = 'skip (15분 안에 이미 실행)'; return; }
      await gh('POST', `/repos/${REPO}/actions/workflows/${wf}/dispatches`, { ref: 'main' }); out[wf] = 'ok';
    } catch (e) { out[wf] = 'error'; }
  };
  if (what === 'generate' || what === 'both') await run('studio-generate.yml');
  if (what === 'publish' || what === 'both') { await run('studio-publish.yml'); await run('publish.yml'); } // publish.yml: 예전 방식 남은 글
  if (what === 'publish' || what === 'both') await run('issue-watch.yml'); // 속보 감지: 안 돌고 있으면 시작 (6시간 동안 1시간마다)
  send(res, 200, out);
};
