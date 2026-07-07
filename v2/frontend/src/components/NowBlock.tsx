import { useState } from 'react'
import type { Task, Direction } from '../types'
import SubtaskList from './SubtaskList'
import type { TimerState } from '../hooks/useTimer'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getDirectionColor } from '../utils/directionColors'
import { priorityLabel, priorityColor } from '../utils/priority'
import { PriorityPicker, prioritiesOn } from './PriorityPicker'

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
  lastSessionNote?: { note: string; when: string } | null
  onStartStep?: (subtaskId: number) => void
}

function padZ(n: number) { return String(n).padStart(2, '0') }

function formatElapsed(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return h > 0 ? `${h}:${padZ(m)}:${padZ(sec)}` : `${padZ(m)}:${padZ(sec)}`
}

function formatTime(s: number): string {
  if (s < 60) return `${s}с`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

export default function NowBlock({ task, directions, timer, todayTime, onStart, onStop, onPause, onResume, onDone, onSendToQueue, onTaskClick, onAddTask, onDropTask, onPriorityChange, pomodoroPhase = 'idle', pomodoroRemaining = 0, onSkipPomodoro, lastSessionNote, onStartStep }: Props) {
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
      className={`relative rounded-2xl border select-none transition-all duration-300 overflow-hidden
        ${isDragOver ? 'border-accent' : timer.isRunning ? 'border-accent/35' : 'border-border-strong'}
        ${timer.isRunning ? 'bg-[#1d1a16]' : 'bg-card'}`}
      style={timer.isRunning ? { boxShadow: '0 0 48px rgba(224,164,88,0.07), 0 8px 32px rgba(0,0,0,0.4)' } : { boxShadow: '0 8px 28px rgba(0,0,0,0.35)' }}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Тонкая янтарная нить сверху, когда идёт фокус */}
      {timer.isRunning && (
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-transparent via-accent/70 to-transparent" />
      )}

      {!task ? (
        <div className="py-14 text-center">
          <div className="text-text-muted text-sm">Нет активной задачи</div>
          <div className="text-text-faint text-xs mt-1.5">
            Перетащите сюда задачу или возьмите из «Следом» ·{' '}
            <button onClick={onAddTask} className="text-text-muted hover:text-accent transition-colors underline underline-offset-2">создать новую</button>
          </div>
        </div>
      ) : (
        <>
          <div className="flex gap-8 px-6 pt-5 pb-4 max-lg:flex-col max-lg:gap-4">
            {/* Левая часть: задача */}
            <div
              draggable
              onDragStart={e => {
                e.dataTransfer.setData(DRAG_TASK_KEY, String(task.id))
                e.dataTransfer.effectAllowed = 'move'
              }}
              className="flex-1 min-w-0 cursor-pointer group"
              onClick={() => onTaskClick(task)}
            >
              <div className="flex items-center gap-2.5 mb-2.5 text-[11px]">
                <span className="section-label">Сейчас</span>
                {direction && dirColor && (
                  <span className="px-2 py-0.5 rounded-full font-medium" style={{ color: dirColor, backgroundColor: dirColor + '22' }}>{direction.name}</span>
                )}
                {task.deadline && (
                  <span className="text-text-secondary">до {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</span>
                )}
                {task.duration_plan && (
                  <span className="text-text-secondary">план {task.duration_plan}ч</span>
                )}
              </div>

              <div className="flex items-start gap-2.5">
                <div className={`relative shrink-0 mt-[7px] ${prioritiesOn() ? '' : 'hidden'}`}>
                  <button
                    onClick={e => { e.stopPropagation(); setShowPrio(v => !v) }}
                    className={`text-[15px] font-mono leading-tight transition-opacity ${task.priority && task.priority !== 'none' ? '' : 'opacity-30 hover:opacity-100'}`}
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
                <h2 className="text-[26px] font-semibold text-text leading-snug tracking-tight group-hover:text-white transition-colors">{task.title}</h2>
              </div>

              {task.notes && (
                <p className="text-xs text-text-secondary mt-3 whitespace-pre-wrap leading-relaxed max-h-20 overflow-y-auto border-l-2 border-border-strong pl-2.5">
                  {task.notes}
                </p>
              )}

              {lastSessionNote && (
                <div className="mt-3 bg-bg-sunken/60 border border-border rounded-lg px-3 py-2">
                  <div className="text-[10px] text-accent/80 font-semibold uppercase tracking-[0.1em]">
                    В прошлый раз
                    <span className="text-text-faint font-normal normal-case tracking-normal">
                      {' · '}
                      {new Date(lastSessionNote.when).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                    </span>
                  </div>
                  <p className="text-xs text-text-secondary mt-1 whitespace-pre-wrap leading-relaxed max-h-16 overflow-y-auto">
                    {lastSessionNote.note}
                  </p>
                </div>
              )}
            </div>

            {/* Правая часть: таймер и управление */}
            <div className="shrink-0 flex flex-col items-end max-lg:items-start gap-2 min-w-[280px]">
              <div className="flex items-baseline gap-3">
                {timer.isRunning && <span className="text-accent text-base animate-pulse leading-none">●</span>}
                {timer.isPaused && <span className="text-text-faint text-base leading-none">●</span>}
                <div className={`text-[56px] font-mono font-semibold tabular-nums leading-none tracking-tight transition-colors ${timer.isPaused ? 'text-text-muted' : timer.isRunning ? 'text-text' : 'text-text-secondary'}`}>
                  {formatElapsed(timer.elapsed)}
                </div>
              </div>

              {task.duration_plan != null && timerActive && (
                <div className="w-full h-[3px] bg-border rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent/80 transition-all duration-500"
                    style={{ width: `${Math.min(100, (timer.elapsed / (task.duration_plan * 3600)) * 100)}%` }}
                  />
                </div>
              )}

              {pomodoroPhase !== 'idle' && (
                <div className={`flex items-center gap-2 px-2.5 py-1 rounded-lg text-xs w-full ${pomodoroPhase === 'break' ? 'bg-[#20281d]' : 'bg-accent/10'}`}>
                  <span className={pomodoroPhase === 'break' ? 'text-ok' : 'text-accent-light'}>
                    {pomodoroPhase === 'break' ? 'Перерыв' : 'Помодоро'}
                  </span>
                  <span className="font-mono text-text tabular-nums">
                    {padZ(Math.floor(pomodoroRemaining / 60))}:{padZ(pomodoroRemaining % 60)}
                  </span>
                  <button onClick={onSkipPomodoro} className="ml-auto text-text-muted hover:text-text-secondary text-[10px]">пропустить</button>
                </div>
              )}

              <div className="text-xs text-text-secondary tabular-nums">
                {formatTime(todayTime + timer.elapsed)} сегодня
                <span className="text-text-muted"> · всего {formatTime(Math.round((task.duration_fact ?? 0) + timer.elapsed))}</span>
              </div>

              <div className="flex items-center gap-2 mt-1 flex-wrap justify-end max-lg:justify-start">
                {!timer.isRunning && !timer.isPaused && (
                  <>
                    <button onClick={onStart} className="btn-primary">▶ Старт</button>
                    <button onClick={onDone} className="btn-outline hover:!text-accent-light hover:!border-accent/50">✓ Готово</button>
                    <button onClick={onSendToQueue} className="btn-ghost">↓ В очередь</button>
                  </>
                )}
                {timer.isRunning && (
                  <>
                    <button onClick={onPause} className="btn bg-raised text-text hover:bg-border-strong">⏸ Пауза</button>
                    <button onClick={onStop} className="btn-outline">■ Стоп</button>
                    <button onClick={onDone} className="btn-outline hover:!text-accent-light hover:!border-accent/50">✓ Готово</button>
                    <button onClick={onSendToQueue} className="btn-ghost">↓ В очередь</button>
                  </>
                )}
                {timer.isPaused && (
                  <>
                    <button onClick={onResume} className="btn-primary">▶ Продолжить</button>
                    <button onClick={onStop} className="btn-outline">■ Стоп</button>
                    <button onClick={onDone} className="btn-outline hover:!text-accent-light hover:!border-accent/50">✓ Готово</button>
                    <button onClick={onSendToQueue} className="btn-ghost">↓ В очередь</button>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Шаги задачи — разбей на короткие подходы. «▶ подход» запускает таймер на шаг. */}
          <div className="px-6 pb-4 pt-3 border-t border-border">
            <div className="section-label mb-2">Шаги</div>
            <SubtaskList
              key={task.id}
              taskId={task.id}
              compact
              onFocusStep={!timerActive && onStartStep ? (s) => onStartStep(s.id) : undefined}
              onChanged={() => window.dispatchEvent(new CustomEvent('gamification-updated'))}
            />
          </div>
        </>
      )}
    </div>
  )
}
