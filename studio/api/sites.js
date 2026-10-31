// 사이트 목록·설정 읽기 / 저장, 글감·검색량
const { guard, send, body, listDir, readJson, writeFile } = require('./_lib');

module.exports = guard(async (req, res) => {
  if (req.method === 'PUT') {
    const { id, site } = await body(req);
    if (!/^[a-z0-9][a-z0-9-]{1,30}$/.test(id || '')) return send(res, 400, { error: '사이트 id 는 영문 소문자·숫자·하이픈 2~31자예요' });
    if (!site || typeof site !== 'object') return send(res, 400, { error: '설정이 비어 있어요' });
    site.id = id;
    await writeFile(`sites/${id}/site.json`, JSON.stringify(site, null, 2) + '\n', `사이트 설정 저장: ${id}`);
    return send(res, 200, { ok: true });
  }
  const dirs = (await listDir('sites')).filter((d) => d.type === 'dir');
  const sites = [];
  for (const d of dirs) {
    const s = await readJson(`sites/${d.name}/site.json`);
    if (!s) continue;
    s.id = d.name;
    if (req.query && req.query.ideas && req.query.id === d.name) s._ideas = await readJson(`sites/${d.name}/ideas.json`);
    sites.push(s);
  }
  send(res, 200, { sites });
});
