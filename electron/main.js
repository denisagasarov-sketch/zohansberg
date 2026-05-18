const { app, BrowserWindow } = require('electron');
const path = require('path');
const express = require('express');

const isProd = app.isPackaged;
const PORT_BACKEND = 3001;
const PORT_FRONTEND = 4173;

// Pass DB path to backend before requiring it
process.env.DB_PATH = app.isPackaged
  ? path.join(app.getPath('userData'), 'focusboard.db')
  : path.join(__dirname, '..', 'backend', 'focusboard.db');

// Start backend
require(path.join(__dirname, '..', 'backend', 'server.js'));

// In prod — serve frontend dist via express
if (isProd) {
  const fe = express();
  const distPath = path.join(__dirname, '..', 'frontend', 'dist');
  fe.use(express.static(distPath));
  fe.listen(PORT_FRONTEND);
}

function createWindow() {
  const win = new BrowserWindow({ width: 1280, height: 800, minWidth: 900, minHeight: 600, icon: path.join(__dirname, 'icon.png') });
  const url = isProd ? `http://localhost:${PORT_FRONTEND}` : 'http://localhost:5173';
  setTimeout(() => win.loadURL(url), 2000);
  win.on('close', e => { e.preventDefault(); win.hide(); });
}

app.whenReady().then(createWindow);
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
