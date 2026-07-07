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
const sndBounce = () => tone(300, 0.04, 'square', 0.08)
const sndSplash = () => { tone(420, 0.18, 'sine', 0.14); tone(220, 0.22, 'sine', 0.1, 0.03) }

interface Stats { wins: number; losses: number; shots: number; hits: number }
const STAT_KEY = 'artillery_stats'
function loadStats(): Stats {
  try { return { wins: 0, losses: 0, shots: 0, hits: 0, ...(JSON.parse(localStorage.getItem(STAT_KEY) || '{}')) } }
  catch { return { wins: 0, losses: 0, shots: 0, hits: 0 } }
}
function saveStats(s: Stats) { try { localStorage.setItem(STAT_KEY, JSON.stringify(s)) } catch {} }

// weapons
type WKind = 'normal' | 'grenade' | 'heavy' | 'cluster'
const WEAPONS: Record<WKind, { name: string; r: number; dmg: number; vmul: number; cluster?: boolean; fuse?: number }> = {
  normal: { name: 'базука', r: 22, dmg: 46, vmul: 1 },
  grenade: { name: 'граната', r: 26, dmg: 56, vmul: 1.05, fuse: 2200 },
  heavy: { name: 'тяжёлый', r: 34, dmg: 72, vmul: 0.9 },
  cluster: { name: 'кластер', r: 16, dmg: 28, vmul: 1, cluster: true },
}
const WORDER: WKind[] = ['normal', 'grenade', 'heavy', 'cluster']

const H = 340
const GRAV = 0.16
const MAXHP = 100
const MOVE_SPEED = 2.2
const CHARGE_PER_S = 70
const JUMP_V = -4.2          // worm hop strength
const TEAM_SIZE = 3
const WATER_H = 26           // height of the water band at the bottom

type Team = 'you' | 'cpu'
interface Worm {
  x: number; y: number; hp: number
  vy: number; airborne: boolean
  facing: 1 | -1; walkPhase: number
  team: Team; alive: boolean
}
interface Shell { x: number; y: number; vx: number; vy: number; w: WKind; fuse?: number }
interface Particle { x: number; y: number; vx: number; vy: number; life: number; max: number; water?: boolean }

export default function ArtilleryGame() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [angle, setAngle] = useState(50)
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [hpP, setHpP] = useState(MAXHP * TEAM_SIZE)
  const [hpC, setHpC] = useState(MAXHP * TEAM_SIZE)
  const [aliveP, setAliveP] = useState(TEAM_SIZE)
  const [aliveC, setAliveC] = useState(TEAM_SIZE)
  const [turn, setTurn] = useState<Team>('you')
  const [msg, setMsg] = useState('')
  const [round, setRound] = useState(0)
  const [stats, setStats] = useState<Stats>(loadStats)
  const [weapon, setWeapon] = useState<WKind>('normal')
  const [wind, setWind] = useState(0)

  const s = useRef({
    W: 600, terrain: [] as number[],
    worms: [] as Worm[],
    pIdx: 0, cIdx: 0,            // active worm index within each team's living order
    shell: null as Shell | null,
    shooter: 'you' as Team,
    over: false,
    charging: false, power: 0, angle: 50,
    cpuErr: null as number | null,
    cpuMoving: false, cpuMoveTarget: 0,
    weapon: 'normal' as WKind,
    wind: 0,
    parts: [] as Particle[], shake: 0,
    camS: 1, camTop: 0,
    keys: {} as Record<string, boolean>,
  })
  const turnRef = useRef(turn); turnRef.current = turn

  const bumpStat = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

  // helpers ----------------------------------------------------------------
  const livingOf = (team: Team) => s.current.worms.filter(w => w.team === team && w.alive)
  const activeWorm = (): Worm | null => {
    const st = s.current
    const team = st.shooter
    const living = livingOf(team)
    if (living.length === 0) return null
    const idx = (team === 'you' ? st.pIdx : st.cIdx) % living.length
    return living[idx]
  }
  const waterY = H - WATER_H

  const syncHud = () => {
    const p = livingOf('you'), c = livingOf('cpu')
    setHpP(p.reduce((a, w) => a + w.hp, 0)); setHpC(c.reduce((a, w) => a + w.hp, 0))
    setAliveP(p.length); setAliveC(c.length)
  }

  useEffect(() => {
    const canvas = canvasRef.current!, c = canvas.getContext('2d')!
    const W = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr
    c.setTransform(dpr, 0, 0, dpr, 0, 0)
    const st = s.current
    st.W = W

    const t: number[] = []
    const base = H * 0.5, ph = Math.random() * 6
    for (let x = 0; x < W; x++) {
      const h = base + Math.sin(x * 0.009 + ph) * 38 + Math.sin(x * 0.035 + ph * 2) * 16 + Math.sin(x * 0.08) * 6
      t.push(Math.min(h, waterY - 6)) // keep ground above the water line
    }
    st.terrain = t

    // spawn two teams spread across the map
    const worms: Worm[] = []
    for (let i = 0; i < TEAM_SIZE; i++) {
      const px = Math.round(W * (0.08 + i * 0.12))
      worms.push({ x: px, y: t[px], hp: MAXHP, vy: 0, airborne: false, facing: 1, walkPhase: 0, team: 'you', alive: true })
      const cx = Math.round(W * (0.92 - i * 0.12))
      worms.push({ x: cx, y: t[cx], hp: MAXHP, vy: 0, airborne: false, facing: -1, walkPhase: 0, team: 'cpu', alive: true })
    }
    st.worms = worms
    st.pIdx = 0; st.cIdx = 0
    st.shell = null; st.over = false; st.shooter = 'you'; st.cpuErr = null
    st.charging = false; st.power = 0; st.angle = 50
    st.parts = []; st.shake = 0; st.cpuMoving = false; st.camS = 1; st.camTop = 0
    st.wind = (Math.random() - 0.5) * 0.1
    setAngle(50); setPower(0); setTurn('you'); setMsg(''); setWind(st.wind)
    syncHud()

    let raf = 0, last = performance.now()
    const loop = (now: number) => {
      const dt = Math.min(40, now - last); last = now
      // A thrown frame must not kill the loop (rAF errors aren't caught by React)
      try { update(dt); render(c) } catch (err) { console.error('[ArtilleryGame] frame error', err) }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [round])

  const passTurn = (to: Team) => {
    const st = s.current
    // advance the rotation of the team that just shot
    const justShot = st.shooter
    const livingJust = livingOf(justShot)
    if (livingJust.length > 0) {
      if (justShot === 'you') st.pIdx = (st.pIdx + 1) % livingJust.length
      else st.cIdx = (st.cIdx + 1) % livingJust.length
    }
    st.shooter = to; setTurn(to)
    if (to === 'you') { st.power = 0; setPower(0) }
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
  const spawnSplash = (x: number) => {
    const st = s.current
    for (let i = 0; i < 12; i++) {
      const a = -Math.PI / 2 + (Math.random() - 0.5) * 1.2, sp = 1 + Math.random() * 3
      st.parts.push({ x, y: waterY, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp, life: 1, max: 1, water: true })
    }
  }

  const checkOver = () => {
    const st = s.current
    const p = livingOf('you').length, c = livingOf('cpu').length
    if (p > 0 && c > 0) return
    st.over = true
    if (c === 0 && p > 0) { setMsg('🏆 ПОБЕДА'); sndWin(); bumpStat('wins') }
    else if (p === 0 && c > 0) { setMsg('💥 ПОРАЖЕНИЕ'); sndLose(); bumpStat('losses') }
    else { setMsg('💥 НИЧЬЯ'); sndLose() }
  }

  const doDamage = (bx: number, by: number, w: WKind) => {
    const st = s.current, cfg = WEAPONS[w]
    crater(st.terrain, bx, cfg.r, st.W, waterY)
    // re-settle every worm onto the new terrain & apply damage + knockback
    for (const wm of st.worms) {
      if (!wm.alive) continue
      const d = Math.hypot(bx - wm.x, by - (wm.y - 8))
      const reach = cfg.r + 16
      if (d < reach) {
        const f = 1 - d / reach
        const dmg = Math.round(f * cfg.dmg)
        if (dmg > 0 && wm.team !== st.shooter && st.shooter === 'you') bumpStat('hits')
        wm.hp = Math.max(0, wm.hp - dmg)
        // knockback: push away from the blast
        const ang = Math.atan2((wm.y - 8) - by, wm.x - bx)
        wm.x = Math.max(14, Math.min(st.W - 14, wm.x + Math.cos(ang) * f * 26))
        wm.vy = Math.min(wm.vy, -Math.abs(Math.sin(ang)) * f * 5 - f * 2)
        wm.airborne = true
        if (wm.hp <= 0) wm.alive = false
      }
      if (wm.alive) wm.y = Math.min(wm.y, st.terrain[Math.max(0, Math.min(st.W - 1, Math.round(wm.x)))])
    }
    syncHud()
  }

  const explode = (bx: number, by: number, w: WKind) => {
    sndBoom(); spawnBoom(bx, by, 18)
    doDamage(bx, by, w)
    if (WEAPONS[w].cluster) {
      for (const off of [-26, 26]) {
        const cx = Math.max(0, Math.min(s.current.W - 1, Math.round(bx + off)))
        doDamage(bx + off, s.current.terrain[cx], w); spawnBoom(bx + off, by, 8)
      }
    }
    checkOver()
  }

  const drown = (wm: Worm) => {
    wm.alive = false; wm.hp = 0; spawnSplash(wm.x); sndSplash(); syncHud(); checkOver()
  }

  const nearestEnemyX = (team: Team): number | null => {
    const me = activeWorm(); if (!me) return null
    const enemies = livingOf(team === 'you' ? 'cpu' : 'you')
    if (enemies.length === 0) return null
    return enemies.reduce((best, w) => Math.abs(w.x - me.x) < Math.abs(best - me.x) ? w.x : best, enemies[0].x)
  }

  const update = (dt: number) => {
    const st = s.current
    // particles
    for (const p of st.parts) { p.x += p.vx; p.y += p.vy; p.vy += p.water ? 0.18 : 0.15; p.life -= dt / 600 }
    st.parts = st.parts.filter(p => p.life > 0)
    if (st.shake > 0) st.shake = Math.max(0, st.shake - dt / 30)

    // dynamic camera
    const shY = st.shell ? st.shell.y : H
    const visibleTop = Math.min(0, shY - 40)
    const targetS = H / (H - visibleTop)
    const ease = Math.min(1, dt / 120)
    st.camS += (targetS - st.camS) * ease
    st.camTop += (visibleTop - st.camTop) * ease

    if (st.over) return

    // worm physics (knockback / falling) for every worm
    for (const wm of st.worms) {
      if (!wm.alive) continue
      if (wm.airborne) {
        wm.vy += GRAV; wm.y += wm.vy
        const ground = st.terrain[Math.max(0, Math.min(st.W - 1, Math.round(wm.x)))]
        if (wm.y >= ground && wm.vy >= 0) { wm.y = ground; wm.airborne = false; wm.vy = 0 }
      }
      if (wm.alive && wm.y >= waterY) drown(wm)
    }
    if (st.over) return

    const me = activeWorm()
    if (st.shooter === 'you' && !st.shell && me) {
      const onGround = !me.airborne
      if (st.keys['ArrowLeft']) { me.x = Math.max(14, me.x - MOVE_SPEED); me.facing = -1; me.walkPhase += dt / 60; if (onGround) { me.y = st.terrain[Math.round(me.x)]; if (Math.random() < 0.3) sndMove() } }
      if (st.keys['ArrowRight']) { me.x = Math.min(st.W - 14, me.x + MOVE_SPEED); me.facing = 1; me.walkPhase += dt / 60; if (onGround) { me.y = st.terrain[Math.round(me.x)]; if (Math.random() < 0.3) sndMove() } }
      if (st.keys['w'] && onGround) { me.airborne = true; me.vy = JUMP_V; st.keys['w'] = false; sndMove() }
      if (st.charging) { st.power = Math.min(100, st.power + dt / 1000 * CHARGE_PER_S); setPower(Math.round(st.power)) }
    }

    // cpu walking to its chosen spot before firing
    if (st.cpuMoving) {
      const cw = activeWorm()
      if (!cw) { st.cpuMoving = false }
      else {
        const d = st.cpuMoveTarget - cw.x
        if (Math.abs(d) < MOVE_SPEED) { cw.x = st.cpuMoveTarget; st.cpuMoving = false; setTimeout(cpuShoot, 250) }
        else { cw.x += Math.sign(d) * MOVE_SPEED; cw.y = st.terrain[Math.round(cw.x)]; cw.facing = (Math.sign(d) || -1) as 1 | -1; if (Math.random() < 0.3) sndMove() }
      }
    }

    const sh = st.shell
    if (sh) {
      sh.vx += st.wind * dt / 16
      sh.x += sh.vx; sh.y += sh.vy; sh.vy += GRAV
      const ix = Math.round(sh.x)
      const inWater = sh.y >= waterY && sh.x >= 0 && sh.x <= st.W
      const ground = ix >= 0 && ix < st.W && sh.y >= st.terrain[ix]
      const off = sh.x < -30 || sh.x > st.W + 30 || sh.y > H + 60

      if (sh.fuse !== undefined) {
        // grenade: bounces off terrain, explodes when fuse runs out
        sh.fuse -= dt
        if (inWater) { sndSplash(); spawnSplash(sh.x); st.shell = null; if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you'); return }
        if (ground && ix >= 0 && ix < st.W) {
          sh.y = st.terrain[ix] - 1
          sh.vy *= -0.46; sh.vx *= 0.62
          if (Math.abs(sh.vy) > 0.8) sndBounce()
        }
        if (sh.fuse <= 0) {
          explode(sh.x, Math.min(sh.y, ground ? st.terrain[ix] : sh.y), sh.w)
          if (st.shooter === 'cpu') st.cpuErr = sh.x - (nearestEnemyX('cpu') ?? sh.x)
          st.shell = null
          if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you')
        } else if (off) {
          st.shell = null; if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you')
        }
        return
      }

      // direct/contact weapons
      let directHit = false
      for (const wm of st.worms) {
        if (wm.alive && wm.team !== st.shooter && Math.hypot(sh.x - wm.x, sh.y - (wm.y - 8)) < 11) { directHit = true; break }
      }
      if (inWater && !ground) { sndSplash(); spawnSplash(sh.x); st.shell = null; if (!st.over) passTurn(st.shooter === 'you' ? 'cpu' : 'you'); return }
      if (directHit || ground) {
        explode(sh.x, ground ? st.terrain[ix] : sh.y, sh.w)
        if (st.shooter === 'cpu') st.cpuErr = sh.x - (nearestEnemyX('cpu') ?? sh.x)
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
    c.translate(W / 2, 0); c.scale(st.camS, st.camS); c.translate(-W / 2, -st.camTop)
    // sky
    const sky = c.createLinearGradient(0, st.camTop - 40, 0, H)
    sky.addColorStop(0, '#3a6bb0'); sky.addColorStop(1, '#9ec8e8')
    c.fillStyle = sky; c.fillRect(-W, st.camTop - 40, W * 3, H + 200)
    // clouds
    c.fillStyle = '#ffffff44'
    for (const [cx, cy, r] of [[W * 0.2, 40, 22], [W * 0.55, 24, 18], [W * 0.8, 50, 26]] as [number, number, number][]) {
      c.beginPath(); c.arc(cx, cy, r, 0, Math.PI * 2); c.arc(cx + r, cy + 4, r * 0.8, 0, Math.PI * 2); c.arc(cx - r, cy + 4, r * 0.7, 0, Math.PI * 2); c.fill()
    }
    // ground
    c.fillStyle = '#6b4a2b'; c.beginPath(); c.moveTo(-W, H)
    c.lineTo(-W, t[0]); for (let x = 0; x < W; x++) c.lineTo(x, t[x]); c.lineTo(W * 2, t[W - 1]); c.lineTo(W * 2, H); c.closePath(); c.fill()
    c.strokeStyle = '#4caf50'; c.lineWidth = 4; c.lineJoin = 'round'
    c.beginPath(); c.moveTo(0, t[0]); for (let x = 1; x < W; x++) c.lineTo(x, t[x]); c.stroke()

    // water band with a moving wavy top
    const wob = performance.now() / 400
    const wg = c.createLinearGradient(0, waterY, 0, H)
    wg.addColorStop(0, '#2b7fd4cc'); wg.addColorStop(1, '#11407acc')
    c.fillStyle = wg
    c.beginPath(); c.moveTo(-W, H)
    for (let x = -W; x <= W * 2; x += 8) c.lineTo(x, waterY + Math.sin(x * 0.05 + wob) * 2.5)
    c.lineTo(W * 2, H); c.closePath(); c.fill()
    c.strokeStyle = '#bfe3ff88'; c.lineWidth = 1.5
    c.beginPath(); for (let x = -W; x <= W * 2; x += 8) { const yy = waterY + Math.sin(x * 0.05 + wob) * 2.5; x === -W ? c.moveTo(x, yy) : c.lineTo(x, yy) } c.stroke()

    // aiming crosshair for the active player worm
    const me = activeWorm()
    if (st.shooter === 'you' && !st.shell && !st.over && me) {
      const a = (st.angle * Math.PI) / 180
      const ox = me.x, oy = me.y - 8
      const R = 46
      const cx2 = ox + Math.cos(a) * R, cy2 = oy - Math.sin(a) * R
      c.strokeStyle = '#e8c56a66'; c.lineWidth = 1
      c.beginPath(); c.moveTo(ox + Math.cos(a) * 14, oy - Math.sin(a) * 14); c.lineTo(cx2, cy2); c.stroke()
      c.strokeStyle = '#e8c56a'; c.lineWidth = 1.5
      c.beginPath(); c.arc(cx2, cy2, 6, 0, Math.PI * 2); c.stroke()
      c.beginPath()
      c.moveTo(cx2 - 10, cy2); c.lineTo(cx2 - 3, cy2); c.moveTo(cx2 + 3, cy2); c.lineTo(cx2 + 10, cy2)
      c.moveTo(cx2, cy2 - 10); c.lineTo(cx2, cy2 - 3); c.moveTo(cx2, cy2 + 3); c.lineTo(cx2, cy2 + 10)
      c.stroke()
      c.fillStyle = '#e8c56a'; c.beginPath(); c.arc(cx2, cy2, 1.4, 0, Math.PI * 2); c.fill()
      if (st.charging) {
        const bw = 40, bx = ox - bw / 2, by = oy - 30, p = st.power / 100
        c.fillStyle = '#000'; c.fillRect(bx - 1, by - 1, bw + 2, 6)
        const grad = c.createLinearGradient(bx, 0, bx + bw, 0)
        grad.addColorStop(0, '#5cc8ff'); grad.addColorStop(0.5, '#e8c56a'); grad.addColorStop(1, '#ff5c5c')
        c.fillStyle = grad; c.fillRect(bx, by, bw * p, 4)
      }
    }

    // worms — draw all living; the active one gets the gun + a bobbing marker
    for (const wm of st.worms) {
      if (!wm.alive) continue
      const isActive = me === wm
      const color = wm.team === 'you' ? '#d24c4c' : '#4c6cd2'
      const label = wm.team === 'you' ? 'ТЫ' : 'ИИ'
      const ang = isActive && wm.team === 'you' ? st.angle : (wm.team === 'you' ? 45 : 135)
      drawWorm(c, wm.x, wm.y, ang, wm.facing, wm.hp, color, label, wm.walkPhase, isActive)
      if (isActive && !st.over) {
        const py = wm.y - 40 + Math.sin(performance.now() / 250) * 2
        c.fillStyle = wm.team === 'you' ? '#e8c56a' : '#8fb0ff'
        c.beginPath(); c.moveTo(wm.x, py + 6); c.lineTo(wm.x - 4, py); c.lineTo(wm.x + 4, py); c.closePath(); c.fill()
      }
    }

    // shell
    if (st.shell) {
      const isGr = st.shell.w === 'grenade'
      c.fillStyle = isGr ? '#2f6b2f' : '#000'
      c.beginPath(); c.arc(st.shell.x, st.shell.y, st.shell.w === 'heavy' ? 5 : isGr ? 4 : 3.5, 0, Math.PI * 2); c.fill()
      c.strokeStyle = isGr ? '#9eff9e' : '#fff'; c.lineWidth = 1; c.stroke()
    }
    // particles
    for (const p of st.parts) { c.fillStyle = p.water ? (p.life > 0.5 ? '#bfe3ff' : '#7fb8e8') : (p.life > 0.5 ? '#000' : '#6f695f'); const sz = 2 + p.life * 2; c.fillRect(p.x - sz / 2, p.y - sz / 2, sz, sz) }
    c.restore()
  }

  const fire = () => {
    const st = s.current
    const me = activeWorm()
    if (st.shell || st.over || st.shooter !== 'you' || !me) return
    launch('you', st.angle, Math.max(8, st.power), st.weapon)
    st.charging = false; setCharging(false); bumpStat('shots')
  }

  const launch = (who: Team, ang: number, pow: number, w: WKind) => {
    const st = s.current
    const me = activeWorm(); if (!me) return
    const cfg = WEAPONS[w]
    const v = pow * 0.2 * cfg.vmul, a = (ang * Math.PI) / 180, dir = who === 'you' ? 1 : -1
    st.shell = { x: me.x + dir * 16, y: me.y - 12, vx: Math.cos(a) * v * dir, vy: -Math.sin(a) * v, w, ...(cfg.fuse ? { fuse: cfg.fuse } : {}) }
    sndFire()
  }

  // CPU: pick weapon, optionally reposition, then fire at nearest enemy
  const cpuStart = () => {
    const st = s.current
    if (st.over) return
    const cw = activeWorm(); if (!cw) { passTurn('you'); return }
    // CPU mostly uses the bazooka; occasionally a grenade when close
    st.weapon = (nearestDist() < st.W * 0.28 && Math.random() < 0.4) ? 'grenade' : 'normal'
    setWeapon(st.weapon)
    if (Math.random() < 0.5) {
      const delta = (Math.random() - 0.5) * 120
      st.cpuMoveTarget = Math.max(st.W * 0.5, Math.min(st.W - 18, cw.x + delta))
      st.cpuMoving = true
    } else setTimeout(cpuShoot, 200)
  }

  const nearestDist = () => {
    const me = activeWorm(); if (!me) return Infinity
    const ex = nearestEnemyX('cpu'); return ex == null ? Infinity : Math.abs(ex - me.x)
  }

  // Replicate the real shell physics to find where a shot lands (x on impact)
  const simulateLanding = (ang: number, pow: number) => {
    const st = s.current
    const me = activeWorm(); if (!me) return st.W
    const v = pow * 0.2 * WEAPONS[st.weapon].vmul, a = (ang * Math.PI) / 180
    let x = me.x - 16, y = me.y - 12
    let vx = Math.cos(a) * v * -1, vy = -Math.sin(a) * v
    for (let i = 0; i < 600; i++) {
      vx += st.wind
      x += vx; y += vy; vy += GRAV
      const ix = Math.round(x)
      if (x < -30 || x > st.W + 30 || y > H + 60) return x
      if (ix >= 0 && ix < st.W && y >= st.terrain[ix]) return x
    }
    return x
  }

  const cpuShoot = () => {
    const st = s.current
    if (st.over) return
    const me = activeWorm(); if (!me) { passTurn('you'); return }
    const targetX = nearestEnemyX('cpu') ?? st.W * 0.2
    const ang = 45 + (Math.random() * 8 - 4)
    let bestPow = 60, bestErr = Infinity
    for (let p = 20; p <= 100; p += 1.5) {
      const land = simulateLanding(ang, p)
      const err = Math.abs(land - targetX)
      if (err < bestErr) { bestErr = err; bestPow = p }
    }
    const pow = Math.max(20, Math.min(100, bestPow + (Math.random() - 0.5) * 10))
    launch('cpu', ang, pow, st.weapon)
  }

  const reset = () => setRound(r => r + 1)
  const cycleWeapon = () => {
    const st = s.current
    const i = (WORDER.indexOf(st.weapon) + 1) % WORDER.length
    st.weapon = WORDER[i]; setWeapon(st.weapon)
  }

  useEffect(() => {
    const norm = (k: string) => (k === 'й' || k === 'Й') ? 'q' : (k === 'ц' || k === 'Ц') ? 'w' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'q', 'Q', 'й', 'Й', 'w', 'W', 'ц', 'Ц'].includes(e.key)) return
      e.preventDefault()
      const st = s.current
      if (st.over) { if (e.key === ' ') reset(); return }
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      if (nk === 'q') { cycleWeapon(); return }
      if (turnRef.current !== 'you' || st.shell) return
      st.keys[nk] = true
      if (e.key === 'ArrowUp') { st.angle = Math.min(170, st.angle + 5); setAngle(st.angle) }
      else if (e.key === 'ArrowDown') { st.angle = Math.max(-80, st.angle - 5); setAngle(st.angle) }
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
      <canvas ref={canvasRef} style={{ width: '100%', height: H, display: 'block', imageRendering: 'pixelated', border: '1px solid #2a2723', borderRadius: 6 }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#a49d90] mt-1 px-1">
        <span>УГОЛ {angle}°</span>
        <span className={charging ? 'text-[#e8c56a]' : ''}>СИЛА {Math.round(power)}</span>
        <span className="text-[#d24c4c]">🐛 {aliveP} · {hpP}</span>
        <span className="text-[#6c8cf2]">ИИ {aliveC} · {hpC}</span>
        <span className="text-[#5cc8ff]">ветер {windDir}</span>
        <span className="flex-1 text-right">{msg ? msg : turn === 'you' ? 'ваш ход' : 'ход ИИ…'}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#4a463f] mt-0.5 px-1">
        <span>← → ход · W прыжок · ↑ ↓ угол · пробел — сила/огонь · Q: <span className="text-[#e8c56a]">{WEAPONS[weapon].name}</span>{msg ? ' · пробел — заново' : ''}</span>
        <span>W {stats.wins} · L {stats.losses}{total ? ` · ${acc}%` : ''}</span>
      </div>
    </div>
  )
}

// A Worms-style worm: rounded body, eyes, bobbing feet; the active one holds a bazooka.
function drawWorm(c: CanvasRenderingContext2D, x: number, y: number, ang: number, facing: 1 | -1, hp: number, color: string, label: string, walkPhase: number, showGun: boolean) {
  const a = (ang * Math.PI) / 180
  const bx = Math.cos(a) * facing, by = -Math.sin(a)
  const face = facing
  const bodyH = 20, bodyW = 13, cyB = y - bodyH / 2 - 2

  c.fillStyle = 'rgba(0,0,0,0.25)'; c.beginPath(); c.ellipse(x, y, 11, 3.5, 0, 0, Math.PI * 2); c.fill()

  const bob = Math.sin(walkPhase) * 1.5
  c.fillStyle = '#2a2a2a'
  c.beginPath(); c.ellipse(x - 4, y - 1 + bob, 4, 2.4, 0, 0, Math.PI * 2); c.fill()
  c.beginPath(); c.ellipse(x + 4, y - 1 - bob, 4, 2.4, 0, 0, Math.PI * 2); c.fill()

  c.fillStyle = color
  c.beginPath()
  c.moveTo(x - bodyW / 2, y - 2)
  c.lineTo(x - bodyW / 2, cyB)
  c.arc(x, cyB, bodyW / 2, Math.PI, 0)
  c.lineTo(x + bodyW / 2, y - 2)
  c.arc(x, y - 2, bodyW / 2, 0, Math.PI)
  c.closePath(); c.fill()
  c.fillStyle = 'rgba(255,255,255,0.18)'; c.beginPath(); c.ellipse(x - face * 2, cyB + 2, 3.5, 6, 0, 0, Math.PI * 2); c.fill()

  const eyeY = cyB - 3
  c.fillStyle = '#fff'
  c.beginPath(); c.arc(x + face * 1 - 3, eyeY, 3, 0, Math.PI * 2); c.arc(x + face * 1 + 3, eyeY, 3, 0, Math.PI * 2); c.fill()
  c.fillStyle = '#111'
  c.beginPath(); c.arc(x + face * 2 - 3, eyeY, 1.4, 0, Math.PI * 2); c.arc(x + face * 2 + 3, eyeY, 1.4, 0, Math.PI * 2); c.fill()

  if (showGun) {
    const gx = x, gy = cyB + 2
    c.strokeStyle = '#38342e'; c.lineWidth = 4; c.lineCap = 'round'
    c.beginPath(); c.moveTo(gx, gy); c.lineTo(gx + bx * 16, gy + by * 16); c.stroke()
    c.strokeStyle = '#7a7367'; c.lineWidth = 1.5
    c.beginPath(); c.moveTo(gx, gy); c.lineTo(gx + bx * 16, gy + by * 16); c.stroke()
  }

  const topY = cyB - 16
  c.font = '8px monospace'; c.textAlign = 'center'
  c.fillStyle = color; c.fillText(label, x, topY - 4)
  const bw = 24
  c.fillStyle = '#000a'; c.fillRect(x - bw / 2 - 1, topY, bw + 2, 5)
  c.fillStyle = hp > 50 ? '#4caf50' : hp > 25 ? '#e8c56a' : '#ff5c5c'
  c.fillRect(x - bw / 2, topY + 1, bw * (Math.max(0, hp) / 100), 3)
  c.textAlign = 'left'
}

function crater(terrain: number[], cx: number, r: number, W: number, maxY: number) {
  for (let x = Math.max(0, Math.floor(cx - r)); x < Math.min(W, cx + r); x++) {
    const dy = Math.sqrt(Math.max(0, r * r - (x - cx) ** 2))
    terrain[x] = Math.min(maxY - 2, terrain[x] + dy * 0.6)
  }
}
