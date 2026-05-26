let audioCtx: AudioContext | null = null

function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  return audioCtx
}

// Returns a safe scheduled time: adds 100ms buffer when context isn't running yet
function st(ctx: AudioContext, t: number): number {
  return ctx.state !== 'running' ? Math.max(t, ctx.currentTime + 0.1) : t
}

function beep(freq: number, duration: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number) {
  const s = st(ctx, t)
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(freq, 1), s)
  gain.gain.setValueAtTime(Math.max(vol, 0.001), s)
  gain.gain.exponentialRampToValueAtTime(0.001, s + duration)
  osc.start(s); osc.stop(s + duration + 0.01)
}

function sweep(f0: number, f1: number, dur: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number) {
  const s = st(ctx, t)
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain); gain.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(f0, 1), s)
  osc.frequency.exponentialRampToValueAtTime(Math.max(f1, 1), s + dur)
  gain.gain.setValueAtTime(Math.max(vol, 0.001), s)
  gain.gain.exponentialRampToValueAtTime(0.001, s + dur)
  osc.start(s); osc.stop(s + dur + 0.01)
}

// ── Long sound helpers (>= 2.5s) for 45-minute sounds ────────────────────

function lngNote(f: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number, dur = 2.5) {
  const s = st(ctx, t)
  const osc = ctx.createOscillator(), g = ctx.createGain()
  osc.connect(g); g.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(f, 1), s)
  g.gain.setValueAtTime(0.001, s)
  g.gain.linearRampToValueAtTime(vol, s + 0.05)
  g.gain.setValueAtTime(vol * 0.85, s + dur - 0.3)
  g.gain.exponentialRampToValueAtTime(0.001, s + dur)
  osc.start(s); osc.stop(s + dur + 0.05)
}

function lngSweep(f0: number, f1: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number, dur = 2.5) {
  const s = st(ctx, t)
  const osc = ctx.createOscillator(), g = ctx.createGain()
  osc.connect(g); g.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(f0, 1), s)
  osc.frequency.exponentialRampToValueAtTime(Math.max(f1, 1), s + dur - 0.3)
  g.gain.setValueAtTime(0.001, s)
  g.gain.linearRampToValueAtTime(vol, s + 0.05)
  g.gain.setValueAtTime(vol * 0.8, s + dur - 0.3)
  g.gain.exponentialRampToValueAtTime(0.001, s + dur)
  osc.start(s); osc.stop(s + dur + 0.05)
}

// Spreads notes across 2s, last note sustained to fill 2.5s total
function lngMel(freqs: number[], type: OscillatorType, vol: number, ctx: AudioContext) {
  const t = st(ctx, ctx.currentTime), n = freqs.length, step = 2.0 / n
  freqs.forEach((f, i) => {
    const nt = t + i * step, isLast = i === n - 1
    const dur = isLast ? Math.max(2.5 - i * step, 0.4) : step * 1.2
    const osc = ctx.createOscillator(), g = ctx.createGain()
    osc.connect(g); g.connect(ctx.destination)
    osc.type = type
    osc.frequency.setValueAtTime(Math.max(f, 1), nt)
    g.gain.setValueAtTime(0.001, nt)
    g.gain.linearRampToValueAtTime(vol, nt + 0.05)
    g.gain.setValueAtTime(vol * 0.85, nt + Math.max(dur - 0.3, 0.05))
    g.gain.exponentialRampToValueAtTime(0.001, nt + dur)
    osc.start(nt); osc.stop(nt + dur + 0.05)
  })
}

function lngChord(freqs: number[], type: OscillatorType, vol: number, ctx: AudioContext) {
  const t = st(ctx, ctx.currentTime), perVol = (vol / freqs.length) * 1.5
  freqs.forEach(f => lngNote(f, type, perVol, ctx, t))
}

export interface TimerSound {
  id: number
  name: string
  play: (ctx: AudioContext, vol: number) => void
  playLong: (ctx: AudioContext, vol: number) => void
}

export const TIMER_SOUNDS: TimerSound[] = [
  // ── Одиночные сигналы ──────────────────────────────────────────────
  { id: 1, name: 'Пиксель',
    play: (ctx, vol) => beep(880, 0.08, 'square', vol * 0.5, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngNote(880, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 2, name: 'Коин',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(988, 0.08, 'square', vol * 0.6, ctx, t); beep(1319, 0.15, 'square', vol * 0.6, ctx, t + 0.08) },
    playLong: (ctx, vol) => lngMel([988, 1319], 'square', vol * 0.6, ctx) },
  { id: 3, name: 'Двойной',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(880, 0.08, 'square', vol * 0.5, ctx, t); beep(880, 0.08, 'square', vol * 0.5, ctx, t + 0.14) },
    playLong: (ctx, vol) => lngNote(880, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 4, name: 'Тик',
    play: (ctx, vol) => beep(1200, 0.04, 'square', vol * 0.4, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngNote(1200, 'square', vol * 0.4, ctx, ctx.currentTime) },
  { id: 5, name: 'Пинг',
    play: (ctx, vol) => beep(1000, 0.3, 'sine', vol * 0.5, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngNote(1000, 'sine', vol * 0.5, ctx, ctx.currentTime) },
  { id: 6, name: 'Клик',
    play: (ctx, vol) => beep(1400, 0.05, 'square', vol * 0.4, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngNote(1400, 'square', vol * 0.4, ctx, ctx.currentTime) },
  { id: 7, name: 'Поп',
    play: (ctx, vol) => sweep(400, 80, 0.1, 'square', vol * 0.5, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(400, 80, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 8, name: 'Свист',
    play: (ctx, vol) => beep(1760, 0.06, 'square', vol * 0.35, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngNote(1760, 'square', vol * 0.35, ctx, ctx.currentTime) },
  // ── Мелодии ───────────────────────────────────────────────────────
  { id: 9, name: '1-UP',
    play: (ctx, vol) => { const t = ctx.currentTime; [523, 659, 784, 1047].forEach((f, i) => beep(f, 0.1, 'square', vol * 0.55, ctx, t + i * 0.08)) },
    playLong: (ctx, vol) => lngMel([523, 659, 784, 1047], 'square', vol * 0.55, ctx) },
  { id: 10, name: 'Победа',
    play: (ctx, vol) => { const t = ctx.currentTime; [523, 659, 784, 1047, 1047, 784, 1047].forEach((f, i) => beep(f, 0.12, 'square', vol * 0.45, ctx, t + i * 0.1)) },
    playLong: (ctx, vol) => lngMel([523, 659, 784, 1047, 1047, 784, 1047], 'square', vol * 0.45, ctx) },
  { id: 11, name: 'Бонус',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(523, 0.12, 'triangle', vol * 0.5, ctx, t); beep(659, 0.12, 'triangle', vol * 0.5, ctx, t + 0.1); beep(784, 0.18, 'triangle', vol * 0.5, ctx, t + 0.2) },
    playLong: (ctx, vol) => lngMel([523, 659, 784], 'triangle', vol * 0.5, ctx) },
  { id: 12, name: 'Гамма',
    play: (ctx, vol) => { const t = ctx.currentTime; [261, 294, 330, 349, 392, 440, 494, 523].forEach((f, i) => beep(f, 0.09, 'square', vol * 0.45, ctx, t + i * 0.07)) },
    playLong: (ctx, vol) => lngMel([261, 294, 330, 349, 392, 440, 494, 523], 'square', vol * 0.45, ctx) },
  { id: 13, name: 'Звезда',
    play: (ctx, vol) => { const t = ctx.currentTime; [523, 659, 784, 880, 1047].forEach((f, i) => beep(f, 0.08, 'triangle', vol * 0.5, ctx, t + i * 0.06)) },
    playLong: (ctx, vol) => lngMel([523, 659, 784, 880, 1047], 'triangle', vol * 0.5, ctx) },
  { id: 14, name: 'Магия',
    play: (ctx, vol) => { const t = ctx.currentTime; [880, 1047, 784, 1047, 880, 659, 784].forEach((f, i) => beep(f, 0.07, 'triangle', vol * 0.45, ctx, t + i * 0.06)) },
    playLong: (ctx, vol) => lngMel([880, 1047, 784, 1047, 880, 659, 784], 'triangle', vol * 0.45, ctx) },
  { id: 15, name: 'Арфа',
    play: (ctx, vol) => { const t = ctx.currentTime; [261, 330, 392, 523, 659, 784, 1047].forEach((f, i) => beep(f, 0.14, 'triangle', vol * 0.4, ctx, t + i * 0.045)) },
    playLong: (ctx, vol) => lngMel([261, 330, 392, 523, 659, 784, 1047], 'triangle', vol * 0.4, ctx) },
  { id: 16, name: 'Флейта',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(784, 0.18, 'triangle', vol * 0.5, ctx, t); beep(880, 0.18, 'triangle', vol * 0.5, ctx, t + 0.18); beep(1047, 0.24, 'triangle', vol * 0.5, ctx, t + 0.36) },
    playLong: (ctx, vol) => lngMel([784, 880, 1047], 'triangle', vol * 0.5, ctx) },
  { id: 17, name: 'Жизнь',
    play: (ctx, vol) => { const t = ctx.currentTime; [659, 784, 1047, 1319, 1047, 784, 1047, 1319].forEach((f, i) => beep(f, 0.08, 'square', vol * 0.5, ctx, t + i * 0.07)) },
    playLong: (ctx, vol) => lngMel([659, 784, 1047, 1319, 1047, 784, 1047, 1319], 'square', vol * 0.5, ctx) },
  { id: 18, name: 'Гриб',
    play: (ctx, vol) => { const t = ctx.currentTime; [[330, 0], [392, 0.06], [523, 0.12], [659, 0.18]].forEach(([f, d]) => beep(f, 0.08, 'square', vol * 0.5, ctx, t + d)) },
    playLong: (ctx, vol) => lngMel([330, 392, 523, 659], 'square', vol * 0.5, ctx) },
  // ── Свипы ─────────────────────────────────────────────────────────
  { id: 19, name: 'Лазер',
    play: (ctx, vol) => sweep(1200, 120, 0.3, 'sawtooth', vol * 0.5, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(1200, 120, 'sawtooth', vol * 0.5, ctx, ctx.currentTime) },
  { id: 20, name: 'Пиу',
    play: (ctx, vol) => sweep(440, 1200, 0.12, 'square', vol * 0.5, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(440, 1200, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 21, name: 'Портал',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(300, 1200, 0.3, 'sine', vol * 0.5, ctx, t); sweep(1200, 300, 0.3, 'sine', vol * 0.4, ctx, t + 0.3) },
    playLong: (ctx, vol) => lngSweep(300, 1200, 'sine', vol * 0.5, ctx, ctx.currentTime) },
  { id: 22, name: 'Апгрейд',
    play: (ctx, vol) => sweep(200, 1200, 0.5, 'square', vol * 0.45, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(200, 1200, 'square', vol * 0.45, ctx, ctx.currentTime) },
  { id: 23, name: 'Нарастание',
    play: (ctx, vol) => {
      const t = st(ctx, ctx.currentTime)
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.setValueAtTime(300, t)
      osc.frequency.linearRampToValueAtTime(900, t + 1.2)
      gain.gain.setValueAtTime(0.001, t)
      gain.gain.linearRampToValueAtTime(vol * 0.7, t + 0.8)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 1.3)
      osc.start(t); osc.stop(t + 1.4)
    },
    playLong: (ctx, vol) => lngSweep(300, 900, 'sine', vol * 0.7, ctx, ctx.currentTime) },
  { id: 24, name: 'Телепорт',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 0.15, 0.3].forEach(d => sweep(600, 1800, 0.12, 'sawtooth', vol * 0.4, ctx, t + d)) },
    playLong: (ctx, vol) => lngSweep(600, 1800, 'sawtooth', vol * 0.4, ctx, ctx.currentTime) },
  { id: 25, name: 'Ракета',
    play: (ctx, vol) => sweep(200, 1600, 0.6, 'sawtooth', vol * 0.4, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(200, 1600, 'sawtooth', vol * 0.4, ctx, ctx.currentTime) },
  { id: 26, name: 'Молния',
    play: (ctx, vol) => sweep(2000, 80, 0.08, 'sawtooth', vol * 0.6, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(2000, 80, 'sawtooth', vol * 0.6, ctx, ctx.currentTime) },
  { id: 27, name: 'Взрыв',
    play: (ctx, vol) => sweep(400, 40, 0.4, 'sawtooth', vol * 0.6, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(400, 40, 'sawtooth', vol * 0.6, ctx, ctx.currentTime) },
  // ── Аккорды и гармоники ────────────────────────────────────────────
  { id: 28, name: 'Гонг',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(220, 2.0, 'sine', vol * 0.8, ctx, t); beep(440, 1.6, 'sine', vol * 0.3, ctx, t); beep(660, 1.2, 'sine', vol * 0.15, ctx, t) },
    playLong: (ctx, vol) => { const t = ctx.currentTime; lngNote(220, 'sine', vol * 0.8, ctx, t); lngNote(440, 'sine', vol * 0.35, ctx, t); lngNote(660, 'sine', vol * 0.18, ctx, t) } },
  { id: 29, name: 'Труба',
    play: (ctx, vol) => { const t = ctx.currentTime; [[392, 0], [523, 0.12], [659, 0.24]].forEach(([f, d]) => beep(f, 0.14, 'square', vol * 0.5, ctx, t + d)) },
    playLong: (ctx, vol) => lngMel([392, 523, 659], 'square', vol * 0.5, ctx) },
  { id: 30, name: 'Финал',
    play: (ctx, vol) => { const t = ctx.currentTime; [261, 329, 392].forEach(f => beep(f, 0.3, 'square', vol * 0.38, ctx, t)); beep(523, 0.7, 'square', vol * 0.45, ctx, t + 0.3) },
    playLong: (ctx, vol) => { lngChord([261, 329, 392], 'square', vol * 0.38, ctx); lngNote(523, 'square', vol * 0.45, ctx, ctx.currentTime + 0.5, 2.0) } },
  { id: 31, name: 'Аккорд',
    play: (ctx, vol) => { const t = ctx.currentTime; [262, 330, 392].forEach(f => beep(f, 0.6, 'triangle', vol * 0.38, ctx, t)) },
    playLong: (ctx, vol) => lngChord([262, 330, 392], 'triangle', vol * 0.4, ctx) },
  { id: 32, name: 'Щит',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(440, 0.1, 'sawtooth', vol * 0.5, ctx, t); beep(220, 0.25, 'sawtooth', vol * 0.4, ctx, t + 0.1) },
    playLong: (ctx, vol) => lngMel([440, 220], 'sawtooth', vol * 0.5, ctx) },
  { id: 33, name: 'Колокол',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(1046, 0.9, 'sine', vol * 0.5, ctx, t); beep(1318, 0.6, 'sine', vol * 0.3, ctx, t + 0.1) },
    playLong: (ctx, vol) => { const t = ctx.currentTime; lngNote(1046, 'sine', vol * 0.5, ctx, t); lngNote(1318, 'sine', vol * 0.3, ctx, t) } },
  { id: 34, name: 'Дрон',
    play: (ctx, vol) => { const t = ctx.currentTime; [110, 220, 330].forEach(f => beep(f, 0.5, 'sawtooth', vol * 0.25, ctx, t)) },
    playLong: (ctx, vol) => lngChord([110, 220, 330], 'sawtooth', vol * 0.35, ctx) },
  { id: 35, name: 'Удар',
    play: (ctx, vol) => sweep(240, 40, 0.18, 'square', vol * 0.7, ctx, ctx.currentTime),
    playLong: (ctx, vol) => lngSweep(240, 40, 'square', vol * 0.7, ctx, ctx.currentTime) },
  // ── Паттерны ──────────────────────────────────────────────────────
  { id: 36, name: 'Загрузка',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 1, 2, 3, 4].forEach(i => beep(440 + i * 110, 0.06, 'square', vol * 0.45, ctx, t + i * 0.09)) },
    playLong: (ctx, vol) => lngMel([440, 550, 660, 770, 880], 'square', vol * 0.45, ctx) },
  { id: 37, name: 'Тревога',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 1, 2, 3, 4, 5].forEach(i => beep(i % 2 === 0 ? 880 : 1047, 0.08, 'square', vol * 0.5, ctx, t + i * 0.1)) },
    playLong: (ctx, vol) => lngMel([880, 1047, 880, 1047, 880, 1047], 'square', vol * 0.5, ctx) },
  { id: 38, name: 'Марш',
    play: (ctx, vol) => { const t = ctx.currentTime; [523, 0, 523, 0, 659, 0, 784, 784].forEach((f, i) => { if (f > 0) beep(f, 0.08, 'square', vol * 0.45, ctx, t + i * 0.1) }) },
    playLong: (ctx, vol) => lngMel([523, 523, 659, 784, 784], 'square', vol * 0.45, ctx) },
  { id: 39, name: 'Спринт',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 1, 2, 3, 4, 5, 6, 7].forEach(i => beep(440 + i * 80, 0.04, 'square', vol * 0.4, ctx, t + i * 0.04)) },
    playLong: (ctx, vol) => lngMel([440, 520, 600, 680, 760, 840, 920, 1000], 'square', vol * 0.4, ctx) },
  { id: 40, name: 'Звонок',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 0.15, 0.42, 0.57].forEach((d, i) => beep(i % 2 === 0 ? 880 : 1100, 0.12, 'square', vol * 0.4, ctx, t + d)) },
    playLong: (ctx, vol) => lngMel([880, 1100, 880, 1100], 'square', vol * 0.4, ctx) },
  { id: 41, name: 'Радар',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(800, 0.06, 'sine', vol * 0.6, ctx, t); beep(800, 0.06, 'sine', vol * 0.3, ctx, t + 0.5) },
    playLong: (ctx, vol) => lngNote(800, 'sine', vol * 0.6, ctx, ctx.currentTime) },
  { id: 42, name: 'Пиу-пиу',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(1200, 200, 0.15, 'sawtooth', vol * 0.45, ctx, t); sweep(1200, 200, 0.15, 'sawtooth', vol * 0.45, ctx, t + 0.22) },
    playLong: (ctx, vol) => lngSweep(1200, 200, 'sawtooth', vol * 0.45, ctx, ctx.currentTime) },
  { id: 43, name: 'Обратный',
    play: (ctx, vol) => { const t = ctx.currentTime; [0, 1, 2, 3, 4].forEach(i => beep(Math.round(880 * Math.pow(0.82, i)), 0.09, 'square', vol * 0.5, ctx, t + i * 0.12)) },
    playLong: (ctx, vol) => lngMel([880, 722, 592, 485, 399], 'square', vol * 0.5, ctx) },
  { id: 44, name: 'Вибрато',
    play: (ctx, vol) => {
      const t = st(ctx, ctx.currentTime)
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      const lfo = ctx.createOscillator(); const lfoGain = ctx.createGain()
      lfo.connect(lfoGain); lfoGain.connect(osc.frequency)
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'square'; osc.frequency.setValueAtTime(660, t)
      lfo.frequency.setValueAtTime(8, t); lfoGain.gain.setValueAtTime(40, t)
      gain.gain.setValueAtTime(vol * 0.5, t)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.7)
      lfo.start(t); osc.start(t); lfo.stop(t + 0.75); osc.stop(t + 0.75)
    },
    playLong: (ctx, vol) => {
      const t = st(ctx, ctx.currentTime)
      const osc = ctx.createOscillator(), gain = ctx.createGain()
      const lfo = ctx.createOscillator(), lfoGain = ctx.createGain()
      lfo.connect(lfoGain); lfoGain.connect(osc.frequency)
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'square'; osc.frequency.setValueAtTime(660, t)
      lfo.frequency.setValueAtTime(8, t); lfoGain.gain.setValueAtTime(40, t)
      gain.gain.setValueAtTime(0.001, t)
      gain.gain.linearRampToValueAtTime(vol * 0.5, t + 0.05)
      gain.gain.setValueAtTime(vol * 0.5, t + 2.2)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 2.5)
      lfo.start(t); osc.start(t); lfo.stop(t + 2.55); osc.stop(t + 2.55)
    } },
  { id: 45, name: 'Пространство',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(1200, 80, 1.2, 'sine', vol * 0.4, ctx, t); beep(600, 0.6, 'sine', vol * 0.15, ctx, t + 0.3) },
    playLong: (ctx, vol) => { const t = ctx.currentTime; lngSweep(1200, 80, 'sine', vol * 0.4, ctx, t); lngNote(600, 'sine', vol * 0.15, ctx, t) } },
]

const ACTION_SOUNDS: Record<string, (ctx: AudioContext, vol: number) => void> = {
  done: (ctx, vol) => {
    const t = ctx.currentTime
    beep(440, 0.1, 'sine', vol * 0.5, ctx, t)
    beep(660, 0.15, 'sine', vol * 0.5, ctx, t + 0.1)
    beep(880, 0.2, 'sine', vol * 0.5, ctx, t + 0.22)
  },
  start: (ctx, vol) => beep(660, 0.1, 'sine', vol * 0.4, ctx, ctx.currentTime),
  pause: (ctx, vol) => beep(440, 0.1, 'sine', vol * 0.3, ctx, ctx.currentTime),
  new_task: (ctx, vol) => beep(880, 0.08, 'sine', vol * 0.3, ctx, ctx.currentTime),
  take_now: (ctx, vol) => {
    const t = ctx.currentTime
    ;[523, 659, 784, 1047].forEach((f, i) => beep(f, 0.1, 'square', vol * 0.55, ctx, t + i * 0.08))
  },
  checkin_open: (ctx, vol) => {
    const t = ctx.currentTime
    beep(523, 0.08, 'sine', vol * 0.3, ctx, t)
    beep(659, 0.1, 'sine', vol * 0.3, ctx, t + 0.1)
  },
  checkin_save: (ctx, vol) => {
    const t = ctx.currentTime
    ;[523, 659, 784, 1047, 1047, 784, 1047].forEach((f, i) =>
      beep(f, 0.12, 'square', vol * 0.45, ctx, t + i * 0.1))
  },
  thought_saved: (ctx, vol) => beep(880, 0.1, 'sine', vol * 0.35, ctx, ctx.currentTime),
  task_delete: (ctx, vol) => beep(220, 0.2, 'sine', vol * 0.3, ctx, ctx.currentTime),
  fanfare: (ctx, vol) => {
    const t = ctx.currentTime
    const melody: [number, number][] = [
      [523, 0], [659, 0.14], [784, 0.28], [1047, 0.42],
      [1047, 0.62], [784, 0.76], [1047, 0.90], [1319, 1.1],
      [1568, 1.35], [2093, 1.65],
    ]
    melody.forEach(([f, d]) => beep(f, 0.2, 'square', vol * 0.7, ctx, t + d))
    ;[[131, 0], [131, 0.42], [131, 0.9], [131, 1.65]].forEach(([f, d]) => beep(f, 0.35, 'square', vol * 0.5, ctx, t + d))
    ;[[659, 0], [784, 0.42], [1047, 0.9], [1319, 1.65]].forEach(([f, d]) => beep(f, 0.2, 'square', vol * 0.4, ctx, t + d))
  },
}

function getVolume(): number {
  try {
    const v = localStorage.getItem('sounds_volume')
    return v ? parseFloat(v) : 0.5
  } catch {
    return 0.5
  }
}

function isSoundEnabled(): boolean {
  try {
    return localStorage.getItem('sounds_enabled') !== 'false'
  } catch {
    return true
  }
}

export function getTimer5mSoundId(): number {
  try {
    const v = localStorage.getItem('timer_sound_5m')
    return v ? parseInt(v, 10) : 1
  } catch {
    return 1
  }
}

export function getTimer45mSoundId(): number {
  try {
    const v = localStorage.getItem('timer_sound_45m')
    return v ? parseInt(v, 10) : 10
  } catch {
    return 10
  }
}

export function previewTimerSound(id: number, long = false): void {
  const sound = TIMER_SOUNDS.find(s => s.id === id)
  if (!sound) return
  const vol = getVolume()
  try {
    if (long) sound.playLong(getCtx(), vol)
    else sound.play(getCtx(), vol)
  } catch (e) {
    console.warn('previewTimerSound error', e)
  }
}

export function playTimer5mSound(): void {
  if (!isSoundEnabled()) return
  const id = getTimer5mSoundId()
  const sound = TIMER_SOUNDS.find(s => s.id === id) ?? TIMER_SOUNDS[0]
  const vol = getVolume()
  try {
    sound.play(getCtx(), vol)
  } catch (e) {
    console.warn('playTimer5mSound error', e)
  }
}

export function playTimer45mSound(): void {
  if (!isSoundEnabled()) return
  const id = getTimer45mSoundId()
  const sound = TIMER_SOUNDS.find(s => s.id === id) ?? TIMER_SOUNDS[9]
  const vol = getVolume()
  try {
    sound.playLong(getCtx(), vol)
  } catch (e) {
    console.warn('playTimer45mSound error', e)
  }
}

// Keep for backward compat with any remaining callers
export function getTimerSoundId(): number { return getTimer5mSoundId() }
export function playTimerSound(): void { playTimer5mSound() }

export function playSound(name: string, volume?: number): void {
  if (!isSoundEnabled()) return
  const vol = volume ?? getVolume()
  try {
    const fn = ACTION_SOUNDS[name]
    if (fn) fn(getCtx(), vol)
  } catch (e) {
    console.warn('playSound error', e)
  }
}
