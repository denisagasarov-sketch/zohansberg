const { app, BrowserWindow } = require('electron');
const path = require('path');
const http = require('http');
const net = require('net');
const express = require('express');

const isProd = app.isPackaged;
const PORT_BACKEND = 3001;
const PORT_FRONTEND = 4173;

// The real data lives in backend/data/focus.db, served by the launchd backend
// service (com.focusboard.backend, KeepAlive) on port 3001. We REUSE that — the
// data layer stays a single always-on process that restarts itself. Only if 3001
// is somehow down do we start an in-process backend as a fallback, pointing at
// the same real DB file so there's never a second, divergent database.
function portOpen(port) {
  return new Promise(resolve => {
    const s = net.connect(port, '127.0.0.1');
    s.setTimeout(700);
    s.on('connect', () => { s.destroy(); resolve(true); });
    s.on('timeout', () => { s.destroy(); resolve(false); });
    s.on('error', () => resolve(false));
  });
}

async function ensureBackend() {
  if (await portOpen(PORT_BACKEND)) {
    console.log('[electron] backend already on 3001 — reusing it');
    return;
  }
  console.log('[electron] no backend on 3001 — starting in-process fallback');
  // Resolve relative to this file so the app survives folder renames/moves.
  process.env.DB_PATH = process.env.DB_PATH
    || path.join(__dirname, '..', 'backend', 'data', 'focus.db');
  require(path.join(__dirname, '..', 'backend', 'server.js'));
}

// In prod, serve the bundled frontend on 4173 (its own origin, allowed by CORS).
function startFrontend() {
  if (!isProd) return;
  const fe = express();
  // The frontend calls the API on the RELATIVE path /api (see frontend/src/api.ts).
  // The vite dev server proxies /api → :3001; the static server must do the same,
  // or every data request 404s against the static files and the app shows nothing.
  fe.use('/api', (req, res) => {
    const proxyReq = http.request(
      { hostname: '127.0.0.1', port: PORT_BACKEND, path: '/api' + req.url, method: req.method, headers: req.headers },
      proxyRes => { res.writeHead(proxyRes.statusCode || 502, proxyRes.headers); proxyRes.pipe(res); }
    );
    proxyReq.on('error', () => { if (!res.headersSent) res.writeHead(502); res.end(); });
    req.pipe(proxyReq);
  });
  fe.use(express.static(path.join(__dirname, '..', 'frontend', 'dist')));
  fe.listen(PORT_FRONTEND);
}

const APP_URL = isProd ? `http://localhost:${PORT_FRONTEND}` : 'http://localhost:5173';

let win = null;

// Wait until the server actually answers before loading — avoids the blank
// "can't connect" page when the window opens faster than express/vite. Retries forever.
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
  win = new BrowserWindow({ width: 1280, height: 800, minWidth: 900, minHeight: 600, icon: path.join(__dirname, 'icon.png') });

  // Closing the window only hides it — keep the app (and backend) alive.
  win.on('close', e => {
    if (!app.isQuitting) { e.preventDefault(); win.hide(); }
  });

  const wc = win.webContents;

  // Renderer died (OOM, GPU reset, JS engine crash, heavy canvas) → reload instead
  // of leaving a frozen blank window. This is the "crashes and won't come back" fix.
  wc.on('render-process-gone', (_e, details) => {
    console.error('[electron] render-process-gone:', details && details.reason);
    if (win && !win.isDestroyed()) loadWhenReady();
  });

  // Page failed to load (server not up yet / transient) → retry. -3 is ERR_ABORTED,
  // which fires normally during reloads and must be ignored.
  wc.on('did-fail-load', (_e, code, desc, _url, isMainFrame) => {
    if (isMainFrame && code !== -3) {
      console.error('[electron] did-fail-load:', code, desc);
      setTimeout(loadWhenReady, 800);
    }
  });

  // Renderer hung → reload it.
  wc.on('unresponsive', () => {
    console.error('[electron] renderer unresponsive — reloading');
    if (win && !win.isDestroyed()) win.reload();
  });

  loadWhenReady();
}

app.on('before-quit', () => { app.isQuitting = true; });

app.whenReady().then(async () => {
  await ensureBackend();
  startFrontend();
  createWindow();
});

// Dock click / reopen: bring back the hidden window, or recreate it if it's gone.
app.on('activate', () => {
  if (win && !win.isDestroyed()) win.show();
  else createWindow();
});
