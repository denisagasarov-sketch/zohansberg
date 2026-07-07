import { useState, useEffect } from 'react'
import type { Task, Direction } from '../../types'
import { api } from '../../api'
import { playSound } from '../../sound'
import { getDirectionColor } from '../../utils/directionColors'
import { priorityLabel, priorityColor } from '../../utils/priority'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onClose: () => void
  onLater: () => void
}

interface SessionRow {
  id: number
  started_at: string
  ended_at: string | null
  duration_actual: number
  note: string | null
}

interface SummaryTask {
  id: number
  title: string
  time_seconds: number
  sessions: SessionRow[]
}

function formatSeconds(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0 && m > 0) return `${h}ч ${m}м`
  if (h > 0) return `${h}ч`
  if (m > 0) return `${m}м`
  return '<1м'
}

function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function TaskCard({ task, done }: { task: SummaryTask; done: boolean }) {
  const [open, setOpen] = useState(false)
  const hasSessions = task.sessions.length > 0
  return (
    <div className="bg-[#141414] rounded-xl overflow-hidden">
      <button
        onClick={() => hasSessions && setOpen(v => !v)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left ${hasSessions ? 'hover:bg-[#1a1a1a]' : ''} transition-colors`}
      >
        <span className={`text-xs shrink-0 w-3 ${done ? 'text-[#4a7a4a]' : 'text-[#555]'}`}>{done ? '✓' : '·'}</span>
        <span className={`flex-1 text-sm truncate ${done ? 'text-[#c8c8c8]' : 'text-[#777]'}`}>{task.title}</span>
        {task.time_seconds > 0 && (
          <span className="text-[11px] text-[#555] font-mono shrink-0">{formatSeconds(task.time_seconds)}</span>
        )}
        {hasSessions && <span className="text-[#383838] text-[10px] shrink-0 ml-1">{open ? '▲' : '▼'}</span>}
      </button>
      {open && hasSessions && (
        <div className="border-t border-[#1e1e1e] divide-y divide-[#1e1e1e]">
          {task.sessions.map(s => (
            <div key={s.id} className="px-4 py-2.5 flex gap-3 items-start">
              <span className="text-[11px] text-[#444] font-mono shrink-0 mt-0.5 whitespace-nowrap">
                {formatTime(s.started_at)}{s.ended_at ? ` → ${formatTime(s.ended_at)}` : ''}
              </span>
              <span className="text-[11px] text-[#555] font-mono shrink-0 mt-0.5">{formatSeconds(s.duration_actual)}</span>
              {s.note && <span className="text-[11px] text-[#666] italic flex-1 leading-snug">{s.note}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Step 2: plan picker ───────────────────────────────────────────────────────

function PlanPicker({ tasks, directions, onSave, onSkip }: {
  tasks: Task[]
  directions: Direction[]
  onSave: (ids: number[]) => void
  onSkip: () => void
}) {
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const available = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday)

  // Group by direction
  const byDir: { dir: Direction | null; tasks: Task[] }[] = []
  const withDir = available.filter(t => t.direction_id != null)
  const noDir = available.filter(t => t.direction_id == null)

  directions.forEach(dir => {
    const dt = withDir.filter(t => t.direction_id === dir.id)
    if (dt.length > 0) byDir.push({ dir, tasks: dt })
  })
  if (noDir.length > 0) byDir.push({ dir: null, tasks: noDir })

  const toggle = (id: number) => setSelected(prev => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })

  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowStr = tomorrow.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <>
      <div className="px-6 pt-5 pb-2 shrink-0">
        <div className="text-xs text-[#5060a0] font-semibold tracking-widest uppercase mb-1">Шаг 2 из 2</div>
        <h2 className="text-xl font-bold text-[#f0f0f0] mb-0.5">Что завтра?</h2>
        <p className="text-sm text-[#555] capitalize">{tomorrowStr}</p>
      </div>

      <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0">
        {byDir.map(({ dir, tasks: dt }) => {
          const c = dir ? getDirectionColor(dir.id) : null
          return (
            <div key={dir?.id ?? 'none'} className="mb-4">
              <div className="text-[10px] font-semibold tracking-widest uppercase mb-1.5"
                style={{ color: c ?? '#383838' }}>
                {dir?.name ?? 'Без направления'}
              </div>
              <div className="space-y-1">
                {dt.map(task => {
                  const active = selected.has(task.id)
                  return (
                    <button
                      key={task.id}
                      onClick={() => toggle(task.id)}
                      className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-colors ${
                        active ? 'bg-[#5060a0]/20 border border-[#5060a0]/40' : 'bg-[#141414] border border-transparent hover:bg-[#1a1a1a]'
                      }`}
                    >
                      <span className={`w-4 h-4 rounded shrink-0 border flex items-center justify-center text-[10px] ${
                        active ? 'border-[#5060a0] bg-[#5060a0] text-white' : 'border-[#333]'
                      }`}>
                        {active ? '✓' : ''}
                      </span>
                      {task.priority && task.priority !== 'none' && (
                        <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>
                          {priorityLabel(task.priority)}
                        </span>
                      )}
                      <span className="flex-1 text-sm text-[#c0c0c0] truncate">{task.title}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
        {available.length === 0 && (
          <p className="text-sm text-[#555] text-center py-8">Нет незавершённых задач</p>
        )}
      </div>

      <div className="px-6 py-4 shrink-0 border-t border-[#252525] flex gap-2">
        <button onClick={onSkip} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
          Пропустить
        </button>
        <button
          onClick={() => onSave([...selected])}
          className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors"
        >
          Сохранить план {selected.size > 0 ? `(${selected.size})` : ''}
        </button>
      </div>
    </>
  )
}

// ── Main modal ────────────────────────────────────────────────────────────────

export default function EveningSummaryModal({ tasks, directions, onClose, onLater }: Props) {
  const [bars, setBars] = useState([0.4, 0.7, 0.5, 0.9, 0.3, 0.8, 0.6, 0.4, 0.7, 0.5])
  const [doneCount, setDoneCount] = useState(0)
  const [timeSeconds, setTimeSeconds] = useState(0)
  const [doneTasks, setDoneTasks] = useState<SummaryTask[]>([])
  const [workedTasks, setWorkedTasks] = useState<SummaryTask[]>([])
  const [step, setStep] = useState<1 | 2>(1)

  useEffect(() => {
    playSound('fanfare', 1.0)
    api.getTodaySummary().then((d: any) => {
      setDoneCount(d.done_count)
      setTimeSeconds(d.time_seconds)
      setDoneTasks(d.done_tasks ?? [])
      setWorkedTasks(d.worked_tasks ?? [])
    }).catch(() => {})
    const id = setInterval(() => {
      setBars(prev => prev.map(() => 0.15 + Math.random() * 0.85))
    }, 130)
    return () => clearInterval(id)
  }, [])

  const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'long' })
  const hasTasks = doneTasks.length > 0 || workedTasks.length > 0

  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowDate = tomorrow.toISOString().slice(0, 10)

  const handleSavePlan = async (ids: number[]) => {
    if (ids.length > 0) {
      await api.setDayPlan(tomorrowDate, ids).catch(() => {})
    }
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80" onClick={onLater} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

        {step === 1 ? (
          <>
            {/* Animated bars */}
            <div className="flex items-end gap-1 px-6 pt-5 pb-1 h-14 shrink-0" style={{ background: 'linear-gradient(180deg, #1a1a2e 0%, #1c1c1c 100%)' }}>
              {bars.map((h, i) => (
                <div key={i} className="flex-1 rounded-t-sm" style={{
                  height: `${h * 100}%`,
                  backgroundColor: `hsl(${230 + i * 4}, 60%, ${45 + h * 20}%)`,
                  transition: 'height 0.12s ease-in-out',
                }} />
              ))}
            </div>

            <div className="px-6 pt-4 pb-2 shrink-0">
              <div className="text-xs text-[#383838] font-semibold tracking-widest uppercase mb-1">Шаг 1 из 2</div>
              <h2 className="text-xl font-bold text-[#f0f0f0] mb-0.5">Итог дня</h2>
              <p className="text-sm text-[#555] capitalize">{today}</p>
            </div>

            <div className="px-6 py-3 shrink-0">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{doneCount}</div>
                  <div className="text-xs text-[#555] mt-0.5">задач выполнено</div>
                </div>
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{formatSeconds(timeSeconds)}</div>
                  <div className="text-xs text-[#555] mt-0.5">время в работе</div>
                </div>
              </div>
            </div>

            {hasTasks && (
              <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0">
                <div className="space-y-1.5">
                  {doneTasks.map(t => <TaskCard key={t.id} task={t} done />)}
                  {workedTasks.length > 0 && doneTasks.length > 0 && (
                    <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase pt-2 pb-1">В работе</div>
                  )}
                  {workedTasks.map(t => <TaskCard key={t.id} task={t} done={false} />)}
                </div>
              </div>
            )}

            <div className="px-6 py-4 shrink-0 border-t border-[#252525] flex gap-2">
              <button onClick={onLater} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
                Позже
              </button>
              <button onClick={() => setStep(2)} className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors">
                Закрыть день →
              </button>
            </div>
          </>
        ) : (
          <PlanPicker
            tasks={tasks}
            directions={directions}
            onSave={handleSavePlan}
            onSkip={onClose}
          />
        )}
      </div>
    </div>
  )
}
