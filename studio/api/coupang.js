// 쿠팡 파트너스 링크 목록: 보기 · 링크 넣기 · 새 상품 추가
// 링크가 필요하다고 표시된 상품에 링크를 넣으면, 아직 안 올라간 그 글 본문에도 자동으로 넣어요
const { REPO, MOCK, gh, guard, send, body, readFile, readJson, writeFile } = require('./_lib');

const FILE = 'topics/coupang_links.json';
const DISCLOSURE = '이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.';

async function branchOf(dir) {
  const name = 'studio/' + dir.replace(/^content\//, '');
  if (MOCK) return 'main';
  try { await gh('GET', `/repos/${REPO}/branches/${encodeURIComponent(name)}`); return name; } catch (e) { return 'main'; }
}

async function insertIntoPost(item) {
  if (!item.post_dir || !item.after) return '글 위치 정보가 없어 목록에만 저장했어요';
  const ref = await branchOf(item.post_dir);
  const post = await readJson(`${item.post_dir}/post.json`, ref);
  if (!post) return '글을 찾지 못해 목록에만 저장했어요';
  if ((post.published || {}).blog) return '글이 이미 올라가서 목록에만 저장했어요 (다음 글부터 쓰여요)';
  let md = await readFile(`${item.post_dir}/article.md`, ref);
  if (!md || md.includes(item.url)) return '이미 들어가 있어요';
  const paras = md.split('\n\n');
  const i = paras.findIndex((p) => p.includes(item.after.trim().slice(0, 20)));
  if (i < 0) return '넣을 문단을 못 찾아 목록에만 저장했어요';
  paras[i] = paras[i].trimEnd() + ` 👉 [${item.name}](${item.url})`;
  md = paras.join('\n\n');
  if (!md.includes(DISCLOSURE)) md = DISCLOSURE + '\n\n' + md;
  await writeFile(`${item.post_dir}/article.md`, md, `쿠팡 링크 넣기: ${item.name}`, ref);
  post.coupang = true;
  await writeFile(`${item.post_dir}/post.json`, JSON.stringify(post, null, 2) + '\n', `쿠팡 링크 표시: ${item.name}`, ref);
  return `글 "${post.title}"에도 넣었어요`;
}

module.exports = guard(async (req, res) => {
  const data = (await readJson(FILE)) || { items: [] };
  if (req.method === 'GET') return send(res, 200, { items: data.items || [] });
  const { action, key, url = '', name = '', search = '' } = await body(req);
  const today = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);
  if (url && !/^https:\/\/link\.coupang\.com\//.test(url.trim())) return send(res, 400, { error: '쿠팡 파트너스 링크(https://link.coupang.com/…)만 넣을 수 있어요' });
  let msg = '저장했어요';
  if (action === 'set') {
    const it = (data.items || []).find((x) => x.key === key);
    if (!it) return send(res, 404, { error: '상품을 못 찾았어요' });
    it.url = url.trim();
    it.status = `링크 있음 (${today} 사장님)`;
    if (it.url) msg = await insertIntoPost(it).catch((e) => `목록엔 저장, 글에 넣기는 실패: ${e.message}`);
  } else if (action === 'add') {
    if (!name) return send(res, 400, { error: '상품 이름을 넣어 주세요' });
    data.items = data.items || [];
    data.items.push({ key: 'item-' + Date.now().toString(36), name, search, url: url.trim(), status: url ? `링크 있음 (${today} 사장님)` : '링크 필요' });
  } else if (action === 'remove') {
    data.items = (data.items || []).filter((x) => x.key !== key);
  }
  await writeFile(FILE, JSON.stringify(data, null, 2) + '\n', `쿠팡 링크 목록 ${action}`);
  send(res, 200, { ok: true, message: msg });
});
