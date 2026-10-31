// 관리화면 서버 공통: 로그인 확인, GitHub 저장소 읽기·쓰기
// Vercel 환경변수: ADMIN_PASSWORD(로그인 비밀번호), GITHUB_TOKEN(저장소 권한 토큰), GITHUB_REPO(예: kim-wasp/woodenjoy-autopilot)
// 로컬 시험: STUDIO_MOCK_DIR=<저장소 폴더> 이면 GitHub 대신 그 폴더를 읽어요 (쓰기·실행은 흉내만)
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const REPO = process.env.GITHUB_REPO || 'kim-wasp/woodenjoy-autopilot';
const MOCK = process.env.STUDIO_MOCK_DIR;
const SECRET = process.env.SESSION_SECRET || process.env.ADMIN_PASSWORD || 'dev';
const API = 'https://api.github.com';

function sign(v) { return crypto.createHmac('sha256', SECRET).update(v).digest('base64url'); }
function makeCookie(days = 30) {
  const exp = Date.now() + days * 864e5;
  const v = `ok.${exp}`;
  return `s=${v}.${sign(v)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${days * 86400}${MOCK ? '' : '; Secure'}`;
}
function authed(req) {
  const m = (req.headers.cookie || '').match(/(?:^|;\s*)s=([^;]+)/);
  if (!m) return false;
  const [ok, exp, sig] = m[1].split('.');
  const v = `${ok}.${exp}`;
  if (!sig || sig.length !== sign(v).length) return false;
  return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(sign(v))) && Number(exp) > Date.now();
}
function send(res, code, data) {
  res.statusCode = code;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  res.end(JSON.stringify(data));
}
async function body(req) {
  if (req.body && typeof req.body === 'object') return req.body;
  if (typeof req.body === 'string') return JSON.parse(req.body || '{}');
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const t = Buffer.concat(chunks).toString('utf8');
  return t ? JSON.parse(t) : {};
}
// 로그인이 필요한 API 를 감싸요
function guard(fn) {
  return async (req, res) => {
    if (!authed(req)) return send(res, 401, { error: '로그인이 필요해요' });
    try { await fn(req, res); } catch (e) { send(res, e.status || 500, { error: e.message }); }
  };
}

async function gh(method, p, data) {
  if (!process.env.GITHUB_TOKEN) throw Object.assign(new Error('GITHUB_TOKEN 환경변수가 없어요 (Vercel 설정)'), { status: 500 });
  const r = await fetch(API + p, {
    method,
    headers: { Authorization: `Bearer ${process.env.GITHUB_TOKEN}`, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'studio' },
    body: data ? JSON.stringify(data) : undefined,
  });
  if (r.status === 204) return null;
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(`GitHub ${r.status}: ${j.message || ''}`), { status: r.status === 404 ? 404 : 502 });
  return j;
}

// 파일 읽기 (텍스트). 없으면 null
async function readFile(p, ref = 'main') {
  if (MOCK) { const f = path.join(MOCK, p); return fs.existsSync(f) ? fs.readFileSync(f, 'utf8') : null; }
  try {
    const j = await gh('GET', `/repos/${REPO}/contents/${encodeURI(p)}?ref=${encodeURIComponent(ref)}`);
    return Buffer.from(j.content, 'base64').toString('utf8');
  } catch (e) { if (e.status === 404) return null; throw e; }
}
async function readJson(p, ref) { const t = await readFile(p, ref); return t ? JSON.parse(t) : null; }
async function listDir(p, ref = 'main') {
  if (MOCK) { const f = path.join(MOCK, p); return fs.existsSync(f) ? fs.readdirSync(f, { withFileTypes: true }).map((d) => ({ name: d.name, type: d.isDirectory() ? 'dir' : 'file' })) : []; }
  try { return (await gh('GET', `/repos/${REPO}/contents/${encodeURI(p)}?ref=${encodeURIComponent(ref)}`)).map((x) => ({ name: x.name, type: x.type })); } catch (e) { if (e.status === 404) return []; throw e; }
}
async function writeFile(p, text, message, branch = 'main') {
  if (MOCK) { fs.writeFileSync(path.join(MOCK, p), text); return; }
  let sha;
  try { sha = (await gh('GET', `/repos/${REPO}/contents/${encodeURI(p)}?ref=${encodeURIComponent(branch)}`)).sha; } catch (e) { if (e.status !== 404) throw e; }
  await gh('PUT', `/repos/${REPO}/contents/${encodeURI(p)}`, { message, content: Buffer.from(text, 'utf8').toString('base64'), branch, sha });
}
// 공개 저장소 이미지 주소
function rawUrl(p, ref = 'main') { return MOCK ? `/mock/${p}` : `https://raw.githubusercontent.com/${REPO}/${ref}/${p}`; }

module.exports = { REPO, MOCK, gh, readFile, readJson, listDir, writeFile, rawUrl, send, body, guard, authed, makeCookie };
