import { useRef, useEffect, useState } from 'react'

// ── 8-bit audio ───────────────────────────────────────────────────────────────
let audioCtx: AudioContext | null = null
function ctx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
  return audioCtx
}
function tone(freq: number, dur: number, type: OscillatorType, vol: number, at = 0) {
  const c = ctx()
  const t = (c.state !== 'running' ? c.currentTime + 0.05 : c.currentTime) + at
  const o = c.createOscillator(), g = c.createGain()
  o.type = type; o.frequency.setValueAtTime(Math.max(freq, 1), t)
  g.gain.setValueAtTime(vol, t)
  g.gain.exponentialRampToValueAtTime(0.0005, t + dur)
  o.connect(g); g.connect(c.destination)
  o.start(t); o.stop(t + dur + 0.02)
}
const sndFire = () => { tone(220, 0.12, 'square', 0.15); tone(440, 0.1, 'square', 0.12, 0.04) }
const sndBoom = () => { tone(160, 0.35, 'sawtooth', 0.2); tone(90, 0.4, 'square', 0.15, 0.02) }
const sndWin = () => [523, 659, 784, 1047].forEach((f, i) => tone(f, 0.14, 'square', 0.15, i * 0.1))
const sndLose = () => [392, 330, 262, 196].forEach((f, i) => tone(f, 0.18, 'square', 0.15, i * 0.12))

// ── Game ───────────────────────────────────────────────────────────────────────
const W = 420, H = 240, G = 0.18

interface Shell { x: number; y: number; vx: number; vy: number }

export default function ArtilleryGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [angle, setAngle] = useState(45)
  const [power, setPower] = useState(55)
  const [turn, setTurn] = useState<'you' | 'cpu'>('you')
  const [msg, setMsg] = useState('')
  const [round, setRound] = useState(0) // bump to restart

  const state = useRef({
    terrain: [] as number[],
    px: 36, ax: W - 36, // gun x
    py: 0, ay: 0,        // gun y (on terrain)
    shell: null as Shell | null,
    shooter: 'you' as 'you' | 'cpu',
    over: false,
    cpuLastErr: null as number | null, // signed miss distance for aim correction
    angle: 45, power: 55,
  })
  const angleRef = useRef(angle); angleRef.current = angle
  const powerRef = useRef(power); powerRef.current = power
  const turnRef = useRef(turn); turnRef.current = turn

  // setup terrain + render loop
  useEffect(() => {
    const canvas = canvasRef.current!
    const c = canvas.getContext('2d')!
    const dpr = window.devicePixelRatio || 1
    canvas.width = W * dpr; canvas.height = H * dpr
    c.setTransform(dpr, 0, 0, dpr, 0, 0)

    const s = state.current
    // terrain: rolling hills
    const t: number[] = []
    const base = H * 0.62
    const ph = Math.random() * 6
    for (let x = 0; x < W; x++) {
      const y = base
        + Math.sin(x * 0.012 + ph) * 26
        + Math.sin(x * 0.05 + ph * 2) * 10
      t.push(y)
    }
    s.terrain = t
    s.py = t[s.px]; s.ay = t[s.ax]
    s.shell = null; s.over = false; s.shooter = 'you'; s.cpuLastErr = null
    setTurn('you'); setMsg('')

    let raf = 0
    const draw = () => {
      c.fillStyle = '#000'; c.fillRect(0, 0, W, H)
      // terrain
      c.fillStyle = '#fff'; c.beginPath(); c.moveTo(0, H)
      for (let x = 0; x < W; x++) c.lineTo(x, t[x])
      c.lineTo(W, H); c.closePath(); c.fill()
      // guns (small turrets) — drawn as black notches with a barrel
      const drawGun = (gx: number, gy: number, ang: number, dir: number, me: boolean) => {
        c.fillStyle = '#000'
        c.beginPath(); c.arc(gx, gy - 4, 7, Math.PI, 0); c.fill()
        c.strokeStyle = me ? '#000' : '#000'; c.lineWidth = 3
        const a = (ang * Math.PI) / 180
        c.beginPath(); c.moveTo(gx, gy - 6)
        c.lineTo(gx + Math.cos(a) * 14 * dir, gy - 6 - Math.sin(a) * 14); c.stroke()
        // outline so black turret shows on white ground
        c.strokeStyle = '#fff'; c.lineWidth = 1
        c.beginPath(); c.arc(gx, gy - 4, 7, Math.PI, 0); c.stroke()
      }
      drawGun(s.px, s.py, angleRef.current, 1, true)
      drawGun(s.ax, s.ay, 45, -1, false)
      // shell
      if (s.shell) {
        c.fillStyle = '#000'
        c.beginPath(); c.arc(s.shell.x, s.shell.y, 3, 0, Math.PI * 2); c.fill()
        c.strokeStyle = '#fff'; c.lineWidth = 1; c.stroke()
      }
      raf = requestAnimationFrame(draw)
    }
    draw()
    return () => cancelAnimationFrame(raf)
  }, [round])

  // physics tick for the shell
  useEffect(() => {
    let raf = 0
    const tick = () => {
      const s = state.current
      const sh = s.shell
      if (sh) {
        sh.x += sh.vx; sh.y += sh.vy; sh.vy += G
        const ix = Math.round(sh.x)
        const hitGround = ix >= 0 && ix < W && sh.y >= s.terrain[ix]
        const offscreen = sh.x < -20 || sh.x > W + 20 || sh.y > H + 40
        const target = s.shooter === 'you' ? { x: s.ax, y: s.ay } : { x: s.px, y: s.py }
        const hitTarget = Math.hypot(sh.x - target.x, sh.y - target.y) < 12

        if (hitTarget) {
          sndBoom(); crater(s.terrain, target.x, 16); s.shell = null; s.over = true
          if (s.shooter === 'you') { setMsg('🏆 ПОБЕДА'); sndWin() }
          else { setMsg('💥 ПОРАЖЕНИЕ'); sndLose() }
        } else if (hitGround || offscreen) {
          if (hitGround) { sndBoom(); crater(s.terrain, sh.x, 12); s.py = s.terrain[s.px]; s.ay = s.terrain[s.ax] }
          // record miss for cpu aim
          if (s.shooter === 'cpu') s.cpuLastErr = sh.x - s.px
          s.shell = null
          // pass turn
          const next = s.shooter === 'you' ? 'cpu' : 'you'
          s.shooter = next; setTurn(next)
          if (next === 'cpu') setTimeout(cpuShoot, 700)
        }
      }
      raf = requestAnimationFrame(tick)
    }
    tick()
    return () => cancelAnimationFrame(raf)
  }, [round])

  const fire = (shooter: 'you' | 'cpu', ang: number, pow: number) => {
    const s = state.current
    if (s.shell || s.over) return
    const v = pow * 0.16
    const a = (ang * Math.PI) / 180
    const dir = shooter === 'you' ? 1 : -1
    const gx = shooter === 'you' ? s.px : s.ax
    const gy = shooter === 'you' ? s.py : s.ay
    s.shell = { x: gx + dir * 14, y: gy - 8, vx: Math.cos(a) * v * dir, vy: -Math.sin(a) * v }
    sndFire()
  }

  const cpuShoot = () => {
    const s = state.current
    if (s.over) return
    // aim toward player with correction from last miss
    let ang = 38 + Math.random() * 20
    const dist = Math.abs(s.ax - s.px)
    let pow = Math.min(95, 30 + dist * 0.12)
    if (s.cpuLastErr != null) {
      // err > 0 means shell landed right of player (overshoot toward center) → reduce power
      pow -= s.cpuLastErr * 0.18
    } else {
      pow += (Math.random() - 0.5) * 18 // first shot: spread
    }
    pow = Math.max(20, Math.min(98, pow))
    fire('cpu', ang, pow)
  }

  // keyboard
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' '].includes(e.key)) return
      e.preventDefault()
      if (state.current.over) { if (e.key === ' ') setRound(r => r + 1); return }
      if (turnRef.current !== 'you' || state.current.shell) return
      if (e.key === 'ArrowLeft') setAngle(a => Math.min(89, a + 2))
      else if (e.key === 'ArrowRight') setAngle(a => Math.max(1, a - 2))
      else if (e.key === 'ArrowUp') setPower(p => Math.min(98, p + 2))
      else if (e.key === 'ArrowDown') setPower(p => Math.max(10, p - 2))
      else if (e.key === ' ') fire('you', angleRef.current, powerRef.current)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="flex flex-col items-center gap-1" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: W, maxWidth: '100%', height: H, imageRendering: 'pixelated', border: '1px solid #252525', borderRadius: 6 }} />
      <div className="flex items-center gap-4 text-[11px] font-mono text-[#999] w-full max-w-[420px] px-1">
        <span>УГОЛ {angle}°</span>
        <span>СИЛА {power}</span>
        <span className="flex-1 text-right">
          {msg ? msg : turn === 'you' ? 'твой ход' : 'ход ИИ…'}
        </span>
      </div>
      <p className="text-[9px] text-[#383838] text-center">← → угол · ↑ ↓ сила · пробел — огонь{msg ? ' · пробел — заново' : ''}</p>
    </div>
  )
}

function crater(terrain: number[], cx: number, r: number) {
  for (let x = Math.max(0, Math.floor(cx - r)); x < Math.min(W, cx + r); x++) {
    const dy = Math.sqrt(Math.max(0, r * r - (x - cx) ** 2))
    terrain[x] = Math.min(H - 2, terrain[x] + dy * 0.5)
  }
}
