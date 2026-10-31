// 관리화면 로컬 시험 서버 (GitHub 대신 이 저장소 폴더를 읽어요)
// 사용: ADMIN_PASSWORD=test node tools/studio_dev.js  → http://localhost:3000
process.env.STUDIO_MOCK_DIR = process.env.STUDIO_MOCK_DIR || require('path').resolve(__dirname, '..');
const http = require('http'), fs = require('fs'), path = require('path'), url = require('url');
const ROOT = path.resolve(__dirname, '../studio');
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.jpg': 'image/jpeg', '.json': 'application/json' };
http.createServer(async (req, res) => {
  const u = url.parse(req.url, true);
  req.query = u.query;
  if (u.pathname.startsWith('/api/')) {
    const f = path.join(ROOT, 'api', u.pathname.slice(5).replace(/\/$/, '') + '.js');
    if (!fs.existsSync(f)) { res.statusCode = 404; return res.end('{}'); }
    return require(f)(req, res);
  }
  let f = u.pathname.startsWith('/mock/') ? path.join(process.env.STUDIO_MOCK_DIR, decodeURIComponent(u.pathname.slice(6))) : path.join(ROOT, u.pathname === '/' ? 'index.html' : u.pathname);
  if (!fs.existsSync(f)) { res.statusCode = 404; return res.end('not found'); }
  res.setHeader('Content-Type', TYPES[path.extname(f)] || 'application/octet-stream');
  fs.createReadStream(f).pipe(res);
}).listen(process.env.PORT || 3000, () => console.log('studio dev on', process.env.PORT || 3000));
