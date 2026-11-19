const http = require('http');
const WebSocket = require('ws');
const url = require('url');
const fs = require('fs');
const path = require('path');
const os = require('os');

class RemoteServer {
  constructor(port = 5050, mainWindow = null) {
    this.port = port;
    this.mainWindow = mainWindow;
    this.server = null;
    this.wss = null;
    this.running = false;
    this.url = '';
  }

  start() {
    if (this.running) return;
    this.server = http.createServer((req, res) => this._handleRequest(req, res));
    this.wss = new WebSocket.Server({ server: this.server });
    this.wss.on('connection', (ws) => {
      ws.on('message', (raw) => {
        try {
          const msg = JSON.parse(raw);
          this._handleWsCommand(msg, ws);
        } catch {}
      });
    });
    this.server.listen(this.port, '0.0.0.0', () => {
      this.running = true;
      const interfaces = os.networkInterfaces();
      let ip = '127.0.0.1';
      for (const name of Object.keys(interfaces)) {
        for (const iface of interfaces[name]) {
          if (iface.family === 'IPv4' && !iface.internal) {
            ip = iface.address; break;
          }
        }
        if (ip !== '127.0.0.1') break;
      }
      this.url = `http://${ip}:${this.port}`;
      if (this.mainWindow) {
        this.mainWindow.webContents.send('remote-started', { url: this.url });
      }
    });
  }

  stop() {
    if (this.wss) { try { this.wss.close(); } catch {} }
    if (this.server) { try { this.server.close(); } catch {} }
    this.running = false;
    if (this.mainWindow) {
      this.mainWindow.webContents.send('remote-stopped');
    }
  }

  _handleRequest(req, res) {
    const parsed = url.parse(req.url, true);
    if (parsed.pathname === '/') {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(this._getMobileHtml());
    } else if (parsed.pathname === '/api/status') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ running: true, url: this.url }));
    } else {
      res.writeHead(404);
      res.end('Not Found');
    }
  }

  _handleWsCommand(msg, ws) {
    if (this.mainWindow) {
      this.mainWindow.webContents.send('remote-command', msg);
      // Forward to display
      if (msg.type === 'show_text') {
        this.mainWindow.webContents.send('display:show', msg);
      } else if (msg.type === 'black') {
        this.mainWindow.webContents.send('display:black', msg);
      } else if (msg.type === 'next' || msg.type === 'prev') {
        this.mainWindow.webContents.send('display:navigate', msg);
      }
    }
    try {
      ws.send(JSON.stringify({ type: 'ok' }));
    } catch {}
  }

  _getMobileHtml() {
    return `<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>Cantio Remote</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
body{background:#11111b;color:#cdd6f4;padding:16px;min-height:100vh}
h1{text-align:center;font-size:22px;color:#cba6f7;margin-bottom:20px}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:400px;margin:0 auto}
button{background:#313244;color:#cdd6f4;border:none;padding:16px;border-radius:12px;font-size:16px;cursor:pointer;transition:all 0.2s;font-weight:600}
button:active{transform:scale(0.95);background:#45475a}
button.go-live{background:#a6e3a1;color:#11111b}
button.black{background:#45475a;color:#f38ba8}
button.full{grid-column:1/-1}
.search-box{margin:16px auto;max-width:400px}
.search-box input{width:100%;padding:12px 16px;border-radius:10px;border:1px solid #45475a;background:#1e1e2e;color:#cdd6f4;font-size:16px}
.results{margin-top:12px}
.result-item{padding:12px;background:#1e1e2e;border-radius:8px;margin-bottom:6px;cursor:pointer}
.result-item:active{background:#313244}
.result-item .title{color:#cdd6f4;font-weight:600}
.result-item .info{color:#6c7086;font-size:12px;margin-top:4px}
.connection{text-align:center;color:#585b70;font-size:12px;margin:16px 0}
</style>
</head>
<body>
<h1>Cantio Remote</h1>
<div class="connection" id="status">Conectare...</div>
<div class="controls">
<button class="go-live" onclick="send('go_live')">Live</button>
<button class="black" onclick="send('black')">Black</button>
<button onclick="send('prev')">◀ Anterior</button>
<button onclick="send('next')">Următor ▶</button>
<button onclick="send('freeze')">Îngheață</button>
<button onclick="send('logo')">Logo</button>
<button class="full" onclick="send('clear')" style="background:#eba0ac;color:#11111b">Șterge text</button>
</div>
<div class="search-box">
<input type="text" id="searchInput" placeholder="Caută cântare..." oninput="search(this.value)">
</div>
<div class="results" id="results"></div>
<script>
let ws;
function connect(){const p=location.protocol==='https:'?'wss:':'ws:';ws=new WebSocket(p+'//'+location.host);ws.onopen=()=>document.getElementById('status').textContent='Conectat';ws.onclose=()=>{document.getElementById('status').textContent='Deconectat';setTimeout(connect,2000)};ws.onerror=()=>{ws.close()}}
function send(cmd){if(ws&&ws.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:cmd}))}
let st;
function search(q){clearTimeout(st);st=setTimeout(()=>{if(!q||q.length<2)return;ws.send(JSON.stringify({type:'search',query:q}))},300)}
connect()
</script>
</body>
</html>`;
  }

  getUrl() { return this.url; }
  getStatus() { return { running: this.running, url: this.url }; }
}

module.exports = RemoteServer;
