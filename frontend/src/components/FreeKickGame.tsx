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
const sndPost = () => { tone(900, 0.05, 'square', 0.18); tone(600, 0.12, 'square', 0.12, 0.05) }

interface Stats { goals: number; shots: number }
const STAT_KEY = 'freekick_stats'
function loadStats(): Stats {
  try { return { goals: 0, shots: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { goals: 0, shots: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

const H = 340
const FLIGHT_MS = 1600
const CHARGE_PER_S = 75
type Phase = 'aim' | 'fly' | 'done'

// ball texture spots (longitude, latitude) on the sphere
const SPOTS = (() => {
  const arr: { lon: number; lat: number }[] = [{ lon: 0, lat: 0 }]
  for (let i = 0; i < 5; i++) arr.push({ lon: (i / 5) * Math.PI * 2, lat: -0.7 })
  for (let i = 0; i < 5; i++) arr.push({ lon: (i / 5) * Math.PI * 2 + 0.6, lat: 0.7 })
  return arr
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

  const s = useRef({
    W: 600, phase: 'aim' as Phase,
    aimX: 0.5, aimY: 0.4, spin: 0, power: 0,
    charging: false, t: 0,
    spot: { bx: 0.5, by: 0.92, label: '' } as { bx: number; by: number; label: string },
    ballPhase: 0, spinSpeed: 0,
    gkX: 0, gkDir: 0, gkCommitted: false, gkJump: 0,
    gkReact: 0.42, gkReach: 1, gkSmart: false, gkLag: 120, gkFumble: 1,
    wallJump: 0, netShake: 0,
    keys: {} as Record<string, boolean>,
  })
  const r = useRef({ aimX, aimY, spin, power, phase })
  r.current = { aimX, aimY, spin, power, phase }

  const bump = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

  const geo = (W: number) => {
    const gw = W * 0.46, gh = H * 0.3
    return { gw, gh, gx: (W - gw) / 2, gy: H * 0.1 }
  }

  const newSpot = () => {
    const opts = [
      { bx: 0.5, by: 0.94, label: 'по центру' },
      { bx: 0.28, by: 0.9, label: 'слева' },
      { bx: 0.72, by: 0.9, label: 'справа' },
      { bx: 0.4, by: 0.86, label: 'полукруг' },
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
    s.current.W = W
    s.current.spot = newSpot()
    s.current.gkX = W / 2

    let raf = 0, last = performance.now()
    const loop = (now: number) => {
      const dt = Math.min(40, now - last); last = now
      update(dt); render(c, W); raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const ballStart = (W: number) => ({ x: s.current.spot.bx * W, y: s.current.spot.by * H })

  const ballPos = (W: number, p: number) => {
    const g = geo(W), start = ballStart(W)
    const tx = g.gx + r.current.aimX * g.gw
    const ty = g.gy + r.current.aimY * g.gh
    const ease = 1 - (1 - p) * (1 - p)
    const baseX = start.x + (tx - start.x) * p
    const curve = (r.current.spin / 100) * (W * 0.26) * Math.sin(Math.PI * p)
    const x = baseX + curve
    const sag = (1 - r.current.power / 100) * 150 * (p * p)
    const lift = (r.current.power / 100) * 18 * Math.sin(Math.PI * p)
    const y = start.y + (ty - start.y) * ease + sag - lift
    return { x, y, scale: 1 - 0.6 * p, tx, ty }
  }

  const update = (dt: number) => {
    const st = s.current, W = st.W
    // horizontal spin of the ball texture
    const baseRoll = st.phase === 'fly' ? st.spinSpeed : 0.0009
    st.ballPhase += baseRoll * dt
    if (st.netShake > 0) st.netShake = Math.max(0, st.netShake - dt)

    if (st.phase === 'aim') {
      if (st.keys['ArrowLeft']) { st.aimX = Math.max(-0.05, st.aimX - dt / 1500); setAimX(st.aimX) }
      if (st.keys['ArrowRight']) { st.aimX = Math.min(1.05, st.aimX + dt / 1500); setAimX(st.aimX) }
      if (st.keys['ArrowUp']) { st.aimY = Math.max(-0.05, st.aimY - dt / 1500); setAimY(st.aimY) }
      if (st.keys['ArrowDown']) { st.aimY = Math.min(0.95, st.aimY + dt / 1500); setAimY(st.aimY) }
      if (st.keys['a']) { st.spin = Math.max(-100, st.spin - dt / 12); setSpin(Math.round(st.spin)) }
      if (st.keys['d']) { st.spin = Math.min(100, st.spin + dt / 12); setSpin(Math.round(st.spin)) }
      if (st.charging) { st.power = Math.min(100, st.power + dt / 1000 * CHARGE_PER_S); setPower(Math.round(st.power)) }
    } else if (st.phase === 'fly') {
      st.t += dt / FLIGHT_MS
      const p = Math.min(1, st.t)
      const g = geo(W)
      st.wallJump = p < 0.6 ? Math.sin((p / 0.6) * Math.PI) * 26 : 0

      // keeper commits at his (random) reaction time; smart keepers read the FINAL spot,
      // others read the mid-flight position (so a late curl fools them)
      if (!st.gkCommitted && p >= st.gkReact) {
        const readP = st.gkSmart ? 0.95 : 0.5
        const b = ballPos(W, readP)
        let dir = Math.sign(b.x - W / 2)
        if (Math.random() < 0.12) dir = -dir || 1 // occasional total misread
        if (dir === 0) dir = Math.random() < 0.5 ? -1 : 1
        st.gkDir = dir
        st.gkCommitted = true
      }
      if (st.gkCommitted) {
        const targetX = W / 2 + st.gkDir * g.gw * 0.4
        st.gkX += (targetX - st.gkX) * Math.min(1, dt / st.gkLag)
        st.gkJump = Math.min(1, st.gkJump + dt / 350)
      }

      if (p >= 0.46 && p <= 0.58) {
        const b = ballPos(W, p)
        const wallCx = (ballStart(W).x + W / 2) / 2, wallHalf = W * 0.1
        const wallTopY = H * 0.56 - st.wallJump
        if (Math.abs(b.x - wallCx) < wallHalf && b.y > wallTopY) { finish('СТЕНКА', false); return }
      }

      if (p >= 1) {
        const b = ballPos(W, 1)
        const nearPost = Math.abs(b.x - g.gx) < 6 || Math.abs(b.x - (g.gx + g.gw)) < 6
        const atBarY = b.y > g.gy - 6 && b.y < g.gy + g.gh
        const inGoal = b.x > g.gx + 4 && b.x < g.gx + g.gw - 4 && b.y > g.gy + 4 && b.y < g.gy + g.gh
        const gkHandsY = g.gy + g.gh - 18 - st.gkJump * 22
        const dist = Math.hypot(b.x - st.gkX, b.y - gkHandsY)
        const caught = dist < W * 0.06 * st.gkReach * st.gkFumble
        if (nearPost && atBarY) { finish('ШТАНГА', false); sndPost() }
        else if (!inGoal) finish('МИМО', false)
        else if (caught) finish('СЕЙВ', false)
        else { st.netShake = 600; finish('⚽ ГОЛ!', true) }
      }
    }
  }

  const finish = (m: string, goal: boolean) => {
    const st = s.current
    st.phase = 'done'; setPhase('done'); setMsg(m)
    if (goal) { sndGoal(); bump('goals') }
    else if (m === 'СЕЙВ') sndSave()
    else if (m !== 'ШТАНГА') sndMiss()
  }

  const kick = () => {
    const st = s.current
    if (st.phase !== 'aim' || st.power < 5) return
    st.charging = false; setCharging(false)
    st.t = 0; st.phase = 'fly'; setPhase('fly')
    st.gkCommitted = false; st.gkJump = 0; st.gkX = st.W / 2
    // randomised keeper so the same kick isn't always a goal
    st.gkReact = 0.34 + Math.random() * 0.26   // when he commits
    st.gkSmart = Math.random() < 0.35          // sometimes reads the real target
    st.gkReach = 0.85 + Math.random() * 0.45   // dive reach
    st.gkLag = 90 + Math.random() * 90         // dive speed
    st.gkFumble = Math.random() < 0.15 ? 0.4 : 1 // occasional fumble
    // horizontal spin speed of the ball
    st.spinSpeed = (st.spin >= 0 ? 1 : -1) * (0.004 + Math.abs(st.spin) / 100 * 0.03)
    sndKick(); bump('shots')
  }

  const reset = () => {
    const st = s.current
    st.phase = 'aim'; setPhase('aim'); setMsg('')
    st.power = 0; setPower(0); st.charging = false; setCharging(false)
    st.t = 0; st.gkX = st.W / 2; st.gkJump = 0; st.wallJump = 0; st.netShake = 0
    st.spot = newSpot()
    st.aimX = 0.5; setAimX(0.5); st.aimY = 0.4; setAimY(0.4)
  }

  const render = (c: CanvasRenderingContext2D, W: number) => {
    const st = s.current, g = geo(W)
    const kSize = g.gh * 0.62 // keeper proportional to goal height

    c.fillStyle = '#0d1a10'; c.fillRect(0, 0, W, H)
    c.fillStyle = '#16361f'; c.fillRect(0, g.gy + g.gh * 0.45, W, H)
    c.fillStyle = '#1a3d24'
    const py0 = g.gy + g.gh * 0.45
    for (let i = 0; i < 6; i++) { const y = py0 + i * (H - py0) / 6; if (i % 2 === 0) c.fillRect(0, y, W, (H - py0) / 6) }

    // net (wobbles on goal)
    const sh = st.netShake > 0 ? Math.sin(st.netShake / 30) * (st.netShake / 600) * 5 : 0
    c.strokeStyle = '#ffffff22'; c.lineWidth = 1
    for (let i = 1; i < 9; i++) { const x = g.gx + (g.gw / 9) * i + sh * Math.sin(i); c.beginPath(); c.moveTo(x, g.gy); c.lineTo(x, g.gy + g.gh); c.stroke() }
    for (let i = 1; i < 5; i++) { const y = g.gy + (g.gh / 5) * i; c.beginPath(); c.moveTo(g.gx, y); c.lineTo(g.gx + g.gw, y); c.stroke() }
    c.strokeStyle = '#fff'; c.lineWidth = 5; c.lineCap = 'round'
    c.beginPath(); c.moveTo(g.gx, g.gy + g.gh); c.lineTo(g.gx, g.gy); c.lineTo(g.gx + g.gw, g.gy); c.lineTo(g.gx + g.gw, g.gy + g.gh); c.stroke()

    drawPerson(c, st.gkX, g.gy + g.gh, kSize, st.gkCommitted ? st.gkDir : 0, st.gkJump, '#ffd24c', true)

    // wall — real little men, jumping
    const wallCx = (ballStart(W).x + W / 2) / 2, wallHalf = W * 0.1, baseY = H * 0.56
    const n = 4, step = (wallHalf * 2) / n
    for (let i = 0; i < n; i++) {
      const x = wallCx - wallHalf + step * i + step / 2
      drawPerson(c, x, baseY, kSize * 0.92, 0, st.wallJump / 26, '#3a6ad0', false)
    }

    if (st.phase === 'aim') {
      const tx = g.gx + r.current.aimX * g.gw, ty = g.gy + r.current.aimY * g.gh
      c.strokeStyle = '#ff5c5c'; c.lineWidth = 2
      c.beginPath(); c.arc(tx, ty, 7, 0, Math.PI * 2); c.stroke()
      c.beginPath(); c.moveTo(tx - 10, ty); c.lineTo(tx + 10, ty); c.moveTo(tx, ty - 10); c.lineTo(tx, ty + 10); c.stroke()
      c.fillStyle = '#ffffff99'
      for (let i = 1; i <= 20; i++) { const b = ballPos(W, i / 20); c.beginPath(); c.arc(b.x, b.y, 1.4, 0, Math.PI * 2); c.fill() }
    }

    const bp = st.phase === 'fly' ? ballPos(W, Math.min(1, st.t)) : { x: ballStart(W).x, y: ballStart(W).y, scale: 1 }
    const rad = 13 * bp.scale
    // shadow on the ground
    const groundY = H - 6
    const shScale = 0.4 + 0.6 * bp.scale
    c.fillStyle = 'rgba(0,0,0,0.35)'
    c.beginPath(); c.ellipse(bp.x, groundY, rad * 1.1 * shScale, rad * 0.4 * shScale, 0, 0, Math.PI * 2); c.fill()
    drawBall(c, bp.x, bp.y, rad, st.ballPhase)
  }

  useEffect(() => {
    const norm = (k: string) => (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'a', 'A', 'd', 'D', 'ф', 'Ф', 'в', 'В'].includes(e.key)) return
      e.preventDefault()
      const st = s.current
      if (st.phase === 'done') { if (e.key === ' ') reset(); return }
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

  const acc = stats.shots ? Math.round((stats.goals / stats.shots) * 100) : 0

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span className={charging ? 'text-[#5cc8ff]' : ''}>СИЛА {Math.round(power)}</span>
        <span className={spin !== 0 ? 'text-[#ff9f5c]' : ''}>КРУЧ {spin > 0 ? '↻' : spin < 0 ? '↺' : ''}{Math.abs(spin)}</span>
        <span className="text-[#666]">точка: {s.current.spot.label}</span>
        <span className="flex-1 text-right">{msg || (phase === 'fly' ? '…' : 'целься и бей')}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ↑ ↓ точка · A/D кручёный · пробел (держать) — сила/удар{msg ? ' · пробел — ещё' : ''}</span>
        <span>голы {stats.goals}/{stats.shots}{stats.shots ? ` · ${acc}%` : ''}</span>
      </div>
    </div>
  )
}

// ── drawing helpers ────────────────────────────────────────────────────────────

// Football with horizontal (around vertical axis) rotation — spots wrap left↔right
function drawBall(c: CanvasRenderingContext2D, x: number, y: number, rad: number, phase: number) {
  c.save()
  c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.clip()
  c.fillStyle = '#fff'; c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.fill()
  c.fillStyle = '#161616'
  for (const sp of SPOTS) {
    const a = sp.lon + phase
    const ca = Math.cos(a)
    if (ca <= 0.04) continue // back hemisphere hidden
    const sx = x + Math.sin(a) * Math.cos(sp.lat) * rad
    const sy = y + Math.sin(sp.lat) * rad
    const pr = rad * 0.2 * ca * Math.max(0.3, Math.cos(sp.lat))
    c.beginPath(); c.ellipse(sx, sy, pr, pr * 0.92, 0, 0, Math.PI * 2); c.fill()
  }
  c.restore()
  c.strokeStyle = '#000'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.stroke()
  c.fillStyle = 'rgba(255,255,255,0.45)'; c.beginPath(); c.arc(x - rad * 0.34, y - rad * 0.34, rad * 0.18, 0, Math.PI * 2); c.fill()
}

// A little stick-figure player. dive: -1..1 lean, jump 0..1 raise.
function drawPerson(c: CanvasRenderingContext2D, x: number, groundY: number, size: number, dive: number, jump: number, color: string, keeper: boolean) {
  const u = size / 40 // unit scale relative to a 40px reference
  c.save()
  c.translate(x, groundY)
  c.rotate(dive * jump * 0.5)
  const up = jump * 14 * u
  c.strokeStyle = color; c.lineWidth = 3 * u; c.lineCap = 'round'
  // legs
  c.beginPath(); c.moveTo(0, -up); c.lineTo(-5 * u, -up + 16 * u); c.moveTo(0, -up); c.lineTo(5 * u, -up + 16 * u); c.stroke()
  // body
  c.beginPath(); c.moveTo(0, -up - 18 * u); c.lineTo(0, -up); c.stroke()
  // arms
  const ay = -up - 13 * u
  if (keeper) {
    c.beginPath(); c.moveTo(0, ay); c.lineTo(dive * 15 * u, ay - 11 * u - jump * 9 * u); c.moveTo(0, ay); c.lineTo(-dive * 9 * u, ay - 6 * u); c.stroke()
    c.fillStyle = color; c.beginPath(); c.arc(dive * 15 * u, ay - 11 * u - jump * 9 * u, 3.5 * u, 0, Math.PI * 2); c.fill()
  } else {
    // wall: arms up to protect, higher when jumping
    c.beginPath(); c.moveTo(-7 * u, ay); c.lineTo(-7 * u, ay - (6 + jump * 10) * u); c.moveTo(7 * u, ay); c.lineTo(7 * u, ay - (6 + jump * 10) * u); c.stroke()
  }
  // head
  c.fillStyle = '#ffe39a'; c.beginPath(); c.arc(0, -up - 24 * u, 5 * u, 0, Math.PI * 2); c.fill()
  c.restore()
}
