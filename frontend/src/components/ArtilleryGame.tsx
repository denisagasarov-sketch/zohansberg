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
const sndFire = () => { tone(180, 0.12, 'square', 0.14); tone(360, 0.1, 'square', 0.1, 0.04) }
const sndBoom = () => { tone(140, 0.4, 'sawtooth', 0.22); tone(70, 0.45, 'square', 0.16, 0.02) }
const sndWin = () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.14, 'square', 0.15, i * 0.1))
const sndLose = () => [392, 330, 262, 196].forEach((f, i) => tone(f, 0.18, 'square', 0.15, i * 0.12))
const sndMove = () => tone(120, 0.03, 'square', 0.05)

// ── stats ──
interface Stats { wins: number; losses: number; shots: number; hits: number }
const STAT_KEY = 'artillery_stats'
function loadStats(): Stats {
  try { return { wins: 0, losses: 0, shots: 0, hits: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { wins: 0, losses: 0, shots: 0, hits: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

// ── game constants ──
const H = 340
const GRAV = 0.16
const MAXHP = 100
const DMG_R = 46
const MAX_DMG = 46
const MOVE_SPEED = 2.2
const TURN_MS = 5000
const CHARGE_PER_S = 70

interface Shell { x: number; y: number; vx: number; vy: number }

export default function ArtilleryGame() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [angle, setAngle] = useState(50)
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [hpP, setHpP] = useState(MAXHP)
  const [hpC, setHpC] = useState(MAXHP)
  const [turn, setTurn] = useState<'you' | 'cpu'>('you')
  const [remaining, setRemaining] = useState(TURN_MS)
  const [msg, setMsg] = useState('')
  const [round, setRound] = useState(0)
  const [stats, setStats] = useState<Stats>(loadStats)

  const s = useRef({
    W: 600, terrain: [] as number[],
    px: 60, py: 0, ax: 540, ay: 0,
    shell: null as Shell | null,
    shooter: 'you' as 'you' | 'cpu',
    over: false,
    charging: false, chargeStart: 0,
    angle: 50, power: 0,
    hpP: MAXHP, hpC: MAXHP,
    turnEnd: 0,
    cpuErr: null as number | null,
    keys: {} as Record<string, boolean>,
  })
  const angleRef = useRef(angle); angleRef.current = angle
  const turnRef = useRef(turn); turnRef.current = turn

  // ── setup terrain + main loop ──
  useEffect(() => {
    const canvas = canvasRef.current!, c = canvas.getContext('2d')!
    const W = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr
    c.setTransform(dpr, 0, 0, dpr, 0, 0)
    const st = s.current
    st.W = W

    const t: number[] = []
    const base = H * 0.6, ph = Math.random() * 6
    for (let x = 0; x < W; x++) {
      t.push(base + Math.sin(x * 0.009 + ph) * 40 + Math.sin(x * 0.035 + ph * 2) * 16 + Math.sin(x * 0.08) * 6)
    }
    st.terrain = t
    st.px = 60; st.ax = W - 60
    st.py = t[st.px]; st.ay = t[st.ax]
    st.shell = null; st.over = false; st.shooter = 'you'; st.cpuErr = null
    st.hpP = MAXHP; st.hpC = MAXHP; st.charging = false; st.power = 0; st.angle = 50
    st.turnEnd = Date.now() + TURN_MS
    setHpP(MAXHP); setHpC(MAXHP); setAngle(50); setPower(0); setTurn('you'); setMsg(''); setRemaining(TURN_MS)

    let raf = 0
    const loop = () => { update(); render(c); raf = requestAnimationFrame(loop) }
    loop()
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round])

  const passTurn = (to: 'you' | 'cpu') => {
    const st = s.current
    st.shooter = to; setTurn(to)
    st.turnEnd = Date.now() + TURN_MS; setRemaining(TURN_MS)
    if (to === 'cpu') setTimeout(cpuTurn, 600)
  }

  const explode = (bx: number, by: number) => {
    const st = s.current
    sndBoom()
    crater(st.terrain, bx, 22, st.W)
    st.py = st.terrain[Math.round(st.px)]; st.ay = st.terrain[Math.round(st.ax)]
    const hit = (tx: number, ty: number) => {
      const d = Math.hypot(bx - tx, by - ty)
      return d < DMG_R ? Math.round((1 - d / DMG_R) * MAX_DMG) : 0
    }
    const dp = hit(st.px, st.py - 8), dc = hit(st.ax, st.ay - 8)
    if (st.shooter === 'you' && dc > 0) bumpStat('hits')
    st.hpP = Math.max(0, st.hpP - dp); st.hpC = Math.max(0, st.hpC - dc)
    setHpP(st.hpP); setHpC(st.hpC)
    if (st.hpP <= 0 || st.hpC <= 0) {
      st.over = true
      if (st.hpC <= 0 && st.hpP > 0) { setMsg('🏆 ПОБЕДА'); sndWin(); bumpStat('wins') }
      else if (st.hpP <= 0 && st.hpC > 0) { setMsg('💥 ПОРАЖЕНИЕ'); sndLose(); bumpStat('losses') }
      else { setMsg('💥 НИЧЬЯ'); sndLose() }
    }
  }

  const update = () => {
    const st = s.current
    if (st.over) return

    if (st.shooter === 'you' && !st.shell) {
      if (st.keys['ArrowLeft']) { st.px = Math.max(20, st.px - MOVE_SPEED); st.py = st.terrain[Math.round(st.px)]; if (Math.random() < 0.3) sndMove() }
      if (st.keys['ArrowRight']) { st.px = Math.min(st.W * 0.5, st.px + MOVE_SPEED); st.py = st.terrain[Math.round(st.px)]; if (Math.random() < 0.3) sndMove() }
      if (st.charging) {
        const p = Math.min(100, (Date.now() - st.chargeStart) / 1000 * CHARGE_PER_S)
        st.power = p; setPower(Math.round(p))
      }
      const rem = st.turnEnd - Date.now()
      setRemaining(Math.max(0, rem))
      if (rem <= 0) { st.power = 0; setPower(0); st.charging = false; setCharging(false); passTurn('cpu') }
    }

    const sh = st.shell
    if (sh) {
      sh.x += sh.vx; sh.y += sh.vy; sh.vy += GRAV
      const ix = Math.round(sh.x)
      const ground = ix >= 0 && ix < st.W && sh.y >= st.terrain[ix]
      const off = sh.x < -30 || sh.x > st.W + 30 || sh.y > H + 60
      const tx = st.shooter === 'you' ? st.ax : st.px
      const ty = st.shooter === 'you' ? st.ay : st.py
      const direct = Math.hypot(sh.x - tx, sh.y - (ty - 8)) < 10
      if (direct || ground) {
        explode(sh.x, ground ? st.terrain[ix] : sh.y)
        if (st.shooter === 'cpu') st.cpuErr = sh.x - st.px
        st.shell = null
        if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you')
      } else if (off) {
        st.shell = null
        if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you')
      }
    }
  }

  const render = (c: CanvasRenderingContext2D) => {
    const st = s.current, W = st.W, t = st.terrain
    c.fillStyle = '#000'; c.fillRect(0, 0, W, H)
    c.fillStyle = '#fff'; c.beginPath(); c.moveTo(0, H)
    for (let x = 0; x < W; x++) c.lineTo(x, t[x])
    c.lineTo(W, H); c.closePath(); c.fill()

    if (st.shooter === 'you' && !st.shell && !st.over) {
      const v = (st.power || 1) * 0.2, a = (st.angle * Math.PI) / 180
      let x = st.px + 16, y = st.py - 12, vx = Math.cos(a) * v, vy = -Math.sin(a) * v
      c.fillStyle = '#000'
      for (let i = 0; i < 140; i++) {
        x += vx; y += vy; vy += GRAV
        if (i % 5 === 0) { c.beginPath(); c.arc(x, y, 1.5, 0, Math.PI * 2); c.fill() }
        if (x < 0 || x > W || y > t[Math.max(0, Math.min(W - 1, Math.round(x)))]) break
      }
    }

    drawTank(c, st.px, st.py, st.angle, 1, st.hpP)
    drawTank(c, st.ax, st.ay, 45, -1, st.hpC)

    if (st.shell) {
      c.fillStyle = '#000'; c.beginPath(); c.arc(st.shell.x, st.shell.y, 3.5, 0, Math.PI * 2); c.fill()
      c.strokeStyle = '#fff'; c.lineWidth = 1; c.stroke()
    }
  }

  const fire = () => {
    const st = s.current
    if (st.shell || st.over || st.shooter !== 'you') return
    launch('you', st.angle, Math.max(8, st.power))
    st.charging = false; setCharging(false)
    bumpStat('shots')
  }

  const launch = (who: 'you' | 'cpu', ang: number, pow: number) => {
    const st = s.current
    const v = pow * 0.2, a = (ang * Math.PI) / 180, dir = who === 'you' ? 1 : -1
    const gx = who === 'you' ? st.px : st.ax
    const gy = who === 'you' ? st.py : st.ay
    st.shell = { x: gx + dir * 16, y: gy - 12, vx: Math.cos(a) * v * dir, vy: -Math.sin(a) * v }
    sndFire()
  }

  const cpuTurn = () => {
    const st = s.current
    if (st.over) return
    const dist = Math.abs(st.ax - st.px)
    const ang = 45 + (Math.random() * 12 - 6)
    let pow = Math.min(100, Math.sqrt(dist * GRAV / Math.sin(2 * ang * Math.PI / 180)) / 0.2)
    if (st.cpuErr != null) pow -= st.cpuErr * 0.22
    else pow += (Math.random() - 0.5) * 8
    pow = Math.max(20, Math.min(100, pow + (Math.random() - 0.5) * 6))
    launch('cpu', ang, pow)
  }

  const bumpStat = (k: keyof Stats) => {
    setStats(prev => { const n = { ...prev, [k]: prev[k] + 1 }; saveStats(n); return n })
  }

  // ── keyboard ──
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) return
      e.preventDefault()
      const st = s.current
      if (st.over) { if (e.key === ' ') setRound(r => r + 1); return }
      if (turnRef.current !== 'you' || st.shell) return
      st.keys[e.key] = true
      if (e.key === 'ArrowUp') { st.angle = Math.min(89, st.angle + 2); setAngle(st.angle) }
      else if (e.key === 'ArrowDown') { st.angle = Math.max(1, st.angle - 2); setAngle(st.angle) }
      else if (e.key === ' ' && !st.charging) { st.charging = true; setCharging(true); st.chargeStart = Date.now() }
    }
    const up = (e: KeyboardEvent) => {
      const st = s.current
      st.keys[e.key] = false
      if (e.key === ' ' && st.charging && turnRef.current === 'you' && !st.over) fire()
    }
    window.addEventListener('keydown', down)
    window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const total = stats.wins + stats.losses
  const acc = stats.shots ? Math.round((stats.hits / stats.shots) * 100) : 0

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span>УГОЛ {angle}°</span>
        <span className={charging ? 'text-[#5060a0]' : ''}>СИЛА {Math.round(power)}</span>
        <span>HP {hpP}</span>
        <span className="text-[#666]">ИИ {hpC}</span>
        <span className="flex-1 text-right">
          {msg ? msg : turn === 'you' ? `твой ход · ${(remaining / 1000).toFixed(1)}с` : 'ход ИИ…'}
        </span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ходьба · ↑ ↓ угол · пробел (держать) — сила/огонь{msg ? ' · пробел — заново' : ''}</span>
        <span>W {stats.wins} · L {stats.losses}{total ? ` · точность ${acc}%` : ''}</span>
      </div>
    </div>
  )
}

function drawTank(c: CanvasRenderingContext2D, x: number, y: number, ang: number, dir: number, hp: number) {
  c.fillStyle = '#000'
  c.beginPath(); c.arc(x, y - 5, 8, Math.PI, 0); c.fill()
  c.fillRect(x - 8, y - 5, 16, 5)
  c.strokeStyle = '#000'; c.lineWidth = 3
  const a = (ang * Math.PI) / 180
  c.beginPath(); c.moveTo(x, y - 8); c.lineTo(x + Math.cos(a) * 16 * dir, y - 8 - Math.sin(a) * 16); c.stroke()
  c.strokeStyle = '#fff'; c.lineWidth = 1
  c.beginPath(); c.arc(x, y - 5, 8, Math.PI, 0); c.stroke(); c.strokeRect(x - 8, y - 5, 16, 5)
  const bw = 22
  c.fillStyle = '#000'; c.fillRect(x - bw / 2 - 1, y - 26, bw + 2, 5)
  c.fillStyle = '#fff'; c.fillRect(x - bw / 2, y - 25, bw * (hp / 100), 3)
}

function crater(terrain: number[], cx: number, r: number, W: number) {
  for (let x = Math.max(0, Math.floor(cx - r)); x < Math.min(W, cx + r); x++) {
    const dy = Math.sqrt(Math.max(0, r * r - (x - cx) ** 2))
    terrain[x] = Math.min(H - 2, terrain[x] + dy * 0.6)
  }
}
