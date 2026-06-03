import { useState, useEffect } from 'react'
import { api } from '../../api'
import { playSound } from '../../sound'

interface Props {
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

interface TaskRow {
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

function TaskCard({ task, done }: { task: TaskRow; done: boolean }) {
  const [open, setOpen] = useState(false)
  const hasSessions = task.sessions.length > 0

  return (
    <div className="bg-[#141414] rounded-xl overflow-hidden">
      <button
        onClick={() => hasSessions && setOpen(v => !v)}
        className={`w-full flex items-center gap-3 px-4 py-3 text-left ${hasSessions ? 'hover:bg-[#1a1a1a]' : ''} transition-colors`}
      >
        <span className={`text-xs shrink-0 w-3 ${done ? 'text-[#4a7a4a]' : 'text-[#555]'}`}>
          {done ? '✓' : '·'}
        </span>
        <span className={`flex-1 text-sm truncate ${done ? 'text-[#c8c8c8]' : 'text-[#777]'}`}>
          {task.title}
        </span>
        {task.time_seconds > 0 && (
          <span className="text-[11px] text-[#555] font-mono shrink-0">{formatSeconds(task.time_seconds)}</span>
        )}
        {hasSessions && (
          <span className="text-[#383838] text-[10px] shrink-0 ml-1">{open ? '▲' : '▼'}</span>
        )}
      </button>

      {open && hasSessions && (
        <div className="border-t border-[#1e1e1e] divide-y divide-[#1e1e1e]">
          {task.sessions.map(s => (
            <div key={s.id} className="px-4 py-2.5 flex gap-3 items-start">
              <span className="text-[11px] text-[#444] font-mono shrink-0 mt-0.5 whitespace-nowrap">
                {formatTime(s.started_at)}
                {s.ended_at ? ` → ${formatTime(s.ended_at)}` : ''}
              </span>
              <span className="text-[11px] text-[#555] font-mono shrink-0 mt-0.5">
                {formatSeconds(s.duration_actual)}
              </span>
              {s.note && (
                <span className="text-[11px] text-[#666] italic flex-1 leading-snug">{s.note}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function EveningSummaryModal({ onClose, onLater }: Props) {
  const [bars, setBars] = useState([0.4, 0.7, 0.5, 0.9, 0.3, 0.8, 0.6, 0.4, 0.7, 0.5])
  const [doneCount, setDoneCount] = useState(0)
  const [timeSeconds, setTimeSeconds] = useState(0)
  const [doneTasks, setDoneTasks] = useState<TaskRow[]>([])
  const [workedTasks, setWorkedTasks] = useState<TaskRow[]>([])

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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80" onClick={onLater} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

        {/* Animated sound bars */}
        <div className="flex items-end gap-1 px-6 pt-5 pb-1 h-14 shrink-0" style={{ background: 'linear-gradient(180deg, #1a1a2e 0%, #1c1c1c 100%)' }}>
          {bars.map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-sm"
              style={{
                height: `${h * 100}%`,
                backgroundColor: `hsl(${230 + i * 4}, 60%, ${45 + h * 20}%)`,
                transition: 'height 0.12s ease-in-out',
              }}
            />
          ))}
        </div>

        <div className="px-6 pt-4 pb-2 shrink-0">
          <h2 className="text-xl font-bold text-[#f0f0f0] mb-0.5">Итог дня</h2>
          <p className="text-sm text-[#555] capitalize">{today}</p>
        </div>

        {/* Metrics */}
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

        {/* Task list — scrollable */}
        {hasTasks && (
          <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0">
            <div className="space-y-1.5">
              {doneTasks.map(task => <TaskCard key={task.id} task={task} done />)}
              {workedTasks.length > 0 && doneTasks.length > 0 && (
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase pt-2 pb-1">В работе</div>
              )}
              {workedTasks.map(task => <TaskCard key={task.id} task={task} done={false} />)}
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="px-6 py-4 shrink-0 border-t border-[#252525] flex gap-2">
          <button onClick={onLater} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
            Позже
          </button>
          <button onClick={onClose} className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white transition-colors font-medium">
            Закрыть день ✓
          </button>
        </div>
      </div>
    </div>
  )
}
