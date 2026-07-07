// Focusboard V2 — отдельный шелл, ОБЩИЕ данные с v1.
// Архитектура процессов:
//   :3001 — бэкенд v1 (launchd com.focusboard.backend, KeepAlive) — переиспользуем
//   :3002 — v2-api (launchd com.denis-task-tracker.v2api ИЛИ spawn в dev)
//   :4174 — статика собранного фронтенда (встроенный http-сервер, без зависимостей)
// Шелл не тянет node_modules вообще — упакованное .app самодостаточно.
const { app, BrowserWindow, Notification } = require('electron');
const path = require('path');
const fs = require('fs');
const http = require('http');
const net = require('net');

const APP_TITLE = 'Focusboard V2';
app.setName(APP_TITLE);

// Один экземпляр: launchd-агент оболочки и объект входа могут стартовать
// параллельно — второй процесс просто показывает окно первого и выходит.
const gotSingleInstance = app.requestSingleInstanceLock();
if (!gotSingleInstance) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (win && !win.isDestroyed()) { win.show(); win.focus(); }
    else createWindow();
  });
}

// Режимы: по умолчанию сервим собранный frontend/dist. Для live-разработки:
// V2_DEV=1 npm run electron:dev + vite на 5174.
const DIST_DIR = path.join(__dirname, '..', 'frontend', 'dist');
const useDist = !process.env.V2_DEV && fs.existsSync(path.join(DIST_DIR, 'index.html'));
const PORT_BACKEND = 3001;          // общий с v1
const PORT_V2API = 3002;
const PORT_FRONTEND = 4174;         // v1 занимает 4173
const PORT_DEV = 5174;              // v1 dev занимает 5173

function portOpen(port) {
  return new Promise(resolve => {
    const s = net.connect(port, '127.0.0.1');
    s.setTimeout(700);
    s.on('connect', () => { s.destroy(); resolve(true); });
    s.on('timeout', () => { s.destroy(); resolve(false); });
    s.on('error', () => resolve(false));
  });
}

// ── Дочерние процессы (только dev/фоллбек; в проде их держит launchd) ─────────
// ВАЖНО: better-sqlite3 собран под системный Node (им живёт launchd-бэкенд v1),
// у Electron другой ABI — поэтому только spawn системного node, никаких require.
let backendChild = null;
let v2ApiChild = null;

function spawnNodeScript(scriptPath, env, onOk) {
  if (!fs.existsSync(scriptPath)) {
    console.error(`[dtt] скрипт не найден (упакованное приложение?): ${scriptPath}`);
    return;
  }
  const { spawn } = require('child_process');
  const tryNodes = ['node', '/opt/homebrew/bin/node', '/usr/local/bin/node', '/usr/bin/node'];
  const launch = (i) => {
    if (i >= tryNodes.length) { console.error('[dtt] node не найден для', scriptPath); return; }
    const child = spawn(tryNodes[i], [scriptPath], { env: { ...process.env, ...env }, stdio: 'inherit' });
    child.on('error', () => launch(i + 1));
    child.on('spawn', () => { console.log(`[dtt] spawned ${path.basename(scriptPath)} via ${tryNodes[i]}`); onOk(child); });
  };
  launch(0);
}

async function ensureBackend() {
  if (await portOpen(PORT_BACKEND)) { console.log('[dtt] backend 3001 — reusing'); return; }
  console.log('[dtt] no backend on 3001 — spawning v1 backend');
  spawnNodeScript(
    path.join(__dirname, '..', '..', 'backend', 'server.js'),
    { DB_PATH: process.env.DB_PATH || path.join(__dirname, '..', '..', 'backend', 'data', 'focus.db') },
    c => { backendChild = c; },
  );
}

async function ensureV2Api() {
  if (await portOpen(PORT_V2API)) { console.log('[dtt] v2-api 3002 — reusing'); return; }
  console.log('[dtt] no v2-api on 3002 — spawning');
  spawnNodeScript(path.join(__dirname, '..', 'api', 'server.js'), {}, c => { v2ApiChild = c; });
}

// ── Автозапуск (Login Items macOS через osascript) ────────────────────────────
const { execFile } = require('child_process');

function osa(script) {
  return new Promise((resolve, reject) => {
    execFile('osascript', ['-e', script], { timeout: 8000 }, (err, stdout) => {
      if (err) reject(err); else resolve(String(stdout).trim());
    });
  });
}

const V1_NAME = 'Focus Board';
const DTT_NAME = 'Focusboard V2';

function dttAppPath() {
  if (app.isPackaged) {
    // .../Focusboard V2.app/Contents/MacOS/бинарь → корень бандла
    const m = process.execPath.match(/^(.*?\.app)\//);
    if (m) return m[1];
  }
  return `/Applications/${DTT_NAME}.app`;
}

// v1 автозапускается через launchd-агент com.focusboard.app (не через Login Items)
const V1_AGENT_PLIST = path.join(require('os').homedir(), 'Library', 'LaunchAgents', 'com.focusboard.app.plist');

function v1AgentLoaded() {
  return new Promise(resolve => {
    execFile('launchctl', ['list', 'com.focusboard.app'], { timeout: 8000 },
      err => resolve(!err));
  });
}

function setV1Autostart(enabled) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(V1_AGENT_PLIST)) return reject(new Error('Агент v1 не найден: ' + V1_AGENT_PLIST));
    const args = enabled ? ['load', '-w', V1_AGENT_PLIST] : ['unload', '-w', V1_AGENT_PLIST];
    execFile('launchctl', args, { timeout: 8000 }, err => {
      // unload уже выгруженного (и наоборот) — не ошибка
      if (err && !/(not loaded|already loaded|No such process|service already loaded)/i.test(String(err.message))) reject(err);
      else resolve();
    });
  });
}

async function loginItemNames() {
  try {
    const out = await osa('tell application "System Events" to get the name of every login item');
    return out ? out.split(', ').map(s => s.trim()) : [];
  } catch { return []; }
}

async function setLoginItem(name, appPath, enabled) {
  const names = await loginItemNames();
  const has = names.includes(name);
  if (enabled && !has) {
    if (!appPath || !fs.existsSync(appPath)) throw new Error(`Приложение не найдено: ${appPath ?? name}`);
    await osa(`tell application "System Events" to make login item at end with properties {path:"${appPath}", hidden:false}`);
  }
  if (!enabled && has) {
    await osa(`tell application "System Events" to delete login item "${name}"`);
  }
}

async function handleAutostart(req, res) {
  const send = (code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(obj)); };
  try {
    if (req.method === 'GET') {
      const names = await loginItemNames();
      return send(200, {
        dtt: names.includes(DTT_NAME),
        v1: await v1AgentLoaded(),
        dtt_installed: fs.existsSync(dttAppPath()),
        v1_installed: fs.existsSync(V1_AGENT_PLIST),
      });
    }
    if (req.method === 'POST') {
      let body = '';
      req.on('data', c => { body += c; });
      req.on('end', async () => {
        try {
          const { target, enabled } = JSON.parse(body || '{}');
          if (target === 'dtt') await setLoginItem(DTT_NAME, dttAppPath(), !!enabled);
          else if (target === 'v1') await setV1Autostart(!!enabled);
          else return send(400, { error: 'target must be dtt|v1' });
          send(200, { ok: true });
        } catch (e) { send(500, { error: e.message }); }
      });
      return;
    }
    send(405, { error: 'method' });
  } catch (e) { send(500, { error: e.message }); }
}

// ── Статика + прокси, без зависимостей ────────────────────────────────────────
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.woff': 'font/woff', '.woff2': 'font/woff2',
  '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.map': 'application/json',
};

function proxy(req, res, port) {
  const p = http.request(
    { hostname: '127.0.0.1', port, path: req.url, method: req.method, headers: req.headers },
    r => { res.writeHead(r.statusCode || 502, r.headers); r.pipe(res); }
  );
  p.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
  req.pipe(p);
}

function startFrontend() {
  // Сервер поднимаем всегда: в dev он обслуживает только /app/* (vite проксирует)
  const server = http.createServer((req, res) => {
    if (req.url.startsWith('/app/autostart')) return handleAutostart(req, res);
    if (!useDist) { res.writeHead(404); return res.end(); }
    if (req.url.startsWith('/api2/')) return proxy(req, res, PORT_V2API);
    if (req.url.startsWith('/api/')) return proxy(req, res, PORT_BACKEND);

    let urlPath = decodeURIComponent((req.url.split('?')[0] || '/'));
    if (urlPath === '/') urlPath = '/index.html';
    let filePath = path.normalize(path.join(DIST_DIR, urlPath));
    if (!filePath.startsWith(DIST_DIR)) { res.writeHead(403); return res.end(); }

    fs.readFile(filePath, (err, data) => {
      if (err) {
        // SPA-фоллбек
        return fs.readFile(path.join(DIST_DIR, 'index.html'), (e2, index) => {
          if (e2) { res.writeHead(404); return res.end(); }
          res.writeHead(200, { 'Content-Type': MIME['.html'] });
          res.end(index);
        });
      }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath)] || 'application/octet-stream' });
      res.end(data);
    });
  });
  server.listen(PORT_FRONTEND, '127.0.0.1');
}

const APP_URL = useDist ? `http://localhost:${PORT_FRONTEND}` : `http://localhost:${PORT_DEV}`;

let win = null;

function loadWhenReady() {
  if (!win || win.isDestroyed()) return;
  const req = http.get(APP_URL, res => {
    res.destroy();
    if (win && !win.isDestroyed()) win.loadURL(APP_URL);
  });
  req.on('error', () => setTimeout(loadWhenReady, 500));
  req.setTimeout(1000, () => req.destroy());
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280, height: 800, minWidth: 900, minHeight: 600,
    title: APP_TITLE,
    backgroundColor: '#141312',
    icon: path.join(__dirname, 'icon.png'),
  });

  // В dev-запуске (electron .) ставим иконку дока вручную
  if (!app.isPackaged && process.platform === 'darwin' && app.dock) {
    try { app.dock.setIcon(path.join(__dirname, 'icon.png')); } catch {}
  }

  win.on('close', e => {
    if (!app.isQuitting) { e.preventDefault(); win.hide(); }
  });

  const wc = win.webContents;
  wc.on('render-process-gone', (_e, details) => {
    console.error('[dtt] render-process-gone:', details && details.reason);
    if (win && !win.isDestroyed()) loadWhenReady();
  });
  wc.on('did-fail-load', (_e, code, desc, _url, isMainFrame) => {
    if (isMainFrame && code !== -3) {
      console.error('[dtt] did-fail-load:', code, desc);
      setTimeout(loadWhenReady, 800);
    }
  });
  wc.on('unresponsive', () => {
    console.error('[dtt] renderer unresponsive — reloading');
    if (win && !win.isDestroyed()) win.reload();
  });

  loadWhenReady();
}

// ── Утреннее напоминание спланировать день ────────────────────────────────────
// Пока сегодняшний чек-ин не заполнен и время в утреннем окне — каждые 30 минут
// шлём нативное уведомление «сядь и заполни утро». Как только чек-ин появился —
// молчим до завтра. Состояние переживает перезапуск (launchd KeepAlive).
const NUDGE_START_HOUR = 7;                 // с 07:00
const NUDGE_END_HOUR = 12;                  // до 12:00 (не позже)
const NUDGE_EVERY_MS = 30 * 60 * 1000;      // раз в полчаса
const nudgeStatePath = () => path.join(app.getPath('userData'), 'morning-nudge.json');

function readNudgeState() {
  try { return JSON.parse(fs.readFileSync(nudgeStatePath(), 'utf8')); } catch { return {}; }
}
function writeNudgeState(s) {
  try { fs.writeFileSync(nudgeStatePath(), JSON.stringify(s)); } catch {}
}

function fetchTodayCheckin() {
  return new Promise(resolve => {
    const req = http.get(`http://127.0.0.1:${PORT_BACKEND}/api/journal/today-checkin`, res => {
      let b = ''; res.on('data', c => { b += c; });
      res.on('end', () => { try { resolve(JSON.parse(b)); } catch { resolve(null); } });
    });
    req.on('error', () => resolve(null));
    req.setTimeout(2500, () => req.destroy());
  });
}

function openMorning() {
  if (!win || win.isDestroyed()) createWindow();
  if (win && !win.isDestroyed()) {
    win.show();
    win.focus();
    if (app.dock) { try { app.dock.show(); } catch {} }
    try { win.loadURL(APP_URL + '#morning'); } catch {}
  }
}

async function checkMorningNudge() {
  if (!Notification.isSupported()) return;
  const now = new Date();
  const hour = now.getHours();
  if (hour < NUDGE_START_HOUR || hour >= NUDGE_END_HOUR) return;

  const today = now.toISOString().slice(0, 10);
  const st = readNudgeState();
  if (st.doneDate === today) return;                        // сегодня уже заполнил

  const checkin = await fetchTodayCheckin();
  if (checkin && checkin.exists) { writeNudgeState({ doneDate: today }); return; }

  const last = st.date === today ? (st.lastAt || 0) : 0;
  if (Date.now() - last < NUDGE_EVERY_MS) return;           // ещё не прошло полчаса

  const n = new Notification({
    title: 'Focus Board · пора спланировать день',
    body: 'Сядь за комп и заполни утренний экран — выбери миссии на сегодня.',
    silent: false,
  });
  n.on('click', openMorning);
  n.show();
  writeNudgeState({ date: today, lastAt: Date.now() });
}

app.on('before-quit', () => {
  app.isQuitting = true;
  if (v2ApiChild) { try { v2ApiChild.kill(); } catch {} }
  if (backendChild) { try { backendChild.kill(); } catch {} }
});

app.whenReady().then(async () => {
  try { await ensureBackend(); } catch (e) { console.error('[dtt] backend:', e.message); }
  try { await ensureV2Api(); } catch (e) { console.error('[dtt] v2-api:', e.message); }
  startFrontend();
  createWindow();
  // Утренний «ежик»: проверяем каждую минуту, шлём не чаще чем раз в полчаса.
  setTimeout(() => { checkMorningNudge().catch(() => {}); }, 5000);
  setInterval(() => { checkMorningNudge().catch(() => {}); }, 60 * 1000);
});

app.on('activate', () => {
  if (win && !win.isDestroyed()) win.show();
  else createWindow();
});
