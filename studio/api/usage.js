// 사용량: Claude 토큰·웹 검색·사진 수와 추정 비용 (status/usage_summary.json, 워크플로가 실행마다 갱신)
const { guard, send, readJson } = require('./_lib');
module.exports = guard(async (req, res) => {
  send(res, 200, (await readJson('status/usage_summary.json')) || { months: {}, recent_runs: [] });
});
