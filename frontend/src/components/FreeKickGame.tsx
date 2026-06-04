import { useRef, useEffect, useState } from 'react'

// ── 8-bit audio ───────────────────────────────────────────────────────────────
let audioCtx: AudioContext | null = null
function ac() {
  if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
  return audioCtx
}
function tone(freq: number, dur: number, type: OscillatorType, vol: number, at = 0) {
  const c = ac()
  const t = (c.state !== 'running' ? c.currentTime + 0.05 : c.currentTime) + at
  const o = c.createOscillator(), g = c.createGain()
  o.type = type; o.frequency.setValueAtTime(Math.max(freq, 1), t)
  g.gain.setValueAtTime(vol, t)
  g.gain.exponentialRampToValueAtTime(0.0005, t + dur)
  o.connect(g); g.connect(c.destination)
  o.start(t); o.stop(t + dur + 0.02)
}
const sndKick = () => tone(200, 0.08, 'square', 0.16)
const sndGoal = () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.13, 'square', 0.15, i * 0.09))
const sndMiss = () => tone(160, 0.3, 'sawtooth', 0.16)
const sndSave = () => { tone(300, 0.1, 'square', 0.14); tone(180, 0.18, 'square', 0.12, 0.08) }

interface Stats { goals: number; shots: number }
const STAT_KEY = 'freekick_stats'
function loadStats(): Stats {
  try { return { goals: 0, shots: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { goals: 0, shots: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

const H = 340
const FLIGHT_MS = 1500
const CHARGE_PER_S = 75
type Phase = 'aim' | 'fly' | 'done'

export default function FreeKickGame() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [aimX, setAimX] = useState(0.5)   // 0..1 across goal
  const [aimY, setAimY] = useState(0.4)   // 0..1 down the goal
  const [spin, setSpin] = useState(0)     // -100..100
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [phase, setPhase] = useState<Phase>('aim')
  const [msg, setMsg] = useState('')
  const [stats, setStats] = useState<Stats>(loadStats)

  const s = useRef({
    W: 600, phase: 'aim' as Phase,
    aimX: 0.5, aimY: 0.4, spin: 0, power: 0,
    charging: false, chargeStart: 0,
    t: 0, gkDir: 0, gkGuess: 0,
    keys: {} as Record<string, boolean>,
  })
  const refs = { aimX, aimY, spin, power, phase }
  const r = useRef(refs); r.current = refs

  const bumpStat = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

  // geometry helpers (depend on W)
  const geo = (W: number) => {
    const gw = W * 0.5, gh = H * 0.3
    const gx = (W - gw) / 2, gy = H * 0.1
    return { gw, gh, gx, gy, ballX0: W / 2, ballY0: H * 0.95, wallY: H * 0.56 }
  }

  useEffect(() => {
    const canvas = canvasRef.current!, c = canvas.getContext('2d')!
    const W = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr
    c.setTransform(dpr, 0, 0, dpr, 0, 0)
    s.current.W = W

    let raf = 0, last = performance.now()
    const loop = (now: number) => {
      const dt = now - last; last = now
      update(dt)
      render(c, W)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ball screen position for progress p (0..1)
  const ballPos = (W: number, p: number) => {
    const g = geo(W)
    const tx = g.gx + r.current.aimX * g.gw
    const ty = g.gy + r.current.aimY * g.gh
    const ease = 1 - (1 - p) * (1 - p)
    const baseX = g.ballX0 + (tx - g.ballX0) * p
    const curve = (r.current.spin / 100) * (W * 0.22) * Math.sin(Math.PI * p)
    const x = baseX + curve
    const sag = (1 - r.current.power / 100) * 120 * (p * p) // weak shots drop
    const y = g.ballY0 + (ty - g.ballY0) * ease + sag
    const scale = 1 - 0.62 * p
    return { x, y, scale, tx, ty }
  }

  const update = (dt: number) => {
    const st = s.current, W = st.W
    if (st.phase === 'aim') {
      // aim move
      if (st.keys['ArrowLeft']) { st.aimX = Math.max(0.05, st.aimX - dt / 1400); setAimX(st.aimX) }
      if (st.keys['ArrowRight']) { st.aimX = Math.min(0.95, st.aimX + dt / 1400); setAimX(st.aimX) }
      if (st.keys['ArrowUp']) { st.aimY = Math.max(0.05, st.aimY - dt / 1400); setAimY(st.aimY) }
      if (st.keys['ArrowDown']) { st.aimY = Math.min(0.95, st.aimY + dt / 1400); setAimY(st.aimY) }
      if (st.keys['a'] || st.keys['A']) { st.spin = Math.max(-100, st.spin - dt / 12); setSpin(Math.round(st.spin)) }
      if (st.keys['d'] || st.keys['D']) { st.spin = Math.min(100, st.spin + dt / 12); setSpin(Math.round(st.spin)) }
      if (st.charging) { st.power = Math.min(100, st.power + dt / 1000 * CHARGE_PER_S); setPower(Math.round(st.power)) }
    } else if (st.phase === 'fly') {
      st.t += dt / FLIGHT_MS
      const p = Math.min(1, st.t)
      // wall block check around mid-flight
      if (p >= 0.46 && p <= 0.6) {
        const b = ballPos(W, p)
        const wallCx = W / 2, wallHalf = W * 0.11
        if (Math.abs(b.x - wallCx) < wallHalf && b.y > geo(W).wallY - 26) {
          finish('СТЕНКА', false); return
        }
      }
      if (p >= 1) {
        const b = ballPos(W, 1)
        const g = geo(W)
        const inGoal = b.x > g.gx && b.x < g.gx + g.gw && b.y > g.gy && b.y < g.gy + g.gh
        // keeper at goal line
        const gkX = W / 2 + st.gkGuess * (g.gw * 0.42)
        const caught = Math.abs(b.x - gkX) < W * 0.07
        if (!inGoal) finish('МИМО', false)
        else if (caught) finish('СЕЙВ', false)
        else finish('⚽ ГОЛ!', true)
      }
    }
  }

  const finish = (m: string, goal: boolean) => {
    const st = s.current
    st.phase = 'done'; setPhase('done'); setMsg(m)
    if (goal) { sndGoal(); bumpStat('goals') }
    else if (m === 'СЕЙВ') sndSave()
    else sndMiss()
  }

  const kick = () => {
    const st = s.current
    if (st.phase !== 'aim' || st.power < 5) return
    st.charging = false; setCharging(false)
    st.t = 0; st.phase = 'fly'; setPhase('fly')
    st.gkGuess = [-1, 0, 1][Math.floor(Math.random() * 3)] // keeper guesses a third
    sndKick()
    bumpStat('shots')
  }

  const reset = () => {
    const st = s.current
    st.phase = 'aim'; setPhase('aim'); setMsg('')
    st.power = 0; setPower(0); st.charging = false; setCharging(false)
    st.t = 0
  }

  const render = (c: CanvasRenderingContext2D, W: number) => {
    const st = s.current, g = geo(W)
    // sky + pitch
    c.fillStyle = '#0d1a10'; c.fillRect(0, 0, W, H)
    c.fillStyle = '#16361f'; c.fillRect(0, g.gy + g.gh * 0.4, W, H)
    // pitch stripes
    c.fillStyle = '#1a3d24'
    for (let i = 0; i < 6; i++) {
      const y = g.gy + g.gh * 0.4 + i * (H - g.gy - g.gh * 0.4) / 6
      if (i % 2 === 0) c.fillRect(0, y, W, (H - g.gy - g.gh * 0.4) / 6)
    }
    // goal frame + net
    c.strokeStyle = '#fff'; c.lineWidth = 4
    c.strokeRect(g.gx, g.gy, g.gw, g.gh)
    c.strokeStyle = '#ffffff33'; c.lineWidth = 1
    for (let i = 1; i < 8; i++) { const x = g.gx + (g.gw / 8) * i; c.beginPath(); c.moveTo(x, g.gy); c.lineTo(x, g.gy + g.gh); c.stroke() }
    for (let i = 1; i < 5; i++) { const y = g.gy + (g.gh / 5) * i; c.beginPath(); c.moveTo(g.gx, y); c.lineTo(g.gx + g.gw, y); c.stroke() }

    // keeper
    const gkX = st.phase === 'done' || st.phase === 'fly' ? W / 2 + st.gkGuess * (g.gw * 0.42) : W / 2
    c.fillStyle = '#ffd24c'
    c.fillRect(gkX - 7, g.gy + g.gh - 26, 14, 26)
    c.beginPath(); c.arc(gkX, g.gy + g.gh - 30, 5, 0, Math.PI * 2); c.fill()

    // wall (players)
    const wallCx = W / 2, wallHalf = W * 0.11
    const n = 4, pw = (wallHalf * 2) / n
    for (let i = 0; i < n; i++) {
      const x = wallCx - wallHalf + pw * i + pw / 2
      c.fillStyle = '#3a6ad0'
      c.fillRect(x - pw * 0.32, g.wallY - 26, pw * 0.64, 26)
      c.beginPath(); c.arc(x, g.wallY - 30, 5, 0, Math.PI * 2); c.fill()
    }

    // aim marker (during aim)
    if (st.phase === 'aim') {
      const tx = g.gx + r.current.aimX * g.gw, ty = g.gy + r.current.aimY * g.gh
      c.strokeStyle = '#ff5c5c'; c.lineWidth = 2
      c.beginPath(); c.arc(tx, ty, 7, 0, Math.PI * 2); c.stroke()
      c.beginPath(); c.moveTo(tx - 10, ty); c.lineTo(tx + 10, ty); c.moveTo(tx, ty - 10); c.lineTo(tx, ty + 10); c.stroke()
      // predicted dotted curve
      c.fillStyle = '#ffffffaa'
      for (let i = 1; i <= 18; i++) {
        const b = ballPos(W, i / 18)
        c.beginPath(); c.arc(b.x, b.y, 1.5, 0, Math.PI * 2); c.fill()
      }
    }

    // ball
    const bp = st.phase === 'fly' ? ballPos(W, Math.min(1, st.t)) : { x: g.ballX0, y: g.ballY0, scale: 1 }
    const rad = 11 * bp.scale
    c.fillStyle = '#fff'; c.beginPath(); c.arc(bp.x, bp.y, rad, 0, Math.PI * 2); c.fill()
    c.fillStyle = '#000'; c.beginPath(); c.arc(bp.x, bp.y, rad * 0.4, 0, Math.PI * 2); c.fill()
  }

  // keyboard
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const k = e.key
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'a', 'A', 'd', 'D', 'ф', 'Ф', 'в', 'В'].includes(k)) return
      e.preventDefault()
      const st = s.current
      if (st.phase === 'done') { if (k === ' ') reset(); return }
      if (st.phase !== 'aim') return
      const nk = (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k
      st.keys[nk] = true
      if (k === ' ' && !st.charging) { st.charging = true; setCharging(true); st.chargeStart = Date.now() }
    }
    const up = (e: KeyboardEvent) => {
      const st = s.current
      const k = e.key
      const nk = (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k
      st.keys[nk] = false
      if (k === ' ' && st.charging && st.phase === 'aim') kick()
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const acc = stats.shots ? Math.round((stats.goals / stats.shots) * 100) : 0

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span className={charging ? 'text-[#5cc8ff]' : ''}>СИЛА {Math.round(power)}</span>
        <span className={spin !== 0 ? 'text-[#ff9f5c]' : ''}>КРУЧ {spin > 0 ? '↻' : spin < 0 ? '↺' : ''}{Math.abs(spin)}</span>
        <span className="flex-1 text-right">{msg || (phase === 'fly' ? '…' : 'целься и бей')}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ↑ ↓ точка · A/D кручёный · пробел (держать) — сила/удар{msg ? ' · пробел — ещё' : ''}</span>
        <span>голы {stats.goals}/{stats.shots}{stats.shots ? ` · ${acc}%` : ''}</span>
      </div>
    </div>
  )
}
