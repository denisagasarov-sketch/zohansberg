import { useState } from 'react'
import type { Task, Direction } from '../types'
import type { TimerState } from '../hooks/useTimer'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getQuadrant } from '../utils/quadrant'

interface Props {
  task: Task | null
  directions: Direction[]
  timer: TimerState
  todayTime: number
  onStart: () => void
  onStop: () => void
  onDone: () => void
  onTaskClick: (task: Task) => void
  onAddTask: () => void
  onDropTask: (taskId: number) => void
  onDragTask?: (taskId: number, e: React.DragEvent) => void
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

export default function NowBlock({ task, directions, timer, todayTime, onStart, onStop, onDone, onTaskClick, onAddTask, onDropTask, onDragTask }: Props) {
  const direction = task ? directions.find(d => d.id === task.direction_id) : null
  const q = task ? getQuadrant(task.is_important ?? 0, task.is_urgent ?? 0) : null
  const [isDragOver, setIsDragOver] = useState(false)

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setIsDragOver(true)
  }

  const handleDragLeave = () => setIsDragOver(false)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const raw = e.dataTransfer.getData(DRAG_TASK_KEY)
    const id = parseInt(raw, 10)
    if (!isNaN(id) && id !== task?.id) onDropTask(id)
  }

  return (
    <div
      className={`bg-[#1c1c1c] border rounded-lg p-4 select-none transition-colors ${isDragOver ? 'border-[#5060a0]' : 'border-[#252525]'}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] mb-3 uppercase">Сейчас</div>

      {!task ? (
        <div className="flex flex-col items-center gap-3 py-4">
          {isDragOver
            ? <p className="text-[#5060a0] text-sm">Отпустите, чтобы взять в работу</p>
            : <p className="text-[#666] text-sm">Ничего в работе — добавьте задачу</p>
          }
          {!isDragOver && (
            <button onClick={onAddTask} className="px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] transition-colors rounded text-sm text-white">+ Добавить задачу</button>
          )}
        </div>
      ) : (
        <>
          <div
            draggable
            onDragStart={e => {
              e.dataTransfer.setData(DRAG_TASK_KEY, String(task.id))
              e.dataTransfer.effectAllowed = 'move'
              onDragTask?.(task.id, e)
            }}
            className="cursor-pointer hover:opacity-80 transition-opacity mb-3"
            onClick={() => onTaskClick(task)}
          >
            <h2 className="text-2xl font-bold text-[#f0f0f0] leading-tight mb-2">{task.title}</h2>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {direction && (
                <span className="text-[#666]">{direction.name}</span>
              )}
              {q && <span className="px-1.5 py-0.5 rounded text-[10px]" style={{ color: q.color, backgroundColor: q.border + '30' }}>{q.label}</span>}
              {task.duration_plan && (
                <span className="text-[#666]">{task.duration_plan}ч план</span>
              )}
            </div>
          </div>

          <div className="mb-2">
            <div className="text-4xl font-mono font-bold text-[#f0f0f0] tabular-nums mb-1">
              {formatElapsed(timer.elapsed)}
            </div>
            <div className="text-xs text-[#666]">{formatTodayTime(todayTime)}</div>
          </div>

          <div className="flex items-center gap-2 mt-3">
            {timer.isRunning ? (
              <button
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[#252525] hover:bg-[#383838] transition-colors rounded text-sm text-[#f0f0f0]"
              >
                ⏹ Стоп
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
