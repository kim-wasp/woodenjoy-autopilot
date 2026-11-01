// Vercel 예약 실행(cron)이 정해진 시간에 GitHub 작업을 깨워요. GitHub 자체 예약은 몇 시간씩 늦거나 건너뛰는 일이 잦아서예요.
// 실제로 만들지·올릴지는 GitHub 쪽 일정(scheduler.py)이 정해요. 그래서 여러 번 불려도 같은 글이 두 번 만들어지거나 올라가지 않아요.
const { REPO, gh, send } = require('./_lib');

module.exports = async (req, res) => {
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.authorization !== `Bearer ${secret}`) return send(res, 401, { error: 'unauthorized' });
  const what = (req.query && req.query.what) || new URL(req.url, 'http://x').searchParams.get('what') || 'both';
  const out = {};
  const run = async (wf) => {
    try { await gh('POST', `/repos/${REPO}/actions/workflows/${wf}/dispatches`, { ref: 'main' }); out[wf] = 'ok'; }
    catch (e) { out[wf] = e.message; }
  };
  if (what === 'generate' || what === 'both') await run('studio-generate.yml');
  if (what === 'publish' || what === 'both') await run('studio-publish.yml');
  send(res, 200, out);
};
