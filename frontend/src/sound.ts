let audioCtx: AudioContext | null = null

function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  }
  return audioCtx
}

function beep(freq: number, duration: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(freq, 1), t)
  gain.gain.setValueAtTime(Math.max(vol, 0.001), t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + duration)
  osc.start(t)
  osc.stop(t + duration + 0.01)
}

function sweep(f0: number, f1: number, dur: number, type: OscillatorType, vol: number, ctx: AudioContext, t: number) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(Math.max(f0, 1), t)
  osc.frequency.exponentialRampToValueAtTime(Math.max(f1, 1), t + dur)
  gain.gain.setValueAtTime(Math.max(vol, 0.001), t)
  gain.gain.exponentialRampToValueAtTime(0.001, t + dur)
  osc.start(t)
  osc.stop(t + dur + 0.01)
}

export interface TimerSound {
  id: number
  name: string
  play: (ctx: AudioContext, vol: number) => void
}

export const TIMER_SOUNDS: TimerSound[] = [
  // ── Одиночные сигналы ──────────────────────────────────────────────
  { id: 1,  name: 'Пиксель',
    play: (ctx, vol) => beep(880, 0.08, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 2,  name: 'Коин',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(988, 0.08, 'square', vol * 0.6, ctx, t); beep(1319, 0.15, 'square', vol * 0.6, ctx, t + 0.08) } },
  { id: 3,  name: 'Двойной',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(880, 0.08, 'square', vol * 0.5, ctx, t); beep(880, 0.08, 'square', vol * 0.5, ctx, t + 0.14) } },
  { id: 4,  name: 'Тик',
    play: (ctx, vol) => beep(1200, 0.04, 'square', vol * 0.4, ctx, ctx.currentTime) },
  { id: 5,  name: 'Пинг',
    play: (ctx, vol) => beep(1000, 0.3, 'sine', vol * 0.5, ctx, ctx.currentTime) },
  { id: 6,  name: 'Клик',
    play: (ctx, vol) => beep(1400, 0.05, 'square', vol * 0.4, ctx, ctx.currentTime) },
  { id: 7,  name: 'Поп',
    play: (ctx, vol) => sweep(400, 80, 0.1, 'square', vol * 0.5, ctx, ctx.currentTime) },
  { id: 8,  name: 'Свист',
    play: (ctx, vol) => beep(1760, 0.06, 'square', vol * 0.35, ctx, ctx.currentTime) },
  // ── Мелодии ───────────────────────────────────────────────────────
  { id: 9,  name: '1-UP',
    play: (ctx, vol) => { const t = ctx.currentTime; [523,659,784,1047].forEach((f,i) => beep(f, 0.1, 'square', vol*0.55, ctx, t+i*0.08)) } },
  { id: 10, name: 'Победа',
    play: (ctx, vol) => { const t = ctx.currentTime; [523,659,784,1047,1047,784,1047].forEach((f,i) => beep(f, 0.12, 'square', vol*0.45, ctx, t+i*0.1)) } },
  { id: 11, name: 'Бонус',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(523,0.12,'triangle',vol*0.5,ctx,t); beep(659,0.12,'triangle',vol*0.5,ctx,t+0.1); beep(784,0.18,'triangle',vol*0.5,ctx,t+0.2) } },
  { id: 12, name: 'Гамма',
    play: (ctx, vol) => { const t = ctx.currentTime; [261,294,330,349,392,440,494,523].forEach((f,i) => beep(f,0.09,'square',vol*0.45,ctx,t+i*0.07)) } },
  { id: 13, name: 'Звезда',
    play: (ctx, vol) => { const t = ctx.currentTime; [523,659,784,880,1047].forEach((f,i) => beep(f,0.08,'triangle',vol*0.5,ctx,t+i*0.06)) } },
  { id: 14, name: 'Магия',
    play: (ctx, vol) => { const t = ctx.currentTime; [880,1047,784,1047,880,659,784].forEach((f,i) => beep(f,0.07,'triangle',vol*0.45,ctx,t+i*0.06)) } },
  { id: 15, name: 'Арфа',
    play: (ctx, vol) => { const t = ctx.currentTime; [261,330,392,523,659,784,1047].forEach((f,i) => beep(f,0.14,'triangle',vol*0.4,ctx,t+i*0.045)) } },
  { id: 16, name: 'Флейта',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(784,0.18,'triangle',vol*0.5,ctx,t); beep(880,0.18,'triangle',vol*0.5,ctx,t+0.18); beep(1047,0.24,'triangle',vol*0.5,ctx,t+0.36) } },
  { id: 17, name: 'Жизнь',
    play: (ctx, vol) => { const t = ctx.currentTime; [659,784,1047,1319,1047,784,1047,1319].forEach((f,i) => beep(f,0.08,'square',vol*0.5,ctx,t+i*0.07)) } },
  { id: 18, name: 'Гриб',
    play: (ctx, vol) => { const t = ctx.currentTime; [[330,0],[392,0.06],[523,0.12],[659,0.18]].forEach(([f,d]) => beep(f,0.08,'square',vol*0.5,ctx,t+d)) } },
  // ── Свипы ─────────────────────────────────────────────────────────
  { id: 19, name: 'Лазер',
    play: (ctx, vol) => sweep(1200, 120, 0.3, 'sawtooth', vol*0.5, ctx, ctx.currentTime) },
  { id: 20, name: 'Пиу',
    play: (ctx, vol) => sweep(440, 1200, 0.12, 'square', vol*0.5, ctx, ctx.currentTime) },
  { id: 21, name: 'Портал',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(300,1200,0.3,'sine',vol*0.5,ctx,t); sweep(1200,300,0.3,'sine',vol*0.4,ctx,t+0.3) } },
  { id: 22, name: 'Апгрейд',
    play: (ctx, vol) => sweep(200, 1200, 0.5, 'square', vol*0.45, ctx, ctx.currentTime) },
  { id: 23, name: 'Нарастание',
    play: (ctx, vol) => {
      const t = ctx.currentTime
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'sine'
      osc.frequency.setValueAtTime(300, t)
      osc.frequency.linearRampToValueAtTime(900, t + 1.2)
      gain.gain.setValueAtTime(0.001, t)
      gain.gain.linearRampToValueAtTime(vol * 0.7, t + 0.8)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 1.3)
      osc.start(t); osc.stop(t + 1.4)
    } },
  { id: 24, name: 'Телепорт',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,0.15,0.3].forEach(d => sweep(600,1800,0.12,'sawtooth',vol*0.4,ctx,t+d)) } },
  { id: 25, name: 'Ракета',
    play: (ctx, vol) => sweep(200, 1600, 0.6, 'sawtooth', vol*0.4, ctx, ctx.currentTime) },
  { id: 26, name: 'Молния',
    play: (ctx, vol) => sweep(2000, 80, 0.08, 'sawtooth', vol*0.6, ctx, ctx.currentTime) },
  { id: 27, name: 'Взрыв',
    play: (ctx, vol) => sweep(400, 40, 0.4, 'sawtooth', vol*0.6, ctx, ctx.currentTime) },
  // ── Аккорды и гармоники ────────────────────────────────────────────
  { id: 28, name: 'Гонг',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(220,2.0,'sine',vol*0.8,ctx,t); beep(440,1.6,'sine',vol*0.3,ctx,t); beep(660,1.2,'sine',vol*0.15,ctx,t) } },
  { id: 29, name: 'Труба',
    play: (ctx, vol) => { const t = ctx.currentTime; [[392,0],[523,0.12],[659,0.24]].forEach(([f,d]) => beep(f,0.14,'square',vol*0.5,ctx,t+d)) } },
  { id: 30, name: 'Финал',
    play: (ctx, vol) => { const t = ctx.currentTime; [261,329,392].forEach(f => beep(f,0.3,'square',vol*0.38,ctx,t)); beep(523,0.7,'square',vol*0.45,ctx,t+0.3) } },
  { id: 31, name: 'Аккорд',
    play: (ctx, vol) => { const t = ctx.currentTime; [262,330,392].forEach(f => beep(f,0.6,'triangle',vol*0.38,ctx,t)) } },
  { id: 32, name: 'Щит',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(440,0.1,'sawtooth',vol*0.5,ctx,t); beep(220,0.25,'sawtooth',vol*0.4,ctx,t+0.1) } },
  { id: 33, name: 'Колокол',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(1046,0.9,'sine',vol*0.5,ctx,t); beep(1318,0.6,'sine',vol*0.3,ctx,t+0.1) } },
  { id: 34, name: 'Дрон',
    play: (ctx, vol) => { const t = ctx.currentTime; [110,220,330].forEach(f => beep(f,0.5,'sawtooth',vol*0.25,ctx,t)) } },
  { id: 35, name: 'Удар',
    play: (ctx, vol) => sweep(240, 40, 0.18, 'square', vol*0.7, ctx, ctx.currentTime) },
  // ── Паттерны ──────────────────────────────────────────────────────
  { id: 36, name: 'Загрузка',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,1,2,3,4].forEach(i => beep(440+i*110,0.06,'square',vol*0.45,ctx,t+i*0.09)) } },
  { id: 37, name: 'Тревога',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,1,2,3,4,5].forEach(i => beep(i%2===0?880:1047,0.08,'square',vol*0.5,ctx,t+i*0.1)) } },
  { id: 38, name: 'Марш',
    play: (ctx, vol) => { const t = ctx.currentTime; [523,0,523,0,659,0,784,784].forEach((f,i) => { if(f>0) beep(f,0.08,'square',vol*0.45,ctx,t+i*0.1) }) } },
  { id: 39, name: 'Спринт',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,1,2,3,4,5,6,7].forEach(i => beep(440+i*80,0.04,'square',vol*0.4,ctx,t+i*0.04)) } },
  { id: 40, name: 'Звонок',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,0.15,0.42,0.57].forEach((d,i) => beep(i%2===0?880:1100,0.12,'square',vol*0.4,ctx,t+d)) } },
  { id: 41, name: 'Радар',
    play: (ctx, vol) => { const t = ctx.currentTime; beep(800,0.06,'sine',vol*0.6,ctx,t); beep(800,0.06,'sine',vol*0.3,ctx,t+0.5) } },
  { id: 42, name: 'Пиу-пиу',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(1200,200,0.15,'sawtooth',vol*0.45,ctx,t); sweep(1200,200,0.15,'sawtooth',vol*0.45,ctx,t+0.22) } },
  { id: 43, name: 'Обратный',
    play: (ctx, vol) => { const t = ctx.currentTime; [0,1,2,3,4].forEach(i => beep(Math.round(880*Math.pow(0.82,i)),0.09,'square',vol*0.5,ctx,t+i*0.12)) } },
  { id: 44, name: 'Вибрато',
    play: (ctx, vol) => {
      const t = ctx.currentTime
      const osc = ctx.createOscillator(); const gain = ctx.createGain()
      const lfo = ctx.createOscillator(); const lfoGain = ctx.createGain()
      lfo.connect(lfoGain); lfoGain.connect(osc.frequency)
      osc.connect(gain); gain.connect(ctx.destination)
      osc.type = 'square'
      osc.frequency.setValueAtTime(660, t)
      lfo.frequency.setValueAtTime(8, t)
      lfoGain.gain.setValueAtTime(40, t)
      gain.gain.setValueAtTime(vol * 0.5, t)
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.7)
      lfo.start(t); osc.start(t); lfo.stop(t + 0.75); osc.stop(t + 0.75)
    } },
  { id: 45, name: 'Пространство',
    play: (ctx, vol) => { const t = ctx.currentTime; sweep(1200,80,1.2,'sine',vol*0.4,ctx,t); beep(600,0.6,'sine',vol*0.15,ctx,t+0.3) } },
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
    // 16-bit victory fanfare, ~2.5 seconds
    const melody: [number, number][] = [
      [523, 0], [659, 0.14], [784, 0.28], [1047, 0.42],
      [1047, 0.62], [784, 0.76], [1047, 0.90], [1319, 1.1],
      [1568, 1.35], [2093, 1.65],
    ]
    melody.forEach(([f, d]) => beep(f, 0.2, 'square', vol * 0.7, ctx, t + d))
    // bass counterpoint
    ;[[131,0],[131,0.42],[131,0.9],[131,1.65]].forEach(([f,d]) => beep(f,0.35,'square',vol*0.5,ctx,t+d))
    // harmony
    ;[[659,0],[784,0.42],[1047,0.9],[1319,1.65]].forEach(([f,d]) => beep(f,0.2,'square',vol*0.4,ctx,t+d))
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

export function getTimerSoundId(): number {
  try {
    const v = localStorage.getItem('timer_sound_id')
    return v ? parseInt(v, 10) : 1
  } catch {
    return 1
  }
}

export function previewTimerSound(id: number): void {
  const sound = TIMER_SOUNDS.find(s => s.id === id)
  if (!sound) return
  const vol = getVolume()
  try {
    sound.play(getCtx(), vol)
  } catch (e) {
    console.warn('previewTimerSound error', e)
  }
}

export function playTimerSound(): void {
  if (!isSoundEnabled()) return
  const id = getTimerSoundId()
  const sound = TIMER_SOUNDS.find(s => s.id === id) ?? TIMER_SOUNDS[0]
  const vol = getVolume()
  try {
    sound.play(getCtx(), vol)
  } catch (e) {
    console.warn('playTimerSound error', e)
  }
}

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
