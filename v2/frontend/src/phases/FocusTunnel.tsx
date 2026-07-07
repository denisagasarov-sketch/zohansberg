// Фокус-туннель: полноэкранная сессия. Ничего, кроме задачи, времени и шагов.
// Дышащий амбиентный фон: янтарь в работе, шалфей на паузе.
import { useState, useEffect } from 'react'
import type { Task, Direction } from '../types'
import type { TimerState } from '../hooks/useTimer'
import { api } from '../api'
import SubtaskList from '../components/SubtaskList'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  task: Task
  directions: Direction[]
  timer: TimerState
  intent: string
  pomodoroPhase?: 'work' | 'break' | 'idle'
  pomodoroRemaining?: number
  onSkipPomodoro?: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  onDone: () => void
}

function padZ(n: number) { return String(n).padStart(2, '0') }
function formatElapsed(s: number) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  return h > 0 ? `${h}:${padZ(m)}:${padZ(sec)}` : `${padZ(m)}:${padZ(sec)}`
}
function fmt(s: number): string {
  if (s < 60) return `${s}с`
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

const PAUSE_TIPS = [
  'Встань и потянись', 'Выпей стакан воды', 'Посмотри вдаль 20 секунд',
  'Сделай несколько глубоких вдохов', 'Разомни шею и плечи', 'Закрой глаза и отдохни',
]

export default function FocusTunnel({ task, directions, timer, intent, pomodoroPhase = 'idle', pomodoroRemaining = 0, onSkipPomodoro, onPause, onResume, onStop, onDone }: Props) {
  const [todayTime, setTodayTime] = useState(0)
  const [lastNote, setLastNote] = useState<string | null>(null)
  const [lastSession, setLastSession] = useState<{ seconds: number; when: string } | null>(null)
  const [pauseTip] = useState(() => PAUSE_TIPS[Math.floor(Math.random() * PAUSE_TIPS.length)])
  const [pauseSec, setPauseSec] = useState(0)
  const [breakNudgeDismissed, setBreakNudgeDismissed] = useState(false)

  const dir = directions.find(d => d.id === task.direction_id)
  const dirColor = dir ? getDirectionColor(dir.id) : null
  const paused = timer.isPaused

  useEffect(() => {
    setBreakNudgeDismissed(false)
    api.getTodayTime(task.id).then(r => setTodayTime(r.total)).catch(() => {})
    api.getTaskSessions(task.id).then(rows => {
      const list = rows as { started_at?: string | null; ended_at?: string | null; duration_actual?: number | null; note?: string | null }[]
      const withNote = list.find(r => r.note?.trim())
      setLastNote(withNote?.note?.trim() ?? null)
      const done = list.find(r => r.ended_at)
      if (done) {
        const when = done.ended_at ?? done.started_at ?? ''
        const d = new Date(when)
        const now = new Date()
        const sameDay = (a: Date, b: Date) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
        const yest = new Date(now); yest.setDate(now.getDate() - 1)
        let rel = ''
        if (!isNaN(d.getTime())) rel = sameDay(d, now) ? 'сегодня' : sameDay(d, yest) ? 'вчера' : ''
        setLastSession({ seconds: done.duration_actual ?? 0, when: rel })
      } else {
        setLastSession(null)
      }
    }).catch(() => {})
  }, [task.id])

  // Счётчик паузы
  useEffect(() => {
    if (!paused) { setPauseSec(0); return }
    const id = setInterval(() => setPauseSec(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [paused])

  const spentToday = todayTime + timer.elapsed

  return (
    <div className="absolute inset-0 z-20 overflow-hidden select-none bg-[#0d0c0b]">
      {/* Дышащий амбиент */}
      <div
        className="absolute inset-0 pointer-events-none tunnel-breath"
        style={{
          background: paused
            ? 'radial-gradient(55% 45% at 50% 46%, rgba(130,168,119,0.13) 0%, rgba(13,12,11,0) 70%)'
            : 'radial-gradient(55% 45% at 50% 46%, rgba(224,164,88,0.11) 0%, rgba(13,12,11,0) 70%)',
        }}
      />
      <div className="absolute inset-0 flex flex-col items-center justify-center px-8">

        {/* Интент или подсказка паузы */}
        <div className={`text-[12px] font-semibold tracking-[0.22em] uppercase mb-2 transition-colors ${paused ? 'text-[#7fa878]' : intent ? 'text-accent/90' : 'text-text-faint'}`}>
          {paused ? pauseTip : (intent || 'Фокус')}
        </div>

        {/* Напоминание намерения вернувшемуся: только что начатая/возобновлённая сессия */}
        {intent && !paused && timer.elapsed < 120 && (
          <div className="text-[11px] text-text-faint mb-6 max-w-lg text-center animate-fade-in">
            ты начинал: {intent}
          </div>
        )}
        {!(intent && !paused && timer.elapsed < 120) && <div className="mb-6" />}

        {/* Таймер */}
        <div className={`font-mono font-semibold tabular-nums leading-none tracking-tight transition-colors duration-500 ${paused ? 'text-[#4d5f45]' : 'text-text'}`}
          style={{ fontSize: 'clamp(96px, 14vw, 176px)' }}>
          {formatElapsed(timer.elapsed)}
        </div>

        {/* Пауза: её длительность */}
        <div className={`h-5 mt-3 text-[13px] tabular-nums transition-opacity ${paused ? 'opacity-100 text-[#5f7f58]' : 'opacity-0'}`}>
          пауза {formatElapsed(pauseSec)}
        </div>

        {/* Задача */}
        <div className="mt-6 max-w-2xl text-center">
          <div className="flex items-center justify-center gap-2.5 mb-1.5">
            {dir && dirColor && <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: dirColor, backgroundColor: dirColor + '22' }}>{dir.name}</span>}
            <span className="text-[11px] text-text-muted tabular-nums">{fmt(spentToday)} сегодня</span>
          </div>
          <h1 className={`text-[22px] font-semibold tracking-tight leading-snug ${paused ? 'text-text-secondary' : 'text-text'}`}>{task.title}</h1>
        </div>

        {/* Помодоро */}
        {pomodoroPhase !== 'idle' && (
          <div className={`flex items-center gap-2 mt-5 px-3 py-1 rounded-full text-xs ${pomodoroPhase === 'break' ? 'bg-[#20281d] text-ok' : 'bg-accent/10 text-accent-light'}`}>
            <span>{pomodoroPhase === 'break' ? 'Перерыв' : 'Помодоро'}</span>
            <span className="font-mono tabular-nums text-text">{padZ(Math.floor(pomodoroRemaining / 60))}:{padZ(pomodoroRemaining % 60)}</span>
            <button onClick={onSkipPomodoro} className="text-text-muted hover:text-text-secondary text-[10px] ml-1">пропустить</button>
          </div>
        )}

        {/* Мягкий якорь от гиперфокуса */}
        {timer.isRunning && !paused && timer.elapsed >= 3000 && !breakNudgeDismissed && (
          <div className="flex items-center gap-3 mt-6 px-3.5 py-2 rounded-full bg-raised/60 border border-border text-[12px] text-text-muted animate-fade-in">
            <span>Ты в фокусе 50 минут — 5 минут паузы?</span>
            <button onClick={onPause} className="text-accent-light hover:text-accent text-[12px]">Пауза</button>
            <button onClick={() => setBreakNudgeDismissed(true)} className="text-text-faint hover:text-text-secondary text-[13px] leading-none" aria-label="Скрыть">✕</button>
          </div>
        )}

        {/* Управление */}
        <div className="flex items-center gap-2.5 mt-9">
          {timer.isRunning && <button onClick={onPause} className="btn bg-raised text-text hover:bg-border-strong !px-5 !py-2.5">Пауза</button>}
          {paused && <button onClick={onResume} className="btn-primary !px-5 !py-2.5">▶ Продолжить</button>}
          <button onClick={onStop} className="btn-outline !px-5 !py-2.5">■ Стоп</button>
        </div>
        <div className="text-[10px] text-text-faint mt-3">Space — пауза/продолжить</div>

        {/* Шаги задачи */}
        <div className="w-full max-w-md mt-9">
          <SubtaskList
            key={task.id}
            taskId={task.id}
            compact
            onChanged={() => window.dispatchEvent(new CustomEvent('gamification-updated'))}
          />
        </div>

        {/* Где остановился в прошлый раз */}
        {timer.elapsed < 300 && (lastNote || lastSession) && (
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 max-w-lg text-center animate-fade-in">
            <span className="text-[10px] uppercase tracking-[0.14em] text-text-faint">в прошлый раз · </span>
            {lastNote
              ? <span className="text-[12px] text-text-muted">{lastNote}</span>
              : <span className="text-[12px] text-text-muted">{fmt(lastSession!.seconds)}{lastSession!.when ? ` · ${lastSession!.when}` : ''}</span>}
          </div>
        )}
      </div>
    </div>
  )
}
