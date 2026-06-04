import { useRef, useEffect, useState } from 'react'
import * as THREE from 'three'

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
  g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0005, t + dur)
  o.connect(g); g.connect(c.destination); o.start(t); o.stop(t + dur + 0.02)
}
const sndKick = () => tone(200, 0.08, 'square', 0.16)
const sndGoal = () => [523, 659, 784, 1047, 1319].forEach((f, i) => tone(f, 0.13, 'square', 0.15, i * 0.09))
const sndMiss = () => tone(160, 0.3, 'sawtooth', 0.16)
const sndSave = () => { tone(300, 0.1, 'square', 0.14); tone(180, 0.18, 'square', 0.12, 0.08) }
const sndWhistle = () => { tone(1800, 0.12, 'square', 0.1); tone(2200, 0.1, 'square', 0.08, 0.1) }

interface Stats { goals: number; shots: number }
const KEY = 'freekick3d_stats'
function loadStats(): Stats { try { return { goals: 0, shots: 0, ...(JSON.parse(localStorage.getItem(KEY) || '{}')) } } catch { return { goals: 0, shots: 0 } } }
function saveStats(s: Stats) { try { localStorage.setItem(KEY, JSON.stringify(s)) } catch {} }

// ── field constants (world units, metres-ish) ─────────────────────────────────
const GOAL_Z = -22       // goal plane
const GOAL_W = 7.32, GOAL_H = 2.44
const WALL_Z = -9
const GRAV = -9.8
const VIEW_H = 360

type Phase = 'aim' | 'fly' | 'done'

// build a football texture (white with black pentagon-ish spots)
function ballTexture(): THREE.Texture {
  const cv = document.createElement('canvas'); cv.width = cv.height = 128
  const x = cv.getContext('2d')!
  x.fillStyle = '#fff'; x.fillRect(0, 0, 128, 128)
  x.fillStyle = '#161616'
  const spots: [number, number, number][] = [[64, 64, 16], [24, 30, 11], [104, 30, 11], [30, 100, 11], [100, 100, 11], [64, 14, 9], [64, 114, 9]]
  for (const [cx, cy, r] of spots) {
    x.beginPath()
    for (let i = 0; i < 5; i++) { const a = (i / 5) * Math.PI * 2 - Math.PI / 2; const px = cx + Math.cos(a) * r, py = cy + Math.sin(a) * r; i ? x.lineTo(px, py) : x.moveTo(px, py) }
    x.closePath(); x.fill()
  }
  const tex = new THREE.CanvasTexture(cv); tex.wrapS = tex.wrapT = THREE.RepeatWrapping
  return tex
}

// a low-poly humanoid goalkeeper (group of boxes/spheres)
function buildKeeper(color: number) {
  const g = new THREE.Group()
  const mat = new THREE.MeshStandardMaterial({ color })
  const skin = new THREE.MeshStandardMaterial({ color: 0xffe39a })
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.8, 0.32), mat); torso.position.y = 1.2; g.add(torso)
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 12, 10), skin); head.position.y = 1.78; g.add(head)
  const mkLimb = (w: number, h: number, d: number) => new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)
  const armL = mkLimb(0.16, 0.62, 0.16); armL.position.set(-0.42, 1.3, 0)
  const armR = mkLimb(0.16, 0.62, 0.16); armR.position.set(0.42, 1.3, 0)
  const legL = mkLimb(0.18, 0.7, 0.18); legL.position.set(-0.16, 0.5, 0)
  const legR = mkLimb(0.18, 0.7, 0.18); legR.position.set(0.16, 0.5, 0)
  const gloveL = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), skin); gloveL.position.set(-0.42, 1.0, 0)
  const gloveR = new THREE.Mesh(new THREE.SphereGeometry(0.12, 8, 8), skin); gloveR.position.set(0.42, 1.0, 0)
  g.add(armL, armR, legL, legR, gloveL, gloveR)
  return { group: g, torso, head, armL, armR, legL, legR, gloveL, gloveR }
}

export default function FreeKick3D() {
  const wrapRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const [aimX, setAimX] = useState(0.5)
  const [aimY, setAimY] = useState(0.45)
  const [spin, setSpin] = useState(0)
  const [power, setPower] = useState(0)
  const [charging, setCharging] = useState(false)
  const [phase, setPhase] = useState<Phase>('aim')
  const [msg, setMsg] = useState('')
  const [stats, setStats] = useState<Stats>(loadStats)
  const [failed, setFailed] = useState<string | null>(null)

  const st = useRef({
    phase: 'aim' as Phase,
    aimX: 0.5, aimY: 0.45, spin: 0, power: 0, charging: false,
    ball: new THREE.Vector3(0, 0.11, 0),
    vel: new THREE.Vector3(), t: 0,
    keeper: null as ReturnType<typeof buildKeeper> | null,
    gkDive: 0, gkAnim: 0, gkActive: false, gkReach: 1.7, gkLag: 1,
    keys: {} as Record<string, boolean>,
    three: null as null | {
      scene: THREE.Scene; cam: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer
      ballMesh: THREE.Mesh; aimMarker: THREE.Mesh; trajLine: THREE.Line
    },
  })
  const rs = useRef({ aimX, aimY, spin, power, phase }); rs.current = { aimX, aimY, spin, power, phase }
  const bump = (k: keyof Stats) => setStats(p => { const n = { ...p, [k]: p[k] + 1 }; saveStats(n); return n })

  useEffect(() => {
    let renderer: THREE.WebGLRenderer
    try {
    const canvas = canvasRef.current!
    const W = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio))
    renderer.setSize(W, VIEW_H, false)
    renderer.shadowMap.enabled = true

    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x0a0e1e)
    scene.fog = new THREE.Fog(0x0a0e1e, 20, 50)

    const cam = new THREE.PerspectiveCamera(55, W / VIEW_H, 0.1, 200)
    cam.position.set(0, 2.4, 6); cam.lookAt(0, 1.4, GOAL_Z)

    scene.add(new THREE.AmbientLight(0x64709a, 0.7))
    const sun = new THREE.DirectionalLight(0xfff2d0, 1.0); sun.position.set(8, 18, 6); sun.castShadow = true
    sun.shadow.mapSize.set(1024, 1024); scene.add(sun)
    // floodlight glows
    const fl = new THREE.PointLight(0xfff6e0, 0.5, 80); fl.position.set(-10, 16, GOAL_Z - 4); scene.add(fl)
    const fr = new THREE.PointLight(0xfff6e0, 0.5, 80); fr.position.set(10, 16, GOAL_Z - 4); scene.add(fr)

    // pitch
    const pitch = new THREE.Mesh(new THREE.PlaneGeometry(60, 80), new THREE.MeshStandardMaterial({ color: 0x1c5a2e }))
    pitch.rotation.x = -Math.PI / 2; pitch.receiveShadow = true; scene.add(pitch)
    // mowing stripes
    for (let i = -8; i < 8; i++) {
      if (i % 2) continue
      const st2 = new THREE.Mesh(new THREE.PlaneGeometry(60, 3), new THREE.MeshStandardMaterial({ color: 0x217037 }))
      st2.rotation.x = -Math.PI / 2; st2.position.set(0, 0.01, i * 3 - 8); scene.add(st2)
    }

    // goal frame
    const postMat = new THREE.MeshStandardMaterial({ color: 0xffffff })
    const postGeo = new THREE.CylinderGeometry(0.08, 0.08, GOAL_H, 8)
    const lp = new THREE.Mesh(postGeo, postMat); lp.position.set(-GOAL_W / 2, GOAL_H / 2, GOAL_Z); scene.add(lp)
    const rp = new THREE.Mesh(postGeo, postMat); rp.position.set(GOAL_W / 2, GOAL_H / 2, GOAL_Z); scene.add(rp)
    const barGeo = new THREE.CylinderGeometry(0.08, 0.08, GOAL_W, 8)
    const bar = new THREE.Mesh(barGeo, postMat); bar.rotation.z = Math.PI / 2; bar.position.set(0, GOAL_H, GOAL_Z); scene.add(bar)
    // net (back + sides as line grids)
    const netMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.18 })
    const netGeo = new THREE.BufferGeometry()
    const pts: number[] = []
    const NZ = GOAL_Z - 2
    for (let i = 0; i <= 12; i++) { const x = -GOAL_W / 2 + (GOAL_W / 12) * i; pts.push(x, 0, NZ, x, GOAL_H, NZ) }
    for (let j = 0; j <= 5; j++) { const y = (GOAL_H / 5) * j; pts.push(-GOAL_W / 2, y, NZ, GOAL_W / 2, y, NZ) }
    // top slope
    for (let i = 0; i <= 12; i++) { const x = -GOAL_W / 2 + (GOAL_W / 12) * i; pts.push(x, GOAL_H, GOAL_Z, x, GOAL_H, NZ) }
    netGeo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    scene.add(new THREE.LineSegments(netGeo, netMat))

    // wall of players
    for (let i = 0; i < 4; i++) {
      const k = buildKeeper(0x2a4ec0); k.group.position.set((i - 1.5) * 0.7, 0, WALL_Z); k.group.scale.set(0.95, 0.95, 0.95)
      scene.add(k.group)
    }

    // keeper
    const keeper = buildKeeper(0xffd24c); keeper.group.position.set(0, 0, GOAL_Z + 0.6); scene.add(keeper.group)
    st.current.keeper = keeper

    // ball
    const ballMesh = new THREE.Mesh(new THREE.SphereGeometry(0.11, 24, 18), new THREE.MeshStandardMaterial({ map: ballTexture(), roughness: 0.6 }))
    ballMesh.castShadow = true; scene.add(ballMesh)

    // aim marker on goal
    const aimMarker = new THREE.Mesh(new THREE.RingGeometry(0.12, 0.18, 16), new THREE.MeshBasicMaterial({ color: 0xff5c5c, side: THREE.DoubleSide }))
    aimMarker.position.z = GOAL_Z + 0.05; scene.add(aimMarker)
    // trajectory preview line
    const trajLine = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineDashedMaterial({ color: 0xffff66, dashSize: 0.25, gapSize: 0.18 }))
    scene.add(trajLine)

    st.current.three = { scene, cam, renderer, ballMesh, aimMarker, trajLine }

    let raf = 0, last = performance.now()
    const loop = (now: number) => {
      const dt = Math.min(0.04, (now - last) / 1000); last = now
      try { update(dt); renderer.render(scene, cam) } catch (err) { console.error('[FreeKick3D loop]', err) }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    const onResize = () => {
      const w2 = Math.max(360, Math.floor(wrapRef.current?.clientWidth ?? 600))
      renderer.setSize(w2, VIEW_H, false); cam.aspect = w2 / VIEW_H; cam.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(onResize); ro.observe(wrapRef.current!)
    sndWhistle()

    return () => { cancelAnimationFrame(raf); ro.disconnect(); renderer.dispose() }
    } catch (err: any) {
      console.error('[FreeKick3D init]', err)
      setFailed(err?.message || 'WebGL недоступен')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // target point on the goal from aim
  const targetPoint = () => new THREE.Vector3((rs.current.aimX - 0.5) * GOAL_W, 0.2 + rs.current.aimY * (GOAL_H - 0.2), GOAL_Z)

  // initial velocity to reach target with given power
  const launchVel = (pow: number) => {
    const tgt = targetPoint()
    const dz = tgt.z - 0           // negative
    const speed = 14 + pow / 100 * 16   // m/s
    const flightT = Math.abs(dz) / speed
    const vx = (tgt.x - 0) / flightT
    const vy = (tgt.y - 0.11) / flightT - 0.5 * GRAV * flightT
    const vz = dz / flightT
    return new THREE.Vector3(vx, vy, vz)
  }

  const update = (dt: number) => {
    const S = st.current, T = S.three; if (!T) return
    const ph = S.phase

    // spin ball visually (horizontal axis = rolls; we spin around Y for curl look + X for travel)
    T.ballMesh.rotation.y += (ph === 'fly' ? S.spin / 100 * 0.25 + 0.1 : 0.01)
    T.ballMesh.rotation.x -= ph === 'fly' ? 0.3 : 0.01

    if (ph === 'aim') {
      const k = S.keys
      if (k['ArrowLeft']) { S.aimX = Math.max(0.02, S.aimX - dt * 0.7); setAimX(S.aimX) }
      if (k['ArrowRight']) { S.aimX = Math.min(0.98, S.aimX + dt * 0.7); setAimX(S.aimX) }
      if (k['ArrowUp']) { S.aimY = Math.min(0.98, S.aimY + dt * 0.7); setAimY(S.aimY) }
      if (k['ArrowDown']) { S.aimY = Math.max(0.02, S.aimY - dt * 0.7); setAimY(S.aimY) }
      if (k['a']) { S.spin = Math.max(-100, S.spin - dt * 90); setSpin(Math.round(S.spin)) }
      if (k['d']) { S.spin = Math.min(100, S.spin + dt * 90); setSpin(Math.round(S.spin)) }
      if (S.charging) { S.power = Math.min(100, S.power + dt * 75); setPower(Math.round(S.power)) }

      S.ball.set(0, 0.11, 0)
      T.ballMesh.position.copy(S.ball)
      const tgt = targetPoint(); T.aimMarker.position.set(tgt.x, tgt.y, GOAL_Z + 0.05); T.aimMarker.visible = true
      // preview trajectory
      const v = launchVel(Math.max(20, S.power)); const pos = new THREE.Vector3(0, 0.11, 0); const vv = v.clone()
      const arr: number[] = []
      for (let i = 0; i < 60; i++) {
        arr.push(pos.x, pos.y, pos.z)
        const sideAcc = S.spin / 100 * 9
        vv.x += sideAcc * dt; vv.y += GRAV * dt; pos.addScaledVector(vv, dt)
        if (pos.z < GOAL_Z) break
      }
      T.trajLine.geometry.setAttribute('position', new THREE.Float32BufferAttribute(arr, 3))
      ;(T.trajLine as any).computeLineDistances?.(); T.trajLine.visible = true
    } else {
      T.aimMarker.visible = false; T.trajLine.visible = false
    }

    if (ph === 'fly') {
      S.t += dt
      const sideAcc = S.spin / 100 * 9     // Magnus curl
      S.vel.x += sideAcc * dt
      S.vel.y += GRAV * dt
      S.ball.addScaledVector(S.vel, dt)
      T.ballMesh.position.copy(S.ball)

      // keeper reacts: start diving partway
      if (!S.gkActive && S.ball.z < -4) {
        // read current lateral velocity direction (curl can fool him)
        S.gkDive = Math.sign(S.vel.x + (S.ball.x) * 0.3) || (Math.random() < 0.5 ? -1 : 1)
        if (Math.random() < 0.12) S.gkDive *= -1
        S.gkActive = true; S.gkAnim = 0
      }
      if (S.gkActive) S.gkAnim = Math.min(1, S.gkAnim + dt / 0.7) // ~0.7s dive (≈42 frames @60fps)
      animateKeeper(S)

      // ground
      if (S.ball.y <= 0.11 && S.vel.y < 0 && S.ball.z > GOAL_Z) { S.ball.y = 0.11; finish('МИМО', false); return }
      // reached goal plane
      if (S.ball.z <= GOAL_Z) {
        const inGoal = Math.abs(S.ball.x) < GOAL_W / 2 - 0.12 && S.ball.y > 0.12 && S.ball.y < GOAL_H - 0.12
        const kp = S.keeper!.group.position
        const handsY = 1.0 + S.gkAnim * 1.0
        const dist = Math.hypot(S.ball.x - kp.x, S.ball.y - handsY)
        const caught = S.gkActive && dist < 0.55 * S.gkReach
        if (!inGoal) finish('МИМО', false)
        else if (caught) finish('СЕЙВ', false)
        else finish('⚽ ГОЛ!', true)
        return
      }
      if (S.ball.z < GOAL_Z - 3 || S.t > 4) finish('МИМО', false)
    } else if (ph === 'done') {
      if (S.gkActive) { S.gkAnim = Math.min(1, S.gkAnim + dt / 0.7); animateKeeper(S) }
    }
  }

  const finish = (m: string, goal: boolean) => {
    const S = st.current
    S.phase = 'done'; setPhase('done'); setMsg(m)
    bump('shots'); if (goal) { bump('goals'); sndGoal() } else if (m === 'СЕЙВ') sndSave(); else sndMiss()
  }

  const kick = () => {
    const S = st.current
    if (S.phase !== 'aim' || S.power < 5) return
    S.charging = false; setCharging(false)
    S.vel = launchVel(S.power); S.t = 0; S.phase = 'fly'; setPhase('fly')
    S.gkActive = false; S.gkAnim = 0
    S.gkReach = 1.4 + Math.random() * 0.7; S.gkLag = 0.6 + Math.random() * 0.6
    sndKick()
  }

  const reset = () => {
    const S = st.current
    S.phase = 'aim'; setPhase('aim'); setMsg('')
    S.power = 0; setPower(0); S.charging = false; setCharging(false)
    S.ball.set(0, 0.11, 0); S.gkActive = false; S.gkAnim = 0
    if (S.keeper) { S.keeper.group.position.set(0, 0, GOAL_Z + 0.6); resetKeeperPose(S.keeper) }
  }

  // keyboard
  useEffect(() => {
    const norm = (k: string) => (k === 'ф' || k === 'Ф') ? 'a' : (k === 'в' || k === 'В') ? 'd' : k.toLowerCase()
    const down = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName; if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight', ' ', 'a', 'A', 'd', 'D', 'ф', 'Ф', 'в', 'В'].includes(e.key)) return
      e.preventDefault()
      const S = st.current
      if (S.phase === 'done') { if (e.key === ' ') reset(); return }
      if (S.phase !== 'aim') return
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      S.keys[nk] = true
      if (e.key === ' ' && !S.charging) { S.power = 0; setPower(0); S.charging = true; setCharging(true) }
    }
    const up = (e: KeyboardEvent) => {
      const S = st.current
      const nk = e.key.startsWith('Arrow') ? e.key : norm(e.key)
      S.keys[nk] = false
      if (e.key === ' ' && S.charging && S.phase === 'aim') kick()
    }
    window.addEventListener('keydown', down); window.addEventListener('keyup', up)
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up) }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const acc = stats.shots ? Math.round((stats.goals / stats.shots) * 100) : 0

  if (failed) return (
    <div className="w-full text-center text-[12px] text-[#777] py-10">
      3D-режим недоступен в этом окружении
      <div className="text-[9px] text-[#444] mt-1">{failed}</div>
    </div>
  )

  return (
    <div ref={wrapRef} className="w-full" onClick={e => e.stopPropagation()}>
      <canvas ref={canvasRef} style={{ width: '100%', height: VIEW_H, display: 'block', borderRadius: 6, border: '1px solid #252525' }} />
      <div className="flex items-center gap-3 text-[11px] font-mono text-[#999] mt-1 px-1">
        <span className={charging ? 'text-[#5cc8ff]' : ''}>СИЛА {Math.round(power)}</span>
        <span className={spin !== 0 ? 'text-[#ff9f5c]' : ''}>КРУЧ {spin > 0 ? '↻' : spin < 0 ? '↺' : ''}{Math.abs(spin)}</span>
        <span className="flex-1 text-right">{msg || (phase === 'fly' ? '…' : '3D · целься и бей')}</span>
      </div>
      <div className="flex items-center justify-between text-[9px] text-[#383838] mt-0.5 px-1">
        <span>← → ↑ ↓ точка · A/D кручёный · пробел (держать) — сила/удар{msg ? ' · пробел — ещё' : ''}</span>
        <span>голы {stats.goals}/{stats.shots}{stats.shots ? ` · ${acc}%` : ''}</span>
      </div>
    </div>
  )
}

// ── keeper procedural animation ─────────────────────────────────────────────
function resetKeeperPose(k: ReturnType<typeof buildKeeper>) {
  k.group.rotation.z = 0
  k.armL.rotation.z = 0; k.armR.rotation.z = 0
  k.legL.rotation.x = 0; k.legR.rotation.x = 0
  k.armL.position.set(-0.42, 1.3, 0); k.armR.position.set(0.42, 1.3, 0)
  k.gloveL.position.set(-0.42, 1.0, 0); k.gloveR.position.set(0.42, 1.0, 0)
  k.group.position.y = 0
}
function animateKeeper(S: any) {
  const k = S.keeper as ReturnType<typeof buildKeeper>; if (!k) return
  const p = S.gkAnim as number, dive = S.gkDive as number
  // phases: crouch (0-0.18) → push (0.18-0.45) → flight stretch (0.45-0.8) → land (0.8-1)
  const reach = 2.2 * S.gkReach * 0.5
  const easeOut = 1 - (1 - p) * (1 - p)
  const jumpArc = Math.sin(Math.min(1, p) * Math.PI) // up then down
  // root slides toward dive and rises
  k.group.position.x = dive * reach * easeOut
  k.group.position.y = jumpArc * 0.7
  k.group.position.z = GOAL_Z + 0.6
  // body lean into dive
  k.group.rotation.z = -dive * Math.min(1, p / 0.5) * 1.0
  // crouch then extend legs
  const crouch = p < 0.18 ? p / 0.18 : 1
  k.legL.rotation.x = -0.5 * crouch * (1 - jumpArc * 0.6)
  k.legR.rotation.x = -0.5 * crouch * (1 - jumpArc * 0.6)
  // arms reach toward the ball side (the dive direction), fully extended in flight
  const stretch = Math.min(1, Math.max(0, (p - 0.2) / 0.4))
  k.armL.rotation.z = dive < 0 ? -1.7 * stretch : -0.3 * stretch
  k.armR.rotation.z = dive > 0 ? 1.7 * stretch : 0.3 * stretch
  // move gloves with arm rotation (approx by offset)
  const ext = 0.55 * stretch
  k.armL.position.set(-0.42 - (dive < 0 ? ext : 0), 1.3 + stretch * 0.2, 0)
  k.armR.position.set(0.42 + (dive > 0 ? ext : 0), 1.3 + stretch * 0.2, 0)
  k.gloveL.position.set(k.armL.position.x - (dive < 0 ? 0.2 : 0), 1.0 + stretch * 0.5 + (dive < 0 ? 0.4 : 0), 0)
  k.gloveR.position.set(k.armR.position.x + (dive > 0 ? 0.2 : 0), 1.0 + stretch * 0.5 + (dive > 0 ? 0.4 : 0), 0)
}
