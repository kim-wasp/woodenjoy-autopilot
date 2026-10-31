// 로그인 / 로그아웃 / 로그인 상태
const crypto = require('crypto');
const { send, body, authed, makeCookie } = require('./_lib');

module.exports = async (req, res) => {
  if (req.method === 'GET') return send(res, 200, { ok: authed(req) });
  if (req.method === 'DELETE') { res.setHeader('Set-Cookie', 's=; Path=/; Max-Age=0'); return send(res, 200, { ok: false }); }
  const pw = process.env.ADMIN_PASSWORD;
  if (!pw) return send(res, 500, { error: 'ADMIN_PASSWORD 환경변수가 없어요 (Vercel 설정)' });
  const { password = '' } = await body(req);
  const a = crypto.createHash('sha256').update(String(password)).digest();
  const b = crypto.createHash('sha256').update(pw).digest();
  if (!crypto.timingSafeEqual(a, b)) { await new Promise((r) => setTimeout(r, 800)); return send(res, 401, { error: '비밀번호가 달라요' }); }
  res.setHeader('Set-Cookie', makeCookie());
  send(res, 200, { ok: true });
};
