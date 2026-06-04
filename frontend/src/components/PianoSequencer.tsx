import { useState, useRef, useEffect, useCallback } from 'react'

// ── 8-bit synth (square wave) ─────────────────────────────────────────────────

let audioCtx: AudioContext | null = null
function getCtx(): AudioContext {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)()
  }
  if (audioCtx.state === 'suspended') audioCtx.resume().catch(() => {})
  return audioCtx
}

function blip(freq: number, dur = 0.18, vol = 0.18) {
  const ctx = getCtx()
  const t = ctx.state !== 'running' ? ctx.currentTime + 0.05 : ctx.currentTime
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'square'
  osc.frequency.setValueAtTime(freq, t)
  gain.gain.setValueAtTime(vol, t)
  gain.gain.exponentialRampToValueAtTime(0.0005, t + dur)
  osc.connect(gain); gain.connect(ctx.destination)
  osc.start(t); osc.stop(t + dur + 0.02)
}

// C major scale, high → low for grid rows (top row = highest note)
const NOTES = [
  { name: 'C5', freq: 523.25 },
  { name: 'B4', freq: 493.88 },
  { name: 'A4', freq: 440.0 },
  { name: 'G4', freq: 392.0 },
  { name: 'F4', freq: 349.23 },
  { name: 'E4', freq: 329.63 },
  { name: 'D4', freq: 293.66 },
  { name: 'C4', freq: 261.63 },
]

const STEPS = 16
const KEY_MAP: Record<string, number> = {
  z: 7, x: 6, c: 5, v: 4, b: 3, n: 2, m: 1, ',': 0,
}

function emptyGrid(): boolean[][] {
  return NOTES.map(() => Array(STEPS).fill(false))
}

function fmtDur(ms: number) {
  const s = Math.round(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

// ── Saved items: a 16-step loop, or a free-length performance track ───────────

interface RecEvent { t: number; note: number }
type Saved =
  | { id: number; kind: 'loop'; name: string; bpm: number; grid: boolean[][] }
  | { id: number; kind: 'track'; name: string; duration: number; events: RecEvent[] }

const STORE_KEY = 'piano_patterns'

function loadSaved(): Saved[] {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    const list = raw ? JSON.parse(raw) : []
    // migrate old loop-only entries (no `kind`)
    return list.map((p: any) => p.kind ? p : { ...p, kind: 'loop' })
  } catch { return [] }
}

function persist(list: Saved[]) {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(list)) } catch {}
}

export default function PianoSequencer() {
  const [grid, setGrid] = useState<boolean[][]>(emptyGrid)
  const [playing, setPlaying] = useState(false)
  const [bpm, setBpm] = useState(120)
  const [step, setStep] = useState(0)
  const [recording, setRecording] = useState(false)
  const [recMs, setRecMs] = useState(0)
  const [playingTrackId, setPlayingTrackId] = useState<number | null>(null)
  const [saved, setSaved] = useState<Saved[]>(loadSaved)

  const stepRef = useRef(0)
  const gridRef = useRef(grid)
  gridRef.current = grid
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // performance recording
  const recStartRef = useRef(0)
  const recEventsRef = useRef<RecEvent[]>([])
  const recTickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const recordingRef = useRef(false)
  recordingRef.current = recording

  // track playback timeouts
  const trackTimeouts = useRef<ReturnType<typeof setTimeout>[]>([])

  // drag-paint state
  const paintRef = useRef<{ active: boolean; mode: boolean } | null>(null)

  const clearTimer = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }, [])

  // Step-sequencer loop — 16th notes
  useEffect(() => {
    if (!playing) { clearTimer(); return }
    const stepMs = (60 / bpm / 4) * 1000
    clearTimer()
    intervalRef.current = setInterval(() => {
      const s = stepRef.current
      const g = gridRef.current
      for (let row = 0; row < NOTES.length; row++) {
        if (g[row][s]) blip(NOTES[row].freq)
      }
      const next = (s + 1) % STEPS
      stepRef.current = next
      setStep(next)
    }, stepMs)
    return clearTimer
  }, [playing, bpm, clearTimer])

  useEffect(() => () => {
    clearTimer()
    if (recTickRef.current) clearInterval(recTickRef.current)
    trackTimeouts.current.forEach(clearTimeout)
  }, [clearTimer])

  // Global mouseup ends drag-paint
  useEffect(() => {
    const up = () => { paintRef.current = null }
    window.addEventListener('mouseup', up)
    return () => window.removeEventListener('mouseup', up)
  }, [])

  const paintCell = (row: number, col: number, mode: boolean) => {
    setGrid(prev => {
      if (prev[row][col] === mode) return prev
      return prev.map((r, ri) => ri === row ? r.map((c, ci) => ci === col ? mode : c) : r)
    })
  }

  const onCellDown = (row: number, col: number) => {
    const mode = !grid[row][col]
    paintRef.current = { active: true, mode }
    paintCell(row, col, mode)
  }

  const onCellEnter = (row: number, col: number) => {
    if (paintRef.current?.active) paintCell(row, col, paintRef.current.mode)
  }

  const playKey = useCallback((row: number) => {
    blip(NOTES[row].freq)
    if (recordingRef.current) {
      recEventsRef.current.push({ t: Date.now() - recStartRef.current, note: row })
    }
  }, [])

  // Keyboard play
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.repeat) return
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      const row = KEY_MAP[e.key.toLowerCase()]
      if (row !== undefined) { e.preventDefault(); playKey(row) }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [playKey])

  const togglePlay = () => {
    if (!playing) { stepRef.current = 0; setStep(0) }
    setPlaying(p => !p)
  }

  // ── Performance recording ──
  const toggleRec = () => {
    if (!recording) {
      recStartRef.current = Date.now()
      recEventsRef.current = []
      setRecMs(0)
      setRecording(true)
      recTickRef.current = setInterval(() => setRecMs(Date.now() - recStartRef.current), 200)
    } else {
      setRecording(false)
      if (recTickRef.current) { clearInterval(recTickRef.current); recTickRef.current = null }
      const duration = Date.now() - recStartRef.current
      const events = recEventsRef.current
      if (events.length > 0) {
        const time = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
        const trackN = saved.filter(s => s.kind === 'track').length + 1
        const entry: Saved = { id: Date.now(), kind: 'track', name: `Трек ${trackN} · ${time}`, duration, events }
        const next = [entry, ...saved]
        setSaved(next); persist(next)
      }
    }
  }

  const hasNotes = grid.some(r => r.some(Boolean))

  const handleSaveLoop = () => {
    if (!hasNotes) return
    const time = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    const loopN = saved.filter(s => s.kind === 'loop').length + 1
    const entry: Saved = { id: Date.now(), kind: 'loop', name: `Луп ${loopN} · ${time}`, bpm, grid: grid.map(r => [...r]) }
    const next = [entry, ...saved]
    setSaved(next); persist(next)
  }

  const handleLoadLoop = (p: Extract<Saved, { kind: 'loop' }>) => {
    setPlaying(false)
    setGrid(p.grid.map(r => [...r]))
    setBpm(p.bpm)
  }

  const stopTrack = () => {
    trackTimeouts.current.forEach(clearTimeout)
    trackTimeouts.current = []
    setPlayingTrackId(null)
  }

  const playTrack = (track: Extract<Saved, { kind: 'track' }>) => {
    stopTrack()
    setPlayingTrackId(track.id)
    track.events.forEach(ev => {
      trackTimeouts.current.push(setTimeout(() => blip(NOTES[ev.note].freq), ev.t))
    })
    trackTimeouts.current.push(setTimeout(() => setPlayingTrackId(null), track.duration + 250))
  }

  const handleDelete = (id: number) => {
    if (playingTrackId === id) stopTrack()
    const next = saved.filter(p => p.id !== id)
    setSaved(next); persist(next)
  }

  return (
    <div className="w-full max-w-[420px] bg-[#141414] border border-[#252525] rounded-xl p-3" onClick={e => e.stopPropagation()}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase flex-1">8-bit студия</span>
        <button
          onClick={togglePlay}
          className={`px-2 py-0.5 rounded text-[11px] transition-colors ${playing ? 'bg-[#5060a0] text-white' : 'bg-[#252525] text-[#999] hover:bg-[#383838]'}`}
        >{playing ? '⏸ стоп' : '▶ луп'}</button>
        <button
          onClick={toggleRec}
          className={`px-2 py-0.5 rounded text-[11px] transition-colors ${recording ? 'bg-[#a04050] text-white' : 'bg-[#252525] text-[#999] hover:bg-[#383838]'}`}
          title="Запись живой игры в отдельный трек"
        >{recording ? `● ${fmtDur(recMs)}` : '● rec'}</button>
        <button
          onClick={handleSaveLoop}
          disabled={!hasNotes}
          className="px-2 py-0.5 rounded text-[11px] bg-[#252525] text-[#999] hover:bg-[#383838] disabled:opacity-40 transition-colors"
          title="Сохранить луп"
        >💾</button>
        <button
          onClick={() => setGrid(emptyGrid())}
          className="px-2 py-0.5 rounded text-[11px] bg-[#252525] text-[#666] hover:bg-[#383838] transition-colors"
        >clear</button>
      </div>

      {/* BPM */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-[10px] text-[#555] w-8">BPM</span>
        <input
          type="range" min={60} max={200} value={bpm}
          onChange={e => setBpm(parseInt(e.target.value))}
          className="flex-1 accent-[#5060a0]"
        />
        <span className="text-[11px] font-mono text-[#999] w-7 text-right">{bpm}</span>
      </div>

      {/* Step grid (drag to paint / erase) */}
      <div className="space-y-0.5 select-none">
        {NOTES.map((note, row) => (
          <div key={note.name} className="flex items-center gap-1">
            <button
              onMouseDown={() => playKey(row)}
              className="w-7 shrink-0 text-[9px] font-mono text-[#666] bg-[#1c1c1c] hover:bg-[#5060a0] hover:text-white rounded py-0.5 transition-colors"
              title={`Сыграть ${note.name}`}
            >{note.name}</button>
            <div className="flex gap-0.5 flex-1">
              {Array.from({ length: STEPS }).map((_, col) => {
                const active = grid[row][col]
                const isBeat = col % 4 === 0
                const isCur = playing && step === col
                return (
                  <button
                    key={col}
                    onMouseDown={() => onCellDown(row, col)}
                    onMouseEnter={() => onCellEnter(row, col)}
                    className={`flex-1 h-3.5 rounded-[2px] transition-colors ${
                      active
                        ? 'bg-[#5060a0]'
                        : isCur
                          ? 'bg-[#383838]'
                          : isBeat ? 'bg-[#222]' : 'bg-[#1a1a1a]'
                    } hover:bg-[#6070b0]`}
                  />
                )
              })}
            </div>
          </div>
        ))}
      </div>

      <p className="text-[9px] text-[#383838] mt-2">Зажми и веди мышкой — рисуй/стирай ноты. z x c v b n m , — играть. ● rec пишет игру в трек.</p>

      {/* Saved loops & tracks */}
      {saved.length > 0 && (
        <div className="mt-2 pt-2 border-t border-[#252525] space-y-1">
          <div className="text-[9px] font-semibold tracking-widest text-[#383838] uppercase">Записи</div>
          {saved.map(p => (
            <div key={p.id} className="flex items-center gap-2 group">
              {p.kind === 'loop' ? (
                <button
                  onClick={() => handleLoadLoop(p)}
                  className="flex-1 text-left text-[11px] text-[#999] hover:text-[#8090c8] transition-colors truncate"
                  title="Загрузить луп в секвенсор"
                >▦ {p.name} · {p.bpm} BPM</button>
              ) : (
                <button
                  onClick={() => playingTrackId === p.id ? stopTrack() : playTrack(p)}
                  className="flex-1 text-left text-[11px] text-[#999] hover:text-[#8090c8] transition-colors truncate"
                  title="Воспроизвести трек"
                >{playingTrackId === p.id ? '⏸' : '▶'} {p.name} · {fmtDur(p.duration)}</button>
              )}
              <button
                onClick={() => handleDelete(p.id)}
                className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#a04050] text-xs transition-all shrink-0"
                title="Удалить"
              >×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
