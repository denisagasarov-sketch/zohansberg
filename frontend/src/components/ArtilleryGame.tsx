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

interface Stats { wins: number; losses: number; shots: number; hits: number }
const STAT_KEY = 'artillery_stats'
function loadStats(): Stats {
  try { return { wins: 0, losses: 0, shots: 0, hits: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { wins: 0, losses: 0, shots: 0, hits: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

// weapons
type WKind = 'normal' | 'heavy' | 'cluster'
const WEAPONS: Record<WKind, { name: string; r: number; dmg: number; vmul: number; cluster?: boolean }> = {
  normal: { name: 'снаряд', r: 22, dmg: 46, vmul: 1 },
  heavy: { name: 'тяжёлый', r: 34, dmg: 72, vmul: 0.9 },
  cluster: { name: 'кластер', r: 16, dmg: 28, vmul: 1, cluster: true },
}
const WORDER: WKind[] = ['normal', 'heavy', 'cluster']

const H = 340
const GRAV = 0.16
const MAXHP = 100
const MOVE_SPEED = 2.2
const CHARGE_PER_S = 70

interface Shell { x: number; y: number; vx: number; vy: number; w: WKind }
interface Particle { x: number; y: number; vx: number; vy: number; life: number; max: number }

export default function ArtilleryGame() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [angle, setAngle] = useState(50)
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [hpP, setHpP] = useState(MAXHP)
  const [hpC, setHpC] = useState(MAXHP)
  const [turn, setTurn] = useState<'you' | 'cpu'>('you')
  const [msg, setMsg] = useState('')
  const [round, setRound] = useState(0)
  const [stats, setStats] = useState<Stats>(loadStats)
  const [weapon, setWeapon] = useState<WKind>('normal')
  const [wind, setWind] = useState(0)

  const s = useRef({
    W: 600, terrain: [] as number[],
    px: 60, py: 0, ax: 540, ay: 0,
    shell: null as Shell | null,
    shooter: 'you' as 'you' | 'cpu',
    over: false,
    charging: false, power: 0, angle: 50,
    hpP: MAXHP, hpC: MAXHP,
    cpuErr: null as number | null,
    cpuMoving: false, cpuMoveTarget: 0,
    weapon: 'normal' as WKind,
    wind: 0,
    parts: [] as Particle[], shake: 0,
    keys: {} as Record<string, boolean>,
  })
  const angleRef = useRef(angle); angleRef.current = angle
  const turnRef = useRef(turn); turnRef.current = turn

  const bumpStat = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

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
    for (let x = 0; x < W; x++) t.push(base + Math.sin(x * 0.009 + ph) * 40 + Math.sin(x * 0.035 + ph * 2) * 16 + Math.sin(x * 0.08) * 6)
    st.terrain = t
    st.px = 60; st.ax = W - 60; st.py = t[st.px]; st.ay = t[st.ax]
    st.shell = null; st.over = false; st.shooter = 'you'; st.cpuErr = null
    st.hpP = MAXHP; st.hpC = MAXHP; st.charging = false; st.power = 0; st.angle = 50
    st.parts = []; st.shake = 0; st.cpuMoving = false
    st.wind = (Math.random() - 0.5) * 0.1
    setHpP(MAXHP); setHpC(MAXHP); setAngle(50); setPower(0); setTurn('you'); setMsg('')
    setWind(st.wind)

    let raf = 0, last = performance.now()
    const loop = (now: number) => { const dt = Math.min(40, now - last); last = now; update(dt); render(c); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round])

  const passTurn = (to: 'you' | 'cpu') => {
    const st = s.current
    st.shooter = to; setTurn(to)
    if (to === 'you') { st.power = 0; setPower(0) }   // reset power each of your turns
    // shifting wind each turn
    st.wind += (Math.random() - 0.5) * 0.04; st.wind = Math.max(-0.12, Math.min(0.12, st.wind)); setWind(st.wind)
    if (to === 'cpu') setTimeout(cpuStart, 500)
  }

  const spawnBoom = (x: number, y: number, n: number) => {
    const st = s.current
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, sp = 1 + Math.random() * 3
      st.parts.push({ x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 1, life: 1, max: 1 })
    }
    st.shake = 12
  }

  const doDamage = (bx: number, by: number, w: WKind) => {
    const st = s.current, cfg = WEAPONS[w]
    crater(st.terrain, bx, cfg.r, st.W)
    st.py = st.terrain[Math.round(st.px)]; st.ay = st.terrain[Math.round(st.ax)]
    const hit = (tx: number, ty: number) => { const d = Math.hypot(bx - tx, by - ty); return d < cfg.r + 14 ? Math.round((1 - d / (cfg.r + 14)) * cfg.dmg) : 0 }
    const dp = hit(st.px, st.py - 8), dc = hit(st.ax, st.ay - 8)
    if (st.shooter === 'you' && dc > 0) bumpStat('hits')
    st.hpP = Math.max(0, st.hpP - dp); st.hpC = Math.max(0, st.hpC - dc)
    setHpP(st.hpP); setHpC(st.hpC)
  }

  const explode = (bx: number, by: number, w: WKind) => {
    sndBoom(); spawnBoom(bx, by, 18)
    doDamage(bx, by, w)
    if (WEAPONS[w].cluster) {
      // shrapnel craters around impact
      for (const off of [-26, 26]) { doDamage(bx + off, s.current.terrain[Math.max(0, Math.min(s.current.W - 1, Math.round(bx + off)))], w); spawnBoom(bx + off, by, 8) }
    }
    const st = s.current
    if (st.hpP <= 0 || st.hpC <= 0) {
      st.over = true
      if (st.hpC <= 0 && st.hpP > 0) { setMsg('🏆 ПОБЕДА'); sndWin(); bumpStat('wins') }
      else if (st.hpP <= 0 && st.hpC > 0) { setMsg('💥 ПОРАЖЕНИЕ'); sndLose(); bumpStat('losses') }
      else { setMsg('💥 НИЧЬЯ'); sndLose() }
    }
  }

  const update = (dt: number) => {
    const st = s.current
    // particles
    for (const p of st.parts) { p.x += p.vx; p.y += p.vy; p.vy += 0.15; p.life -= dt / 600 }
    st.parts = st.parts.filter(p => p.life > 0)
    if (st.shake > 0) st.shake = Math.max(0, st.shake - dt / 30)
    if (st.over) return

    if (st.shooter === 'you' && !st.shell) {
      if (st.keys['ArrowLeft']) { st.px = Math.max(20, st.px - MOVE_SPEED); st.py = st.terrain[Math.round(st.px)]; if (Math.random() < 0.3) sndMove() }
      if (st.keys['ArrowRight']) { st.px = Math.min(st.W * 0.5, st.px + MOVE_SPEED); st.py = st.terrain[Math.round(st.px)]; if (Math.random() < 0.3) sndMove() }
      if (st.charging) { st.power = Math.min(100, st.power + dt / 1000 * CHARGE_PER_S); setPower(Math.round(st.power)) }
    }

    // cpu walking to its chosen spot before firing
    if (st.cpuMoving) {
      const d = st.cpuMoveTarget - st.ax
      if (Math.abs(d) < MOVE_SPEED) { st.ax = st.cpuMoveTarget; st.cpuMoving = false; setTimeout(cpuShoot, 250) }
      else { st.ax += Math.sign(d) * MOVE_SPEED; st.ay = st.terrain[Math.round(st.ax)]; if (Math.random() < 0.3) sndMove() }
    }

    const sh = st.shell
    if (sh) {
      sh.vx += st.wind * dt / 16
      sh.x += sh.vx; sh.y += sh.vy; sh.vy += GRAV
      const ix = Math.round(sh.x)
      const ground = ix >= 0 && ix < st.W && sh.y >= st.terrain[ix]
      const off = sh.x < -30 || sh.x > st.W + 30 || sh.y > H + 60
      const tx = st.shooter === 'you' ? st.ax : st.px
      const ty = st.shooter === 'you' ? st.ay : st.py
      const direct = Math.hypot(sh.x - tx, sh.y - (ty - 8)) < 10
      if (direct || ground) {
        explode(sh.x, ground ? st.terrain[ix] : sh.y, sh.w)
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
    c.save()
    if (st.shake > 0) c.translate((Math.random() - 0.5) * st.shake, (Math.random() - 0.5) * st.shake)
    c.fillStyle = '#000'; c.fillRect(-20, -20, W + 40, H + 40)
    c.fillStyle = '#fff'; c.beginPath(); c.moveTo(0, H)
    for (let x = 0; x < W; x++) c.lineTo(x, t[x])
    c.lineTo(W, H); c.closePath(); c.fill()

    // yellow aiming trajectory (player turn) with wind
    if (st.shooter === 'you' && !st.shell && !st.over) {
      const v = (st.power || 1) * 0.2 * WEAPONS[st.weapon].vmul, a = (st.angle * Math.PI) / 180
      let x = st.px + 16, y = st.py - 12, vx = Math.cos(a) * v, vy = -Math.sin(a) * v
      c.fillStyle = '#ffd24c'
      for (let i = 0; i < 150; i++) {
        vx += st.wind / 16; x += vx; y += vy; vy += GRAV
        if (i % 5 === 0) { c.beginPath(); c.arc(x, y, 1.8, 0, Math.PI * 2); c.fill() }
        if (x < 0 || x > W || y > t[Math.max(0, Math.min(W - 1, Math.round(x)))]) break
      }
    }

    drawTank(c, st.px, st.py, st.angle, 1, st.hpP, '#000')
    drawTank(c, st.ax, st.ay, 45, -1, st.hpC, '#000')

    if (st.shell) {
      c.fillStyle = '#000'; c.beginPath(); c.arc(st.shell.x, st.shell.y, st.shell.w === 'heavy' ? 5 : 3.5, 0, Math.PI * 2); c.fill()
      c.strokeStyle = '#fff'; c.lineWidth = 1; c.stroke()
    }
    // particles
    for (const p of st.parts) { c.fillStyle = p.life > 0.5 ? '#000' : '#555'; const sz = 2 + p.life * 2; c.fillRect(p.x - sz / 2, p.y - sz / 2, sz, sz) }
    c.restore()
  }

  const fire = () => {
    const st = s.current
    if (st.shell || st.over || st.shooter !== 'you') return
    launch('you', st.angle, Math.max(8, st.power), st.weapon)
    st.charging = false; setCharging(false); bumpStat('shots')
  }

  const launch = (who: 'you' | 'cpu', ang: number, pow: number, w: WKind) => {
    const st = s.current
    const v = pow * 0.2 * WEAPONS[w].vmul, a = (ang * Math.PI) / 180, dir = who === 'you' ? 1 : -1
    const gx = who === 'you' ? st.px : st.ax, gy = who === 'you' ? st.py : st.ay
    st.shell = { x: gx + dir * 16, y: gy - 12, vx: Math.cos(a) * v * dir, vy: -Math.sin(a) * v, w }
    sndFire()
  }

  // CPU: optionally reposition, then fire with wind-aware aim
  const cpuStart = () => {
    const st = s.current
    if (st.over) return
    if (Math.random() < 0.6) {
      const delta = (Math.random() - 0.5) * 120
      st.cpuMoveTarget = Math.max(st.W * 0.55, Math.min(st.W - 24, st.ax + delta))
      st.cpuMoving = true
    } else setTimeout(cpuShoot, 200)
  }

  const cpuShoot = () => {
    const st = s.current
    if (st.over) return
    const dist = Math.abs(st.ax - st.px)
    const ang = 45 + (Math.random() * 8 - 4)            // tighter angle band
    let pow = Math.sqrt(dist * GRAV / Math.sin(2 * ang * Math.PI / 180)) / (0.2 * WEAPONS.normal.vmul)
    pow -= st.wind * 60                                  // compensate wind toward player (player is left)
    if (st.cpuErr != null) pow -= st.cpuErr * 0.3        // strong correction from last miss
    else pow += (Math.random() - 0.5) * 5
    pow = Math.max(20, Math.min(100, pow + (Math.random() - 0.5) * 3)) // small spread → accurate
    launch('cpu', ang, pow, 'normal')
  }

  const reset = () => setRound(r => r + 1)
  const cycleWeapon = () => {
    const st = s.current
    const i = (WORDER.indexOf(st.weapon) + 1) % WORDER.length
    st.weapon = WORDER[i]; setWeapon(st.weapon)
  }

  useEffect(() => {
    const norm = (k: string) => (k === 'й' || k === 'Й') ? 'q' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'q', 'Q', 'й', 'Й'].includes(e.key)) return
      e.preventDefault()
      const st = s.current
      if (st.over) { if (e.key === ' ') reset(); return }
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      if (nk === 'q') { cycleWeapon(); return }
      if (turnRef.current !== 'you' || st.shell) return
      st.keys[nk] = true
      if (e.key === 'ArrowUp') { st.angle = Math.min(89, st.angle + 2); setAngle(st.angle) }
      else if (e.key === 'ArrowDown') { st.angle = Math.max(1, st.angle - 2); setAngle(st.angle) }
      else if (e.key === ' ' && !st.charging) { st.power = 0; setPower(0); st.charging = true; setCharging(true) }
    }
    const up = (e: KeyboardEvent) => {
      const st = s.current
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      st.keys[nk] = false
      if (e.key === ' ' && st.charging && turnRef.current === 'you' && !st.over) fire()
    }
    window.addEventListener('keydown', down); window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const total = stats.wins + stats.losses
  const acc = stats.shots ? Math.round((stats.hits / stats.shots) * 100) : 0
  const windDir = wind > 0.005 ? `→ ${Math.abs(Math.round(wind * 100))}` : wind < -0.005 ? `← ${Math.abs(Math.round(wind * 100))}` : 'штиль'

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span>УГОЛ {angle}°</span>
        <span className={charging ? 'text-[#ffd24c]' : ''}>СИЛА {Math.round(power)}</span>
        <span>HP {hpP}</span>
        <span className="text-[#666]">ИИ {hpC}</span>
        <span className="text-[#5cc8ff]">ветер {windDir}</span>
        <span className="flex-1 text-right">{msg ? msg : turn === 'you' ? 'ваш ход' : 'ход ИИ…'}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ход · ↑ ↓ угол · пробел — сила/огонь · Q оружие: <span className="text-[#ffd24c]">{WEAPONS[weapon].name}</span>{msg ? ' · пробел — заново' : ''}</span>
        <span>W {stats.wins} · L {stats.losses}{total ? ` · ${acc}%` : ''}</span>
      </div>
    </div>
  )
}

function drawTank(c: CanvasRenderingContext2D, x: number, y: number, ang: number, dir: number, hp: number, _col: string) {
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
