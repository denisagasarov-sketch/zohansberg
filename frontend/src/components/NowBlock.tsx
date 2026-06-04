import { useState } from 'react'
import type { Task, Direction } from '../types'
import type { TimerState } from '../hooks/useTimer'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getDirectionColor } from '../utils/directionColors'
import { priorityLabel, priorityColor } from '../utils/priority'
import { PriorityPicker } from './PriorityPicker'

interface Props {
  task: Task | null
  directions: Direction[]
  timer: TimerState
  todayTime: number
  onStart: () => void
  onStop: () => void
  onPause: () => void
  onResume: () => void
  onDone: () => void
  onSendToQueue: () => void
  onTaskClick: (task: Task) => void
  onAddTask: () => void
  onDropTask: (taskId: number) => void
  onPriorityChange: (taskId: number, priority: string) => void
  pomodoroPhase?: 'work' | 'break' | 'idle'
  pomodoroRemaining?: number
  onSkipPomodoro?: () => void
}

function padZ(n: number) { return String(n).padStart(2, '0') }

function formatElapsed(s: number) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${padZ(m)}:${padZ(sec)}`
}

function formatTime(s: number): string {
  if (s < 60) return `${s}с`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

export default function NowBlock({ task, directions, timer, todayTime, onStart, onStop, onPause, onResume, onDone, onSendToQueue, onTaskClick, onAddTask, onDropTask, onPriorityChange, pomodoroPhase = 'idle', pomodoroRemaining = 0, onSkipPomodoro }: Props) {
  const [showPrio, setShowPrio] = useState(false)
  const direction = task ? directions.find(d => d.id === task.direction_id) : null
  const dirColor = direction ? getDirectionColor(direction.id) : null
  const [isDragOver, setIsDragOver] = useState(false)

  const timerActive = timer.isRunning || timer.isPaused

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
        <div className="py-10 text-center">
          <div className="text-[#383838] text-sm">Нет активной задачи</div>
          <div className="text-[#2c2c2c] text-xs mt-1.5">Перетащите сюда задачу или возьмите из «Следом»</div>
        </div>
      ) : (
        <>
          {/* Task title row */}
          <div
            draggable
            onDragStart={e => {
              e.dataTransfer.setData(DRAG_TASK_KEY, String(task.id))
              e.dataTransfer.effectAllowed = 'move'
            }}
            className="cursor-pointer hover:opacity-80 transition-opacity mb-4"
            onClick={() => onTaskClick(task)}
          >
            <div className="flex items-start gap-2 mb-1.5">
              <div className="relative shrink-0 mt-[3px]">
                <button
                  onClick={e => { e.stopPropagation(); setShowPrio(v => !v) }}
                  className={`text-[13px] font-mono leading-tight transition-opacity ${task.priority && task.priority !== 'none' ? '' : 'opacity-30 hover:opacity-100'}`}
                  style={{ color: priorityColor(task.priority) }}
                  title="Приоритет"
                >
                  {priorityLabel(task.priority)}
                </button>
                {showPrio && (
                  <PriorityPicker
                    current={task.priority}
                    onChange={v => onPriorityChange(task.id, v)}
                    onClose={() => setShowPrio(false)}
                  />
                )}
              </div>
              <h2 className="text-xl font-bold text-[#f0f0f0] leading-tight">{task.title}</h2>
            </div>
            <div className="flex items-center gap-2 flex-wrap text-xs">
              {direction && dirColor && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ color: dirColor, backgroundColor: dirColor + '28' }}>{direction.name}</span>
              )}
              {task.deadline && (
                <span className="text-[#666]">до {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</span>
              )}
              {task.duration_plan && (
                <span className="text-[#666]">{task.duration_plan}ч план</span>
              )}
            </div>
          </div>

          {/* Timer */}
          <div className="mb-3">
            {/* Counter + pulsing dot */}
            <div className="flex items-center gap-2 mb-1">
              {timer.isRunning && (
                <span className="text-[#5060a0] text-xl animate-pulse leading-none">●</span>
              )}
              {timer.isPaused && (
                <span className="text-[#383838] text-xl leading-none">●</span>
              )}
              <div className={`text-7xl font-mono font-bold tabular-nums leading-none ${timer.isPaused ? 'text-[#505050]' : 'text-[#f0f0f0]'}`}>
                {formatElapsed(timer.elapsed)}
              </div>
            </div>

            {/* Progress bar (only when timer has been used and plan is set) */}
            {task.duration_plan != null && timerActive && (
              <div className="w-full h-0.5 bg-[#252525] rounded-full overflow-hidden mb-2">
                <div
                  className="h-full bg-[#5060a0] transition-all duration-500"
                  style={{ width: `${Math.min(100, (timer.elapsed / (task.duration_plan * 3600)) * 100)}%` }}
                />
              </div>
            )}

            {/* Pomodoro indicator */}
            {pomodoroPhase !== 'idle' && (
              <div className={`flex items-center gap-2 mt-2 px-2 py-1 rounded-lg text-xs ${pomodoroPhase === 'break' ? 'bg-[#1a3a1a]' : 'bg-[#1a1a3a]'}`}>
                <span className={pomodoroPhase === 'break' ? 'text-[#4a9a4a]' : 'text-[#8090c8]'}>
                  {pomodoroPhase === 'break' ? '☕ Перерыв' : '🍅 Помодоро'}
                </span>
                <span className="font-mono text-[#f0f0f0]">
                  {padZ(Math.floor(pomodoroRemaining / 60))}:{padZ(pomodoroRemaining % 60)}
                </span>
                <button onClick={onSkipPomodoro} className="ml-auto text-[#555] hover:text-[#999] text-[10px]">пропустить</button>
              </div>
            )}

            {/* Two time lines */}
            <div className="text-xs text-[#666] mt-1">
              {formatTime(todayTime + timer.elapsed)} сегодня
            </div>
            <div className="text-xs text-[#505050]">
              Всего: {formatTime(Math.round((task.duration_fact ?? 0) + timer.elapsed))}
            </div>
          </div>

          {/* Buttons — 3 states */}
          <div className="flex items-center gap-2">
            {!timer.isRunning && !timer.isPaused && (
              <>
                <button
                  onClick={onStart}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] transition-colors rounded text-sm text-white"
                >
                  ▶ Старт
                </button>
                <button
                  onClick={onDone}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#5060a0] hover:text-[#8090c8] transition-colors rounded text-sm text-[#666]"
                >
                  ✓ Готово
                </button>
                <button
                  onClick={onSendToQueue}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#666] hover:text-[#f0f0f0] transition-colors rounded text-sm text-[#666]"
                >
                  ↓ В очередь
                </button>
              </>
            )}

            {timer.isRunning && (
              <>
                <button
                  onClick={onPause}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#252525] hover:bg-[#383838] transition-colors rounded text-sm text-[#f0f0f0]"
                >
                  ⏸ Пауза
                </button>
                <button
                  onClick={onStop}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#666] transition-colors rounded text-sm text-[#666]"
                >
                  ■ Стоп
                </button>
                <button
                  onClick={onDone}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#5060a0] hover:text-[#8090c8] transition-colors rounded text-sm text-[#666]"
                >
                  ✓ Готово
                </button>
                <button
                  onClick={onSendToQueue}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#666] hover:text-[#f0f0f0] transition-colors rounded text-sm text-[#666]"
                >
                  ↓ В очередь
                </button>
              </>
            )}

            {timer.isPaused && (
              <>
                <button
                  onClick={onResume}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] transition-colors rounded text-sm text-white"
                >
                  ▶ Продолжить
                </button>
                <button
                  onClick={onStop}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#666] transition-colors rounded text-sm text-[#666]"
                >
                  ■ Стоп
                </button>
                <button
                  onClick={onDone}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#5060a0] hover:text-[#8090c8] transition-colors rounded text-sm text-[#666]"
                >
                  ✓ Готово
                </button>
                <button
                  onClick={onSendToQueue}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#666] hover:text-[#f0f0f0] transition-colors rounded text-sm text-[#666]"
                >
                  ↓ В очередь
                </button>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}
