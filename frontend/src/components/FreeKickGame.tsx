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
function noise(dur: number, vol: number) {
  const c = ac(); const t = c.state !== 'running' ? c.currentTime + 0.05 : c.currentTime
  const n = Math.floor(c.sampleRate * dur), buf = c.createBuffer(1, n, c.sampleRate), d = buf.getChannelData(0)
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / n)
  const src = c.createBufferSource(), g = c.createGain()
  src.buffer = buf; g.gain.value = vol; src.connect(g); g.connect(c.destination); src.start(t)
}
const sndKick = () => tone(200, 0.08, 'square', 0.16)
const sndGoal = () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.13, 'square', 0.15, i * 0.09))
const sndMiss = () => tone(160, 0.3, 'sawtooth', 0.16)
const sndSave = () => { tone(300, 0.1, 'square', 0.14); tone(180, 0.18, 'square', 0.12, 0.08) }
const sndPost = () => { tone(900, 0.05, 'square', 0.18); tone(600, 0.12, 'square', 0.12, 0.05) }
const sndWhistle = () => { tone(1800, 0.12, 'square', 0.1); tone(2200, 0.1, 'square', 0.08, 0.1) }
const sndRoar = () => { noise(0.9, 0.18); [1, 2, 3, 4].forEach(i => tone(200 + Math.random() * 300, 0.5, 'sawtooth', 0.05, i * 0.05)) }
const sndTop = () => [1047, 1319, 1568].forEach((f, i) => tone(f, 0.12, 'square', 0.16, i * 0.07))

interface Stats { goals: number; shots: number; best: number }
const STAT_KEY = 'freekick_stats'
function loadStats(): Stats {
  try { return { goals: 0, shots: 0, best: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { goals: 0, shots: 0, best: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

const H = 340
const FLIGHT_MS = 1600
const CHARGE_PER_S = 75
const SERIES = 5
type Phase = 'aim' | 'fly' | 'done' | 'series'

const SPOTS_TEX = (() => {
  const a: { lon: number; lat: number }[] = [{ lon: 0, lat: 0 }]
  for (let i = 0; i < 5; i++) a.push({ lon: (i / 5) * Math.PI * 2, lat: -0.7 })
  for (let i = 0; i < 5; i++) a.push({ lon: (i / 5) * Math.PI * 2 + 0.6, lat: 0.7 })
  return a
})()

export default function FreeKickGame() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [aimX, setAimX] = useState(0.5)
  const [aimY, setAimY] = useState(0.4)
  const [spin, setSpin] = useState(0)
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [phase, setPhase] = useState<Phase>('aim')
  const [msg, setMsg] = useState('')
  const [stats, setStats] = useState<Stats>(loadStats)
  const [attempt, setAttempt] = useState(1)
  const [scored, setScored] = useState(0)
  const [streak, setStreak] = useState(0)
  const [wind, setWind] = useState(0)
  const [weather, setWeather] = useState<'clear' | 'rain'>('clear')

  const s = useRef({
    W: 600, phase: 'aim' as Phase,
    aimX: 0.5, aimY: 0.4, spin: 0, power: 0,
    charging: false, t: 0,
    spot: { bx: 0.5, by: 0.92, label: '' } as { bx: number; by: number; label: string },
    ballPhase: 0, spinSpeed: 0,
    gkX: 0, gkDir: 0, gkCommitted: false, gkJump: 0,
    gkReact: 0.42, gkReach: 1, gkSmart: false, gkLag: 120, gkFumble: 1,
    wallJump: 0, netShake: 0,
    wind: 0, weather: 'clear' as 'clear' | 'rain',
    trail: [] as { x: number; y: number; r: number }[],
    rain: [] as { x: number; y: number; v: number }[],
    dodgeIdx: -1, dodge: 0,
    rebound: null as { vx: number; t: number } | null,
    ballInNet: 0,
    attempt: 1, scored: 0, streak: 0,
    crowd: [] as { x: number; y: number; c: string }[],
    keys: {} as Record<string, boolean>,
  })
  const r = useRef({ aimX, aimY, spin, power, phase })
  r.current = { aimX, aimY, spin, power, phase }

  const geo = (W: number) => { const gw = W * 0.46, gh = H * 0.3; return { gw, gh, gx: (W - gw) / 2, gy: H * 0.1 } }
  const newSpot = () => {
    const opts = [
      { bx: 0.5, by: 0.94, label: 'по центру' }, { bx: 0.28, by: 0.9, label: 'слева' },
      { bx: 0.72, by: 0.9, label: 'справа' }, { bx: 0.4, by: 0.86, label: 'полукруг' },
      { bx: 0.62, by: 0.96, label: 'острый угол' },
    ]
    return opts[Math.floor(Math.random() * opts.length)]
  }

  useEffect(() => {
    const canvas = canvasRef.current!, c = canvas.getContext('2d')!
    const W = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr
    c.setTransform(dpr, 0, 0, dpr, 0, 0)
    const st = s.current
    st.W = W; st.gkX = W / 2
    // crowd dots
    const g = geo(W); st.crowd = []
    const cols = ['#888', '#aaa', '#c0c0c0', '#999', '#b08', '#08b', '#5cc8ff', '#ff9f5c']
    for (let i = 0; i < 160; i++) st.crowd.push({ x: Math.random() * W, y: 6 + Math.random() * (g.gy - 8), c: cols[Math.floor(Math.random() * cols.length)] })
    startSeries(true)

    let raf = 0, last = performance.now()
    const loop = (now: number) => { const dt = Math.min(40, now - last); last = now; update(dt); render(c, W); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startSeries = (first = false) => {
    const st = s.current
    st.attempt = 1; setAttempt(1); st.scored = 0; setScored(0)
    nextShot(first)
  }

  const nextShot = (silent = false) => {
    const st = s.current
    st.phase = 'aim'; setPhase('aim'); setMsg('')
    st.power = 0; setPower(0); st.charging = false; setCharging(false)
    st.t = 0; st.gkX = st.W / 2; st.gkJump = 0; st.wallJump = 0; st.netShake = 0
    st.trail = []; st.rebound = null; st.ballInNet = 0
    st.spot = newSpot(); st.aimX = 0.5; setAimX(0.5); st.aimY = 0.4; setAimY(0.4)
    st.wind = (Math.random() - 0.5) * 0.16; setWind(st.wind)
    st.weather = Math.random() < 0.35 ? 'rain' : 'clear'; setWeather(st.weather)
    st.rain = []
    if (st.weather === 'rain') for (let i = 0; i < 70; i++) st.rain.push({ x: Math.random() * st.W, y: Math.random() * H, v: 4 + Math.random() * 3 })
    // cowardly wall player sometimes
    st.dodgeIdx = Math.random() < 0.3 ? Math.floor(Math.random() * 4) : -1; st.dodge = 0
    if (!silent) sndWhistle()
  }

  const ballStart = (W: number) => ({ x: s.current.spot.bx * W, y: s.current.spot.by * H })

  const ballPos = (W: number, p: number) => {
    const g = geo(W), start = ballStart(W)
    const tx = g.gx + r.current.aimX * g.gw, ty = g.gy + r.current.aimY * g.gh
    const ease = 1 - (1 - p) * (1 - p)
    const baseX = start.x + (tx - start.x) * p
    const curve = (r.current.spin / 100) * (W * 0.26) * Math.sin(Math.PI * p)
    const windOff = s.current.wind * W * 0.5 * p * p
    const x = baseX + curve + windOff
    const sag = (1 - r.current.power / 100) * 150 * (p * p)
    const lift = (r.current.power / 100) * 18 * Math.sin(Math.PI * p)
    const y = start.y + (ty - start.y) * ease + sag - lift
    return { x, y, scale: 1 - 0.6 * p, tx, ty }
  }

  const update = (dt: number) => {
    const st = s.current, W = st.W
    st.ballPhase += (st.phase === 'fly' ? st.spinSpeed : 0.0009) * dt
    if (st.netShake > 0) st.netShake = Math.max(0, st.netShake - dt)
    if (st.dodgeIdx >= 0 && st.phase === 'fly') st.dodge = Math.min(1, st.dodge + dt / 300)
    for (const rp of st.rain) { rp.y += rp.v; rp.x += st.wind * 20; if (rp.y > H) { rp.y = -5; rp.x = Math.random() * W } }

    if (st.phase === 'aim') {
      if (st.keys['ArrowLeft']) { st.aimX = Math.max(-0.05, st.aimX - dt / 1500); setAimX(st.aimX) }
      if (st.keys['ArrowRight']) { st.aimX = Math.min(1.05, st.aimX + dt / 1500); setAimX(st.aimX) }
      if (st.keys['ArrowUp']) { st.aimY = Math.max(-0.05, st.aimY - dt / 1500); setAimY(st.aimY) }
      if (st.keys['ArrowDown']) { st.aimY = Math.min(0.95, st.aimY + dt / 1500); setAimY(st.aimY) }
      if (st.keys['a']) { st.spin = Math.max(-100, st.spin - dt / 12); setSpin(Math.round(st.spin)) }
      if (st.keys['d']) { st.spin = Math.min(100, st.spin + dt / 12); setSpin(Math.round(st.spin)) }
      if (st.charging) { st.power = Math.min(100, st.power + dt / 1000 * CHARGE_PER_S); setPower(Math.round(st.power)) }
    } else if (st.phase === 'fly') {
      const p0 = st.t
      const slow = p0 > 0.82 ? 0.4 : 1                 // slow-mo near goal
      st.t += (dt / FLIGHT_MS) * slow
      const p = Math.min(1, st.t), g = geo(W)
      st.wallJump = p < 0.6 ? Math.sin((p / 0.6) * Math.PI) * 26 : 0

      const b = ballPos(W, p)
      st.trail.push({ x: b.x, y: b.y, r: 13 * b.scale }); if (st.trail.length > 12) st.trail.shift()

      if (!st.gkCommitted && p >= st.gkReact) {
        const readP = st.gkSmart ? 0.95 : 0.5
        const rb = ballPos(W, readP)
        let dir = Math.sign(rb.x - W / 2)
        if (Math.random() < 0.12) dir = -dir || 1
        if (dir === 0) dir = Math.random() < 0.5 ? -1 : 1
        st.gkDir = dir; st.gkCommitted = true
      }
      if (st.gkCommitted) {
        const targetX = W / 2 + st.gkDir * g.gw * 0.4
        st.gkX += (targetX - st.gkX) * Math.min(1, dt / st.gkLag)
        st.gkJump = Math.min(1, st.gkJump + dt / 350)
      }

      // wall block (with possible gap from a dodging player)
      if (p >= 0.46 && p <= 0.58) {
        const wallCx = (ballStart(W).x + W / 2) / 2, wallHalf = W * 0.1
        const wallTopY = H * 0.56 - st.wallJump
        const n = 4, step = (wallHalf * 2) / n
        let blocked = Math.abs(b.x - wallCx) < wallHalf && b.y > wallTopY
        if (blocked && st.dodgeIdx >= 0) {
          const gapX = wallCx - wallHalf + step * st.dodgeIdx + step / 2
          if (Math.abs(b.x - gapX) < step / 2) blocked = false // slipped through the gap
        }
        if (blocked) { finish('СТЕНКА', false); return }
      }

      if (p >= 1) {
        const nearPost = Math.abs(b.x - g.gx) < 6 || Math.abs(b.x - (g.gx + g.gw)) < 6
        const atBarY = b.y > g.gy - 6 && b.y < g.gy + g.gh
        const inGoal = b.x > g.gx + 4 && b.x < g.gx + g.gw - 4 && b.y > g.gy + 4 && b.y < g.gy + g.gh
        const gkHandsY = g.gy + g.gh - 18 - st.gkJump * 22
        const caught = Math.hypot(b.x - st.gkX, b.y - gkHandsY) < W * 0.06 * st.gkReach * st.gkFumble
        // top-corner ("девятка") zones
        const topZone = g.gh * 0.34, sideZone = g.gw * 0.2
        const inTop = b.y < g.gy + topZone && (b.x < g.gx + sideZone || b.x > g.gx + g.gw - sideZone)
        if (nearPost && atBarY) { finish('ШТАНГА', false); sndPost(); st.rebound = { vx: (b.x < W / 2 ? -1 : 1) * 3, t: 0 } }
        else if (!inGoal) finish('МИМО', false)
        else if (caught) finish('СЕЙВ', false)
        else if (inTop) { st.netShake = 600; st.ballInNet = 1; finish('🎯 ДЕВЯТКА!', true) }
        else { st.netShake = 600; st.ballInNet = 1; finish('⚽ ГОЛ!', true) }
      }
    } else if (st.phase === 'done') {
      if (st.rebound) { st.rebound.t += dt; }
      if (st.ballInNet > 0 && st.ballInNet < 1.5) st.ballInNet += dt / 600
    }
  }

  const finish = (m: string, goal: boolean) => {
    const st = s.current
    st.phase = 'done'; setPhase('done'); setMsg(m)
    setStats(prev => {
      const n = { ...prev, shots: prev.shots + 1, goals: prev.goals + (goal ? 1 : 0) }
      if (goal) { st.streak += 1; setStreak(st.streak); if (st.streak > n.best) n.best = st.streak }
      else { st.streak = 0; setStreak(0) }
      saveStats(n); return n
    })
    if (goal) { st.scored += 1; setScored(st.scored); sndGoal(); setTimeout(sndRoar, 120); if (m.includes('ДЕВЯТКА')) sndTop() }
    else if (m === 'СЕЙВ') sndSave()
    else if (m !== 'ШТАНГА') sndMiss()
    // advance series after a short beat
    setTimeout(() => {
      const cur = s.current
      if (cur.phase !== 'done') return
      if (cur.attempt >= SERIES) { cur.phase = 'series'; setPhase('series') }
    }, 1100)
  }

  const kick = () => {
    const st = s.current
    if (st.phase !== 'aim' || st.power < 5) return
    st.charging = false; setCharging(false)
    st.t = 0; st.phase = 'fly'; setPhase('fly')
    st.gkCommitted = false; st.gkJump = 0; st.gkX = st.W / 2
    // difficulty scales with attempt and current streak
    const diff = (st.attempt - 1) * 0.08 + Math.min(st.streak, 6) * 0.05
    st.gkReact = 0.34 + Math.random() * 0.24
    st.gkSmart = Math.random() < (0.3 + diff)
    st.gkReach = 0.85 + Math.random() * 0.4 + diff * 0.3
    st.gkLag = 100 - diff * 30 + Math.random() * 70
    st.gkFumble = Math.random() < Math.max(0.05, 0.16 - diff) ? 0.4 : 1
    st.spinSpeed = (st.spin >= 0 ? 1 : -1) * (0.004 + Math.abs(st.spin) / 100 * 0.03)
    sndKick()
  }

  const advance = () => {
    const st = s.current
    if (st.phase === 'series') { startSeries(); return }
    if (st.phase === 'done') {
      st.attempt += 1; setAttempt(st.attempt)
      nextShot()
    }
  }

  const render = (c: CanvasRenderingContext2D, W: number) => {
    const st = s.current, g = geo(W)
    const kSize = g.gh * 0.62

    // evening sky gradient + floodlights
    const sky = c.createLinearGradient(0, 0, 0, g.gy + g.gh)
    sky.addColorStop(0, '#0a0a1e'); sky.addColorStop(1, '#10182a')
    c.fillStyle = sky; c.fillRect(0, 0, W, H)
    for (const lx of [W * 0.15, W * 0.85]) {
      const lg = c.createRadialGradient(lx, 0, 0, lx, 0, H * 0.7)
      lg.addColorStop(0, 'rgba(255,255,210,0.12)'); lg.addColorStop(1, 'rgba(255,255,210,0)')
      c.fillStyle = lg; c.fillRect(0, 0, W, H)
    }
    // stands + crowd
    c.fillStyle = '#0e0e16'; c.fillRect(0, 0, W, g.gy - 2)
    for (const m of st.crowd) { c.fillStyle = m.c; c.globalAlpha = 0.5; c.fillRect(m.x, m.y, 2, 2) }
    c.globalAlpha = 1
    // pitch
    c.fillStyle = '#16361f'; c.fillRect(0, g.gy + g.gh * 0.45, W, H)
    c.fillStyle = '#1a3d24'
    const py0 = g.gy + g.gh * 0.45
    for (let i = 0; i < 6; i++) { const y = py0 + i * (H - py0) / 6; if (i % 2 === 0) c.fillRect(0, y, W, (H - py0) / 6) }

    // goal
    const sh = st.netShake > 0 ? Math.sin(st.netShake / 30) * (st.netShake / 600) * 5 : 0
    c.strokeStyle = '#ffffff22'; c.lineWidth = 1
    for (let i = 1; i < 9; i++) { const x = g.gx + (g.gw / 9) * i + sh * Math.sin(i); c.beginPath(); c.moveTo(x, g.gy); c.lineTo(x, g.gy + g.gh); c.stroke() }
    for (let i = 1; i < 5; i++) { const y = g.gy + (g.gh / 5) * i; c.beginPath(); c.moveTo(g.gx, y); c.lineTo(g.gx + g.gw, y); c.stroke() }
    c.strokeStyle = '#fff'; c.lineWidth = 5; c.lineCap = 'round'
    c.beginPath(); c.moveTo(g.gx, g.gy + g.gh); c.lineTo(g.gx, g.gy); c.lineTo(g.gx + g.gw, g.gy); c.lineTo(g.gx + g.gw, g.gy + g.gh); c.stroke()
    // top-corner target zones
    if (st.phase === 'aim') {
      c.strokeStyle = '#ffd24c55'; c.lineWidth = 1; const tz = g.gh * 0.34, sz = g.gw * 0.2
      c.strokeRect(g.gx + 3, g.gy + 3, sz, tz); c.strokeRect(g.gx + g.gw - sz - 3, g.gy + 3, sz, tz)
    }

    drawPerson(c, st.gkX, g.gy + g.gh, kSize, st.gkCommitted ? st.gkDir : 0, st.gkJump, '#ffd24c', true)

    const wallCx = (ballStart(W).x + W / 2) / 2, wallHalf = W * 0.1, baseY = H * 0.56, n = 4, step = (wallHalf * 2) / n
    for (let i = 0; i < n; i++) {
      let x = wallCx - wallHalf + step * i + step / 2
      const jump = st.dodgeIdx === i ? 0 : st.wallJump / 26
      if (st.dodgeIdx === i) x += (i < 2 ? -1 : 1) * st.dodge * step // coward steps aside
      drawPerson(c, x, baseY, kSize * 0.92, 0, jump, '#3a6ad0', false)
    }

    // aim
    if (st.phase === 'aim') {
      const tx = g.gx + r.current.aimX * g.gw, ty = g.gy + r.current.aimY * g.gh
      c.strokeStyle = '#ff5c5c'; c.lineWidth = 2
      c.beginPath(); c.arc(tx, ty, 7, 0, Math.PI * 2); c.stroke()
      c.beginPath(); c.moveTo(tx - 10, ty); c.lineTo(tx + 10, ty); c.moveTo(tx, ty - 10); c.lineTo(tx, ty + 10); c.stroke()
      c.fillStyle = '#ffffff99'
      for (let i = 1; i <= 20; i++) { const b = ballPos(W, i / 20); c.beginPath(); c.arc(b.x, b.y, 1.4, 0, Math.PI * 2); c.fill() }
    }

    // ball trail
    for (let i = 0; i < st.trail.length; i++) {
      const tp = st.trail[i]; c.globalAlpha = (i / st.trail.length) * 0.4
      c.fillStyle = '#fff'; c.beginPath(); c.arc(tp.x, tp.y, tp.r * 0.7, 0, Math.PI * 2); c.fill()
    }
    c.globalAlpha = 1

    // ball
    let bp = st.phase === 'fly' ? ballPos(W, Math.min(1, st.t)) : { x: ballStart(W).x, y: ballStart(W).y, scale: 1 }
    if (st.phase === 'done' && st.rebound) bp = { x: ballStart(W).x, y: ballStart(W).y, scale: 0.5 } // ball gone after post
    const rad = 13 * (st.phase === 'fly' ? bp.scale : (st.ballInNet > 0 ? 0.4 : 1))
    const groundY = H - 6, shScale = 0.4 + 0.6 * (st.phase === 'fly' ? bp.scale : 1)
    if (st.phase !== 'done' || !st.ballInNet) { c.fillStyle = 'rgba(0,0,0,0.35)'; c.beginPath(); c.ellipse(bp.x, groundY, rad * 1.1 * shScale, rad * 0.4 * shScale, 0, 0, Math.PI * 2); c.fill() }
    if (st.phase === 'fly' || st.ballInNet > 0 || st.phase === 'aim') drawBall(c, bp.x, bp.y, rad, st.ballPhase)

    // rain
    if (st.weather === 'rain') {
      c.strokeStyle = 'rgba(150,180,220,0.4)'; c.lineWidth = 1
      for (const rp of st.rain) { c.beginPath(); c.moveTo(rp.x, rp.y); c.lineTo(rp.x - st.wind * 30, rp.y + 8); c.stroke() }
    }

    // scoreboard
    c.fillStyle = '#000a'; c.fillRect(W / 2 - 46, 4, 92, 16)
    c.fillStyle = '#ffd24c'; c.font = '11px monospace'; c.textAlign = 'center'
    c.fillText(`${st.scored} / ${SERIES}   попытка ${Math.min(st.attempt, SERIES)}`, W / 2, 16)
    c.textAlign = 'left'

    if (st.phase === 'series') {
      c.fillStyle = '#000c'; c.fillRect(0, 0, W, H)
      c.fillStyle = '#fff'; c.font = 'bold 22px monospace'; c.textAlign = 'center'
      c.fillText(`Серия: ${st.scored} / ${SERIES}`, W / 2, H / 2 - 8)
      c.fillStyle = '#ffd24c'; c.font = '13px monospace'
      c.fillText(st.scored === SERIES ? 'идеально! 🏆' : st.scored >= 3 ? 'хорошо!' : 'ещё разок', W / 2, H / 2 + 16)
      c.fillStyle = '#888'; c.font = '11px monospace'; c.fillText('пробел — новая серия', W / 2, H / 2 + 38)
      c.textAlign = 'left'
    }
  }

  useEffect(() => {
    const norm = (k: string) => (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'a', 'A', 'd', 'D', 'ф', 'Ф', 'в', 'В'].includes(e.key)) return
      e.preventDefault()
      const st = s.current
      if (st.phase === 'done' || st.phase === 'series') { if (e.key === ' ') advance(); return }
      if (st.phase !== 'aim') return
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      st.keys[nk] = true
      if (e.key === ' ' && !st.charging) { st.charging = true; setCharging(true) }
    }
    const up = (e: KeyboardEvent) => {
      const st = s.current
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      st.keys[nk] = false
      if (e.key === ' ' && st.charging && st.phase === 'aim') kick()
    }
    window.addEventListener('keydown', down); window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span className={charging ? 'text-[#5cc8ff]' : ''}>СИЛА {Math.round(power)}</span>
        <span className={spin !== 0 ? 'text-[#ff9f5c]' : ''}>КРУЧ {spin > 0 ? '↻' : spin < 0 ? '↺' : ''}{Math.abs(spin)}</span>
        <span className="text-[#5cc8ff]">ветер {wind > 0.01 ? `→${Math.round(Math.abs(wind) * 60)}` : wind < -0.01 ? `←${Math.round(Math.abs(wind) * 60)}` : '0'}</span>
        <span>{weather === 'rain' ? '🌧' : '🌙'}</span>
        <span className="flex-1 text-right">{msg || (phase === 'fly' ? '…' : 'целься и бей')}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ↑ ↓ точка · A/D кручёный · пробел — сила/удар</span>
        <span>серия {scored}/{attempt > SERIES ? SERIES : attempt - 1} · стрик {streak} · рекорд {stats.best}</span>
      </div>
    </div>
  )
}

function drawBall(c: CanvasRenderingContext2D, x: number, y: number, rad: number, phase: number) {
  if (rad < 0.5) return
  c.save(); c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.clip()
  c.fillStyle = '#fff'; c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.fill()
  c.fillStyle = '#161616'
  for (const sp of SPOTS_TEX) {
    const a = sp.lon + phase, ca = Math.cos(a)
    if (ca <= 0.04) continue
    const sx = x + Math.sin(a) * Math.cos(sp.lat) * rad, sy = y + Math.sin(sp.lat) * rad
    const pr = rad * 0.2 * ca * Math.max(0.3, Math.cos(sp.lat))
    c.beginPath(); c.ellipse(sx, sy, pr, pr * 0.92, 0, 0, Math.PI * 2); c.fill()
  }
  c.restore()
  c.strokeStyle = '#000'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.stroke()
  c.fillStyle = 'rgba(255,255,255,0.45)'; c.beginPath(); c.arc(x - rad * 0.34, y - rad * 0.34, rad * 0.18, 0, Math.PI * 2); c.fill()
}

function drawPerson(c: CanvasRenderingContext2D, x: number, groundY: number, size: number, dive: number, jump: number, color: string, keeper: boolean) {
  const u = size / 40
  c.save(); c.translate(x, groundY); c.rotate(dive * jump * 0.5)
  const up = jump * 14 * u
  c.strokeStyle = color; c.lineWidth = 3 * u; c.lineCap = 'round'
  c.beginPath(); c.moveTo(0, -up); c.lineTo(-5 * u, -up + 16 * u); c.moveTo(0, -up); c.lineTo(5 * u, -up + 16 * u); c.stroke()
  c.beginPath(); c.moveTo(0, -up - 18 * u); c.lineTo(0, -up); c.stroke()
  const ay = -up - 13 * u
  if (keeper) {
    c.beginPath(); c.moveTo(0, ay); c.lineTo(dive * 15 * u, ay - 11 * u - jump * 9 * u); c.moveTo(0, ay); c.lineTo(-dive * 9 * u, ay - 6 * u); c.stroke()
    c.fillStyle = color; c.beginPath(); c.arc(dive * 15 * u, ay - 11 * u - jump * 9 * u, 3.5 * u, 0, Math.PI * 2); c.fill()
  } else {
    c.beginPath(); c.moveTo(-7 * u, ay); c.lineTo(-7 * u, ay - (6 + jump * 10) * u); c.moveTo(7 * u, ay); c.lineTo(7 * u, ay - (6 + jump * 10) * u); c.stroke()
  }
  c.fillStyle = '#ffe39a'; c.beginPath(); c.arc(0, -up - 24 * u, 5 * u, 0, Math.PI * 2); c.fill()
  c.restore()
}
