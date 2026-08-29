// The Chronicle — 本地预览服务器（零依赖）
// 用法：npm run dev [-- --port 7100 --host 127.0.0.1]
// 服务内容：site/ 目录（构建产物）；若未构建则提示先运行 python build.py
const http = require('http');
const fs = require('fs');
const path = require('path');

function parseArgs(argv) {
  const args = { port: process.env.PORT || 7100, host: process.env.HOST || '127.0.0.1' };
  for (let i = 2; i < argv.length; i++) {
    if ((argv[i] === '--port' || argv[i] === '-p') && argv[i + 1]) args.port = Number(argv[++i]);
    else if ((argv[i] === '--host' || argv[i] === '-h') && argv[i + 1]) args.host = argv[++i];
    else if (argv[i].startsWith('--port=')) args.port = Number(argv[i].split('=')[1]);
    else if (argv[i].startsWith('--host=')) args.host = argv[i].split('=')[1];
  }
  return args;
}

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
  '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.xml': 'application/xml',
};

const { port, host } = parseArgs(process.argv);
const rootDir = path.join(__dirname, 'site');

const server = http.createServer((req, res) => {
  let urlPath = decodeURIComponent(req.url.split('?')[0]);
  let filePath = path.join(rootDir, urlPath);
  if (!filePath.startsWith(rootDir)) { res.writeHead(403); return res.end('Forbidden'); }

  if (!fs.existsSync(rootDir)) {
    res.writeHead(503, { 'Content-Type': 'text/html; charset=utf-8' });
    return res.end('<h1>尚未构建</h1><p>请先运行 <code>python build.py</code> 生成 site/ 目录。</p>');
  }

  if (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory()) {
    filePath = path.join(filePath, 'index.html');
  }
  if (!fs.existsSync(filePath) && !path.extname(filePath)) {
    filePath += '.html'; // 允许 /sections/world 这样的无扩展访问
  }
  if (!fs.existsSync(filePath)) { res.writeHead(404); return res.end('Not Found'); }

  const ext = path.extname(filePath).toLowerCase();
  res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);
});

server.listen(port, host, () => {
  console.log(`The Chronicle 预览: http://${host}:${port}/  (root: ${rootDir})`);
});
