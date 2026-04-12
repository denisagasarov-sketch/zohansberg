import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import { formatDuration, formatDeadline, isOverdue } from '../../utils/time'
import type { TaskStatus } from '../../types'

const STATUS_DOT: Record<TaskStatus, string> = {
  active:         'bg-[#3b82f6]',
  completed:      'bg-[#22c55e]',
  overdue:        'bg-[#ef4444]',
  stuck:          'bg-[#f59e0b]',
  inbox:          'bg-[#4a4a55]',
  'no-next-step': 'bg-[#a855f7]',
}

interface Props {
  taskId: string
}

export function TaskItem({ taskId }: Props) {
  const { tasks, updateTask, deleteTask, setFocusTask, setPage, totalTimeForTask } = useStore()
  const task = tasks[taskId]
  const [expanded, setExpanded] = useState(false)

  if (!task) return null

  const time = totalTimeForTask(taskId)
  const deadlineStr = task.deadline ? formatDeadline(task.deadline) : null
  const overdue = isOverdue(task.deadline)
  const completedSteps = task.steps.filter(s => s.completed).length

  return (
    <div className={`border-b border-[#111113] last:border-0 ${task.status === 'completed' ? 'opacity-50' : ''}`}>
      <div className="group flex items-center gap-3 px-8 py-2.5 hover:bg-[#111113]/50 transition-colors">
        {/* Status dot */}
        <span className={`flex-shrink-0 w-1.5 h-1.5 rounded-full ${STATUS_DOT[task.status]}`} />

        {/* Expand toggle */}
        {task.steps.length > 0 && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="flex-shrink-0 text-[#2a2a31] hover:text-[#4a4a55] text-xs transition-colors"
          >
            <span className={`inline-block transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
          </button>
        )}

        {/* Title */}
        <div className="flex-1 min-w-0">
          <InlineEdit
            value={task.title}
            onSave={(v) => updateTask(taskId, { title: v })}
            className={`text-sm ${task.status === 'completed' ? 'line-through text-[#4a4a55]' : 'text-[#c8c8d4]'}`}
          />
        </div>

        {/* Meta row */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {task.steps.length > 0 && (
            <span className="text-xs font-mono text-[#4a4a55]">
              {completedSteps}/{task.steps.length}
            </span>
          )}
          {time > 0 && (
            <span className="text-xs font-mono text-[#4a4a55]">{formatDuration(time)}</span>
          )}
          {deadlineStr && (
            <span className={`text-xs font-mono ${overdue ? 'text-[#ef4444]' : 'text-[#4a4a55]'}`}>
              {deadlineStr}
            </span>
          )}

          {/* Focus link */}
          <button
            onClick={() => { setFocusTask(taskId); setPage(1) }}
            className="opacity-0 group-hover:opacity-100 text-[#3b82f6] text-xs border border-[#3b82f6]/30 px-1.5 py-0.5 rounded hover:bg-[#3b82f6]/10 transition-all"
          >
            →
          </button>

          {/* Status selector */}
          <select
            value={task.status}
            onChange={e => updateTask(taskId, { status: e.target.value as TaskStatus })}
            className="opacity-0 group-hover:opacity-100 text-xs bg-[#111113] border border-[#2a2a31] rounded px-1 py-0.5 text-[#8b8b9a] outline-none cursor-pointer transition-opacity"
          >
            {(['active','completed','overdue','stuck','inbox','no-next-step'] as TaskStatus[]).map(s => (
              <option key={s} value={s} className="bg-[#0a0a0b]">{s}</option>
            ))}
          </select>

          {/* Delete */}
          <button
            onClick={() => deleteTask(taskId)}
            className="opacity-0 group-hover:opacity-100 text-[#4a4a55] hover:text-[#ef4444] text-xs transition-all"
          >
            ×
          </button>
        </div>
      </div>

      {/* Steps preview */}
      {expanded && task.steps.length > 0 && (
        <div className="px-12 pb-2">
          {task.steps.slice().sort((a, b) => a.order - b.order).map(step => (
            <div key={step.id} className="flex items-center gap-2 py-0.5">
              <span className={`w-3 h-3 rounded-sm border flex items-center justify-center flex-shrink-0 ${
                step.completed ? 'border-[#22c55e] text-[#22c55e]' : 'border-[#2a2a31]'
              }`}>
                {step.completed && <span className="text-[8px]">✓</span>}
              </span>
              <span className={`text-xs ${step.completed ? 'line-through text-[#2a2a31]' : 'text-[#6b6b7a]'}`}>
                {step.title}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
