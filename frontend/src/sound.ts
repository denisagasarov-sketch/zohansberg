let audioCtx: AudioContext | null = null

function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  }
  return audioCtx
}

function beep(freq: number, duration: number, type: OscillatorType, vol: number, ctx: AudioContext, startAt: number) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.type = type
  osc.frequency.setValueAtTime(freq, startAt)
  gain.gain.setValueAtTime(vol, startAt)
  gain.gain.exponentialRampToValueAtTime(0.001, startAt + duration)
  osc.start(startAt)
  osc.stop(startAt + duration)
}

const SOUNDS: Record<string, (ctx: AudioContext, vol: number) => void> = {
  бип: (ctx, vol) => {
    beep(880, 0.15, 'sine', vol, ctx, ctx.currentTime)
  },
  пипипипи: (ctx, vol) => {
    const t = ctx.currentTime
    for (let i = 0; i < 4; i++) beep(1200, 0.1, 'square', vol * 0.7, ctx, t + i * 0.12)
  },
  гонг: (ctx, vol) => {
    const t = ctx.currentTime
    beep(220, 1.8, 'sine', vol, ctx, t)
    beep(440, 1.4, 'sine', vol * 0.4, ctx, t)
  },
  нарастающий: (ctx, vol) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    const t = ctx.currentTime
    osc.frequency.setValueAtTime(300, t)
    osc.frequency.linearRampToValueAtTime(900, t + 1.2)
    gain.gain.setValueAtTime(0.001, t)
    gain.gain.linearRampToValueAtTime(vol, t + 0.8)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 1.3)
    osc.start(t)
    osc.stop(t + 1.4)
  },
  '1up': (ctx, vol) => {
    const notes = [523, 659, 784, 1047]
    const t = ctx.currentTime
    notes.forEach((f, i) => beep(f, 0.1, 'square', vol * 0.6, ctx, t + i * 0.08))
  },
  победа: (ctx, vol) => {
    const notes = [523, 659, 784, 1047, 1047, 784, 1047]
    const t = ctx.currentTime
    notes.forEach((f, i) => beep(f, 0.12, 'square', vol * 0.5, ctx, t + i * 0.1))
  },
  laser: (ctx, vol) => {
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sawtooth'
    const t = ctx.currentTime
    osc.frequency.setValueAtTime(1200, t)
    osc.frequency.exponentialRampToValueAtTime(200, t + 0.3)
    gain.gain.setValueAtTime(vol, t)
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35)
    osc.start(t)
    osc.stop(t + 0.4)
  },
  coin: (ctx, vol) => {
    const t = ctx.currentTime
    beep(988, 0.08, 'square', vol * 0.6, ctx, t)
    beep(1319, 0.15, 'square', vol * 0.6, ctx, t + 0.08)
  },
}

const ACTION_SOUNDS: Record<string, (ctx: AudioContext, vol: number) => void> = {
  done: (ctx, vol) => {
    const t = ctx.currentTime
    beep(440, 0.1, 'sine', vol * 0.5, ctx, t)
    beep(660, 0.15, 'sine', vol * 0.5, ctx, t + 0.1)
    beep(880, 0.2, 'sine', vol * 0.5, ctx, t + 0.22)
  },
  start: (ctx, vol) => beep(660, 0.1, 'sine', vol * 0.4, ctx, ctx.currentTime),
  pause: (ctx, vol) => beep(440, 0.1, 'sine', vol * 0.3, ctx, ctx.currentTime),
  timer_end: (ctx, vol) => SOUNDS['гонг'](ctx, vol),
  new_task: (ctx, vol) => beep(880, 0.08, 'sine', vol * 0.3, ctx, ctx.currentTime),
  take_now: (ctx, vol) => SOUNDS['1up'](ctx, vol),
  checkin_open: (ctx, vol) => {
    const t = ctx.currentTime
    beep(523, 0.08, 'sine', vol * 0.3, ctx, t)
    beep(659, 0.1, 'sine', vol * 0.3, ctx, t + 0.1)
  },
  checkin_save: (ctx, vol) => SOUNDS['победа'](ctx, vol),
  thought_saved: (ctx, vol) => beep(880, 0.1, 'sine', vol * 0.35, ctx, ctx.currentTime),
  task_delete: (ctx, vol) => beep(220, 0.2, 'sine', vol * 0.3, ctx, ctx.currentTime),
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
    const v = localStorage.getItem('sounds_enabled')
    return v !== 'false'
  } catch {
    return true
  }
}

export function playSound(name: string, volume?: number): void {
  if (!isSoundEnabled()) return
  const vol = volume ?? getVolume()
  try {
    const ctx = getCtx()
    const fn = SOUNDS[name] ?? ACTION_SOUNDS[name]
    if (fn) fn(ctx, vol)
  } catch (e) {
    console.warn('playSound error', e)
  }
}
