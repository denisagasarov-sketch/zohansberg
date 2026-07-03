import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// --- Crash resilience for the standalone window (Safari Web App / Electron) ---
// A web-app window doesn't recover from a React white-screen on its own. When the
// tree throws, auto-reload — but guard against a reload loop from a deterministic
// crash: after a few reloads in a short window, stop and show a manual button.
// Ship every JS-level error to the backend so a crash in the standalone window
// (no devtools) leaves a trace in backend/client-errors.log.
function report(kind: string, message: string, stack?: string) {
  try {
    fetch('http://localhost:3001/api/client-error', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, message, stack, url: location.href, userAgent: navigator.userAgent, ts: Date.now() }),
      keepalive: true,
    }).catch(() => { /* ignore */ })
  } catch { /* ignore */ }
}
window.addEventListener('error', e => report('window.error', e.message, (e.error && e.error.stack) || undefined))
window.addEventListener('unhandledrejection', e => report('unhandledrejection', String(e.reason), e.reason && e.reason.stack))

const RELOAD_KEY = 'fb_reload_ts'
function reloadGuarded(): boolean {
  try {
    const now = Date.now()
    const hist: number[] = JSON.parse(sessionStorage.getItem(RELOAD_KEY) || '[]')
      .filter((t: number) => now - t < 12000)
    hist.push(now)
    sessionStorage.setItem(RELOAD_KEY, JSON.stringify(hist))
    if (hist.length > 3) return false // looping — let the boundary show a button
    location.reload()
    return true
  } catch {
    location.reload()
    return true
  }
}

class RootBoundary extends React.Component<{ children: React.ReactNode }, { crashed: boolean }> {
  state = { crashed: false }
  static getDerivedStateFromError() { return { crashed: true } }
  componentDidCatch(err: unknown) {
    console.error('[RootBoundary]', err)
    const e = err as Error
    report('react', e && e.message ? e.message : String(err), e && e.stack)
    if (!reloadGuarded()) this.setState({ crashed: true })
  }
  render() {
    if (this.state.crashed) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, background: '#181818', color: '#f0f0f0', fontFamily: 'system-ui, sans-serif' }}>
          <div style={{ fontSize: 14, color: '#999' }}>Приложение перезапускалось несколько раз подряд</div>
          <button
            onClick={() => { try { sessionStorage.removeItem(RELOAD_KEY) } catch { /* ignore */ } location.reload() }}
            style={{ padding: '8px 18px', fontSize: 13, borderRadius: 6, border: '1px solid #333', background: '#252525', color: '#f0f0f0', cursor: 'pointer' }}
          >
            Перезагрузить
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RootBoundary>
      <App />
    </RootBoundary>
  </React.StrictMode>
)
