// 일정표 (스튜디오 업로드가 30분마다 status/schedule.json 으로 기록)
const { guard, send, readJson } = require('./_lib');

module.exports = guard(async (req, res) => {
  send(res, 200, (await readJson('status/schedule.json')) || { items: [] });
});
