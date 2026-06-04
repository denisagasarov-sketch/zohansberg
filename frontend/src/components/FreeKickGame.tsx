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

interface Spot { bx: number; by: number; label: string }

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
    ballRot: 0, rotSpeed: 0,
    gkX: 0, gkDir: 0, gkCommitted: false, gkJump: 0,
    wallJump: 0,
    keys: {} as Record<string, boolean>,
  })
  const r = useRef({ aimX, aimY, spin, power, phase })
  r.current = { aimX, aimY, spin, power, phase }

  const bump = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

  const geo = (W: number) => {
    const gw = W * 0.46, gh = H * 0.3
    const gx = (W - gw) / 2, gy = H * 0.1
    return { gw, gh, gx, gy, postR: 4 }
  }

  const newSpot = (): Spot => {
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

  const ballStart = (W: number) => {
    const sp = s.current.spot
    return { x: sp.bx * W, y: sp.by * H }
  }

  // ball screen position for progress p
  const ballPos = (W: number, p: number) => {
    const g = geo(W)
    const start = ballStart(W)
    const tx = g.gx + r.current.aimX * g.gw
    const ty = g.gy + r.current.aimY * g.gh
    const ease = 1 - (1 - p) * (1 - p)
    const baseX = start.x + (tx - start.x) * p
    const curve = (r.current.spin / 100) * (W * 0.26) * Math.sin(Math.PI * p)
    const x = baseX + curve
    const sag = (1 - r.current.power / 100) * 150 * (p * p)   // weak shots drop short
    const lift = (r.current.power / 100) * 18 * Math.sin(Math.PI * p) // slight arc
    const y = start.y + (ty - start.y) * ease + sag - lift
    const scale = 1 - 0.6 * p
    return { x, y, scale, tx, ty }
  }

  const update = (dt: number) => {
    const st = s.current, W = st.W
    st.ballRot += (st.phase === 'fly' ? st.rotSpeed : 0.0006) * dt

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

      // wall jumps up early, then comes down
      st.wallJump = p < 0.6 ? Math.sin((p / 0.6) * Math.PI) * 26 : 0

      // keeper reads ball direction around p=0.4 and commits to a dive
      if (!st.gkCommitted && p >= 0.4) {
        const b = ballPos(W, 0.45)
        st.gkDir = Math.sign(b.x - W / 2) || (Math.random() < 0.5 ? -1 : 1)
        st.gkCommitted = true
      }
      if (st.gkCommitted) {
        const reach = g.gw * 0.4
        const targetX = W / 2 + st.gkDir * reach
        st.gkX += (targetX - st.gkX) * Math.min(1, dt / 120)
        st.gkJump = Math.min(1, st.gkJump + dt / 350)
      }

      // wall block (over-the-wall miss if too low through the wall zone)
      if (p >= 0.46 && p <= 0.58) {
        const b = ballPos(W, p)
        const wallCx = (ballStart(W).x + W / 2) / 2
        const wallHalf = W * 0.1
        const wallTopY = H * 0.56 - st.wallJump
        if (Math.abs(b.x - wallCx) < wallHalf && b.y > wallTopY) { finish('СТЕНКА', false); return }
      }

      if (p >= 1) {
        const b = ballPos(W, 1)
        // posts
        const nearLeft = Math.abs(b.x - g.gx) < 6, nearRight = Math.abs(b.x - (g.gx + g.gw)) < 6
        const atBarY = b.y > g.gy - 6 && b.y < g.gy + g.gh
        const inGoal = b.x > g.gx + 4 && b.x < g.gx + g.gw - 4 && b.y > g.gy + 4 && b.y < g.gy + g.gh
        const gkHandsX = st.gkX
        const gkHandsY = g.gy + g.gh - 18 - st.gkJump * 22
        const caught = Math.hypot(b.x - gkHandsX, b.y - gkHandsY) < W * 0.06
        if ((nearLeft || nearRight) && atBarY) { finish('ШТАНГА', false); sndPost() }
        else if (!inGoal) finish('МИМО', false)
        else if (caught) finish('СЕЙВ', false)
        else finish('⚽ ГОЛ!', true)
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
    st.rotSpeed = 0.004 + Math.abs(st.spin) / 100 * 0.02
    if (st.spin < 0) st.rotSpeed = -st.rotSpeed
    sndKick(); bump('shots')
  }

  const reset = () => {
    const st = s.current
    st.phase = 'aim'; setPhase('aim'); setMsg('')
    st.power = 0; setPower(0); st.charging = false; setCharging(false)
    st.t = 0; st.gkX = st.W / 2; st.gkJump = 0; st.wallJump = 0
    st.spot = newSpot()
    setAimX(0.5); st.aimX = 0.5; setAimY(0.4); st.aimY = 0.4
  }

  const render = (c: CanvasRenderingContext2D, W: number) => {
    const st = s.current, g = geo(W)
    // sky + pitch
    c.fillStyle = '#0d1a10'; c.fillRect(0, 0, W, H)
    c.fillStyle = '#16361f'; c.fillRect(0, g.gy + g.gh * 0.45, W, H)
    c.fillStyle = '#1a3d24'
    const py0 = g.gy + g.gh * 0.45
    for (let i = 0; i < 6; i++) { const y = py0 + i * (H - py0) / 6; if (i % 2 === 0) c.fillRect(0, y, W, (H - py0) / 6) }

    // goal: net, posts, bar
    c.strokeStyle = '#ffffff22'; c.lineWidth = 1
    for (let i = 1; i < 9; i++) { const x = g.gx + (g.gw / 9) * i; c.beginPath(); c.moveTo(x, g.gy); c.lineTo(x, g.gy + g.gh); c.stroke() }
    for (let i = 1; i < 5; i++) { const y = g.gy + (g.gh / 5) * i; c.beginPath(); c.moveTo(g.gx, y); c.lineTo(g.gx + g.gw, y); c.stroke() }
    c.strokeStyle = '#fff'; c.lineWidth = 5; c.lineCap = 'round'
    c.beginPath(); c.moveTo(g.gx, g.gy + g.gh); c.lineTo(g.gx, g.gy); c.lineTo(g.gx + g.gw, g.gy); c.lineTo(g.gx + g.gw, g.gy + g.gh); c.stroke()

    // keeper (little man)
    drawKeeper(c, st.gkX, g.gy + g.gh, st.gkCommitted ? st.gkDir : 0, st.gkJump)

    // wall (jumping players)
    const wallCx = (ballStart(W).x + W / 2) / 2, wallHalf = W * 0.1, baseY = H * 0.56
    const n = 4, step = (wallHalf * 2) / n
    for (let i = 0; i < n; i++) {
      const x = wallCx - wallHalf + step * i + step / 2
      drawWallMan(c, x, baseY - st.wallJump, step * 0.7)
    }

    // aim marker + predicted curve
    if (st.phase === 'aim') {
      const tx = g.gx + r.current.aimX * g.gw, ty = g.gy + r.current.aimY * g.gh
      c.strokeStyle = '#ff5c5c'; c.lineWidth = 2
      c.beginPath(); c.arc(tx, ty, 7, 0, Math.PI * 2); c.stroke()
      c.beginPath(); c.moveTo(tx - 10, ty); c.lineTo(tx + 10, ty); c.moveTo(tx, ty - 10); c.lineTo(tx, ty + 10); c.stroke()
      c.fillStyle = '#ffffff99'
      for (let i = 1; i <= 20; i++) { const b = ballPos(W, i / 20); c.beginPath(); c.arc(b.x, b.y, 1.4, 0, Math.PI * 2); c.fill() }
    }

    // ball
    const bp = st.phase === 'fly' ? ballPos(W, Math.min(1, st.t)) : { x: ballStart(W).x, y: ballStart(W).y, scale: 1 }
    drawBall(c, bp.x, bp.y, 13 * bp.scale, st.ballRot)
  }

  // keyboard (RU/EN aware for A/D)
  useEffect(() => {
    const norm = (k: string) => (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const allowed = ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'a', 'A', 'd', 'D', 'ф', 'Ф', 'в', 'В']
      if (!allowed.includes(e.key)) return
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
function drawBall(c: CanvasRenderingContext2D, x: number, y: number, rad: number, rot: number) {
  c.save(); c.translate(x, y); c.rotate(rot)
  c.fillStyle = '#fff'; c.beginPath(); c.arc(0, 0, rad, 0, Math.PI * 2); c.fill()
  // center pentagon + ring of pentagons = classic football look
  c.fillStyle = '#161616'
  pentagon(c, 0, 0, rad * 0.36)
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2 - Math.PI / 2
    pentagon(c, Math.cos(a) * rad * 0.66, Math.sin(a) * rad * 0.66, rad * 0.2, a)
  }
  c.restore()
  c.strokeStyle = '#000'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, rad, 0, Math.PI * 2); c.stroke()
  // shine
  c.fillStyle = 'rgba(255,255,255,0.5)'; c.beginPath(); c.arc(x - rad * 0.32, y - rad * 0.32, rad * 0.18, 0, Math.PI * 2); c.fill()
}
function pentagon(c: CanvasRenderingContext2D, cx: number, cy: number, r: number, rot = 0) {
  c.beginPath()
  for (let i = 0; i < 5; i++) {
    const a = rot + (i / 5) * Math.PI * 2 - Math.PI / 2
    const px = cx + Math.cos(a) * r, py = cy + Math.sin(a) * r
    if (i === 0) c.moveTo(px, py); else c.lineTo(px, py)
  }
  c.closePath(); c.fill()
}
function drawKeeper(c: CanvasRenderingContext2D, x: number, groundY: number, dive: number, jump: number) {
  // dive: -1 left, 0 still, 1 right ; jump 0..1 raises & tilts
  c.save()
  c.translate(x, groundY)
  const tilt = dive * jump * 0.5
  c.rotate(tilt)
  const up = jump * 14
  c.strokeStyle = '#ffd24c'; c.fillStyle = '#ffd24c'; c.lineWidth = 3; c.lineCap = 'round'
  // legs
  c.beginPath(); c.moveTo(0, -up); c.lineTo(-5, -up + 14); c.moveTo(0, -up); c.lineTo(5, -up + 14); c.stroke()
  // body
  c.beginPath(); c.moveTo(0, -up - 16); c.lineTo(0, -up); c.stroke()
  // arms reaching toward dive direction (up when jumping)
  const ay = -up - 12
  c.beginPath(); c.moveTo(0, ay)
  c.lineTo(dive * 14, ay - 10 - jump * 8)
  c.moveTo(0, ay); c.lineTo(-dive * 8, ay - 6); c.stroke()
  // gloves
  c.beginPath(); c.arc(dive * 14, ay - 10 - jump * 8, 3.5, 0, Math.PI * 2); c.fill()
  // head
  c.fillStyle = '#ffe39a'; c.beginPath(); c.arc(0, -up - 22, 5, 0, Math.PI * 2); c.fill()
  c.restore()
}
function drawWallMan(c: CanvasRenderingContext2D, x: number, feetY: number, w: number) {
  c.fillStyle = '#3a6ad0'
  c.fillRect(x - w * 0.28, feetY - 24, w * 0.56, 24)
  c.fillStyle = '#ffe39a'; c.beginPath(); c.arc(x, feetY - 29, 5, 0, Math.PI * 2); c.fill()
  // arms crossed (protect)
  c.strokeStyle = '#3a6ad0'; c.lineWidth = 3
  c.beginPath(); c.moveTo(x - w * 0.28, feetY - 18); c.lineTo(x + w * 0.28, feetY - 14); c.stroke()
}
