const { app, BrowserWindow, shell } = require('electron')
const { spawn } = require('child_process')
const path = require('path')
const http = require('http')

const BACKEND_PORT = 3001
const FRONTEND_PORT = 4173

let mainWindow = null
let backendProc = null
let frontendProc = null

// ─── Child process helpers ────────────────────────────────────────────────────

function startBackend() {
  const serverPath = path.join(__dirname, '..', 'backend', 'server.js')
  backendProc = spawn(process.execPath, [serverPath], {
    cwd: path.join(__dirname, '..', 'backend'),
    env: { ...process.env, PORT: String(BACKEND_PORT) },
    stdio: 'inherit',
  })
  backendProc.on('error', err => console.error('backend error:', err))
}

function buildAndServeFrontend() {
  return new Promise((resolve, reject) => {
    const frontendDir = path.join(__dirname, '..', 'frontend')

    // Build first, then preview
    const build = spawn('npm', ['run', 'build'], {
      cwd: frontendDir,
      stdio: 'inherit',
      shell: true,
    })

    build.on('close', code => {
      if (code !== 0) return reject(new Error(`Frontend build failed (exit ${code})`))

      frontendProc = spawn('npm', ['run', 'preview', '--', '--host', '--port', String(FRONTEND_PORT)], {
        cwd: frontendDir,
        stdio: 'inherit',
        shell: true,
      })
      frontendProc.on('error', err => console.error('frontend error:', err))

      // Wait until preview is serving
      waitForPort(FRONTEND_PORT, 30000).then(resolve).catch(reject)
    })
  })
}

function waitForPort(port, timeout = 20000) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`http://localhost:${port}`, () => resolve())
      req.on('error', () => {
        if (Date.now() - start > timeout) return reject(new Error(`Timeout waiting for port ${port}`))
        setTimeout(check, 300)
      })
      req.end()
    }
    check()
  })
}

function killChildren() {
  if (backendProc) { try { backendProc.kill() } catch {} backendProc = null }
  if (frontendProc) { try { frontendProc.kill() } catch {} frontendProc = null }
}

// ─── Window ───────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    icon: path.join(__dirname, 'icon.png'),
    backgroundColor: '#181818',
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  mainWindow.loadURL(`http://localhost:${FRONTEND_PORT}`)

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http')) shell.openExternal(url)
    return { action: 'deny' }
  })

  // Closing window hides it — app stays in Dock and menu bar
  mainWindow.on('close', e => {
    if (!app.isQuitting) {
      e.preventDefault()
      mainWindow.hide()
    }
  })

  mainWindow.on('closed', () => { mainWindow = null })
}

// ─── App lifecycle ────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  startBackend()

  try {
    // Wait for backend to be ready, then start frontend
    await waitForPort(BACKEND_PORT, 15000)
    await buildAndServeFrontend()
  } catch (err) {
    console.error('Startup failed:', err)
  }

  createWindow()

  // Re-show window when clicking Dock icon
  app.on('activate', () => {
    if (mainWindow) {
      mainWindow.show()
    } else {
      createWindow()
    }
  })
})

app.on('before-quit', () => { app.isQuitting = true })
app.on('will-quit', killChildren)

// Keep app alive when all windows closed (macOS behaviour)
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    killChildren()
    app.quit()
  }
})
