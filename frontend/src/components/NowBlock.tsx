import type { Task, Direction } from '../types'
import type { TimerState } from '../hooks/useTimer'

interface Props {
  task: Task | null
  directions: Direction[]
  timer: TimerState
  todayTime: number
  onStart: () => void
  onPause: () => void
  onDone: () => void
  onTaskClick: (task: Task) => void
  onAddTask: () => void
}

function padZ(n: number) { return String(n).padStart(2, '0') }

function formatElapsed(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${padZ(m)}:${padZ(sec)}`
}

function formatTodayTime(s: number) {
  if (s < 60) return `${s}с сегодня`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м сегодня`
  return `${m}м сегодня`
}

function priorityLabel(p: string) {
  if (p === 'high') return { label: 'Высокий', cls: 'text-[#b07070] bg-[#6a3030]/30' }
  if (p === 'medium') return { label: 'Средний', cls: 'text-[#a08850] bg-[#4a3a1e]/30' }
  return { label: 'Низкий', cls: 'text-[#555] bg-[#222]/60' }
}

export default function NowBlock({ task, directions, timer, todayTime, onStart, onPause, onDone, onTaskClick, onAddTask }: Props) {
  const direction = task ? directions.find(d => d.id === task.direction_id) : null
  const progress = timer.sessionDuration > 0 ? Math.min(1, timer.elapsed / (timer.sessionDuration * 60)) : 0
  const pri = task ? priorityLabel(task.priority) : null

  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4 select-none">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] mb-3 uppercase">Сейчас</div>

      {!task ? (
        <div className="flex flex-col items-center gap-3 py-4">
          <p className="text-[#666] text-sm">Ничего в работе — добавьте задачу</p>
          <button onClick={onAddTask} className="px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] transition-colors rounded text-sm text-white">+ Добавить задачу</button>
        </div>
      ) : (
        <>
          <div
            className="cursor-pointer hover:opacity-80 transition-opacity mb-3"
            onClick={() => onTaskClick(task)}
          >
            <h2 className="text-2xl font-bold text-[#f0f0f0] leading-tight mb-2">{task.title}</h2>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {direction && (
                <span className="text-[#666]">{direction.name}</span>
              )}
              {pri && (
                <span className={`px-1.5 py-0.5 rounded text-[10px] ${pri.cls}`}>{pri.label}</span>
              )}
              {task.duration_plan && (
                <span className="text-[#666]">{task.duration_plan}ч план</span>
              )}
            </div>
          </div>

          <div className="mb-2">
            <div className="text-4xl font-mono font-bold text-[#f0f0f0] tabular-nums mb-2">
              {formatElapsed(timer.elapsed)}
            </div>
            <div className="h-0.5 bg-[#252525] rounded-full overflow-hidden mb-1">
              <div
                className="h-full bg-[#5060a0] transition-all duration-1000"
                style={{ width: `${progress * 100}%` }}
              />
            </div>
            <div className="text-xs text-[#666]">{formatTodayTime(todayTime)}</div>
          </div>

          <div className="flex items-center gap-2 mt-3">
            {timer.isRunning ? (
              <button
                onClick={onPause}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#252525] hover:bg-[#383838] transition-colors rounded text-sm text-[#f0f0f0]"
              >
                ⏸ Пауза
              </button>
            ) : (
              <button
                onClick={onStart}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] transition-colors rounded text-sm text-white"
              >
                ▶ Старт
              </button>
            )}
            <button
              onClick={onDone}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#5060a0] hover:text-[#8090c8] transition-colors rounded text-sm text-[#666]"
            >
              ✓ Готово
            </button>
          </div>
        </>
      )}
    </div>
  )
}
