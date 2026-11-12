// 네이버 크리에이터 어드바이저 트렌드 메모: 사장님이 붙여넣은 인기·급등 검색어를 저장해요 (자동 수집 아님)
const { guard, send, body, readJson, writeFile } = require('./_lib');
const FILE = 'status/naver_trends.json';
function parse(text) {
  const out = [];
  for (let line of String(text || '').split(/[\n,]/)) {
    line = line.replace(/^\s*\d+\s*[.)]?\s*/, '').replace(/\s*(new|NEW|급상승|▲\s*\d+|↑\s*\d*|\d+위)\s*$/g, '').trim();
    if (line && line.length <= 40 && !out.includes(line)) out.push(line);
  }
  return out.slice(0, 60);
}
module.exports = guard(async (req, res) => {
  const data = (await readJson(FILE)) || { entries: [] };
  if (req.method === 'POST') {
    const { text = '', label = '' } = await body(req);
    const keywords = parse(text);
    if (!keywords.length) return send(res, 400, { error: '검색어를 찾지 못했어요. 한 줄에 하나씩 붙여넣어 주세요' });
    data.entries.unshift({ at: new Date().toISOString(), label: String(label).slice(0, 30), keywords });
    data.entries = data.entries.slice(0, 30);
    await writeFile(FILE, JSON.stringify(data, null, 1), `트렌드 메모: ${keywords.slice(0, 3).join(', ')}`);
    return send(res, 200, { ok: true, count: keywords.length });
  }
  if (req.method === 'DELETE') {
    const { at } = await body(req);
    data.entries = data.entries.filter((e) => e.at !== at);
    await writeFile(FILE, JSON.stringify(data, null, 1), '트렌드 메모 지우기');
    return send(res, 200, { ok: true });
  }
  send(res, 200, data);
});
