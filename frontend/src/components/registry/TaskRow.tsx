import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import { formatDuration, formatDeadline, isOverdue } from '../../utils/time'
import type { TaskStatus } from '../../types'

const STATUS_CONFIG: Record<TaskStatus, { label: string; cls: string }> = {
  active:          { label: 'Active',       cls: 'text-[#3b82f6]  border-[#3b82f6]/30  bg-[#3b82f6]/5' },
  completed:       { label: 'Done',         cls: 'text-[#22c55e]  border-[#22c55e]/30  bg-[#22c55e]/5' },
  overdue:         { label: 'Overdue',      cls: 'text-[#ef4444]  border-[#ef4444]/30  bg-[#ef4444]/5' },
  stuck:           { label: 'Stuck',        cls: 'text-[#f59e0b]  border-[#f59e0b]/30  bg-[#f59e0b]/5' },
  inbox:           { label: 'Inbox',        cls: 'text-[#6b6b7a]  border-[#6b6b7a]/30  bg-transparent' },
  'no-next-step':  { label: 'No next step', cls: 'text-[#a855f7]  border-[#a855f7]/30  bg-[#a855f7]/5' },
}

export function TaskRow({ taskId }: { taskId: string }) {
  const { tasks, directions, subGoals, updateTask, deleteTask, setFocusTask, setPage, totalTimeForTask } = useStore()
  const task = tasks[taskId]
  const [expanded, setExpanded] = useState(false)
  const [editingDeadline, setEditingDeadline] = useState(false)

  if (!task) return null

  const dir = directions.find(d => d.id === task.directionId)
  const sg = subGoals[task.subGoalId]
  const time = totalTimeForTask(taskId)
  const deadlineStr = task.deadline ? formatDeadline(task.deadline) : null
  const overdue = isOverdue(task.deadline)
  const statusCfg = STATUS_CONFIG[task.status]
  const completedSteps = task.steps.filter(s => s.completed).length
  const hasSteps = task.steps.length > 0
  const nextStep = task.steps.find(s => !s.completed)

  return (
    <>
      <div
        className={`group grid grid-cols-[1fr_100px_90px_80px_64px] gap-2 px-3 py-2.5 border-b border-[#111113] hover:bg-[#0f0f11] transition-colors items-center cursor-pointer ${
          task.status === 'completed' ? 'opacity-40' : ''
        }`}
        onClick={() => hasSteps && setExpanded(!expanded)}
      >
        {/* Title */}
        <div className="flex items-center gap-2 min-w-0" onClick={e => e.stopPropagation()}>
          {hasSteps && (
            <span className={`text-[10px] text-[#2a2a31] flex-shrink-0 group-hover:text-[#4a4a55] transition-colors ${expanded ? 'rotate-90 inline-block' : ''}`}>
              ▶
            </span>
          )}
          <div className="min-w-0 flex-1">
            <InlineEdit
              value={task.title}
              onSave={(v) => updateTask(taskId, { title: v })}
              className={`text-sm ${task.status === 'completed' ? 'line-through text-[#4a4a55]' : 'text-[#c8c8d4]'}`}
            />
            {nextStep && !expanded && (
              <div className="text-xs text-[#2a2a31] mt-0.5 truncate">→ {nextStep.title}</div>
            )}
          </div>
        </div>

        {/* Direction / Sub-goal */}
        <div className="min-w-0">
          <div className="text-xs text-[#4a4a55] font-mono truncate">{dir?.name}</div>
          <div className="text-xs text-[#2a2a31] truncate">{sg?.title}</div>
        </div>

        {/* Status */}
        <div onClick={e => e.stopPropagation()}>
          <select
            value={task.status}
            onChange={e => updateTask(taskId, { status: e.target.value as TaskStatus })}
            className={`text-xs border rounded px-1.5 py-0.5 bg-transparent outline-none cursor-pointer font-mono w-full ${statusCfg.cls}`}
          >
            {Object.entries(STATUS_CONFIG).map(([k, v]) => (
              <option key={k} value={k} className="bg-[#0a0a0b] text-[#c8c8d4]">{v.label}</option>
            ))}
          </select>
        </div>

        {/* Deadline */}
        <div onClick={e => e.stopPropagation()}>
          {editingDeadline ? (
            <input
              autoFocus
              type="date"
              value={task.deadline ?? ''}
              onChange={e => updateTask(taskId, { deadline: e.target.value || undefined })}
              onBlur={() => setEditingDeadline(false)}
              className="text-xs bg-[#111113] border border-[#3b82f6]/50 rounded px-1 py-0.5 outline-none text-[#c8c8d4] w-full"
            />
          ) : (
            <button
              onClick={() => setEditingDeadline(true)}
              className={`text-xs font-mono ${
                deadlineStr
                  ? overdue ? 'text-[#ef4444]' : 'text-[#6b6b7a]'
                  : 'text-[#2a2a31] hover:text-[#4a4a55]'
              }`}
            >
              {deadlineStr ?? '—'}
            </button>
          )}
        </div>

        {/* Time + actions */}
        <div className="flex items-center justify-end gap-1" onClick={e => e.stopPropagation()}>
          <span className="text-xs font-mono text-[#4a4a55]">{time > 0 ? formatDuration(time) : '—'}</span>
          <button
            onClick={() => { setFocusTask(taskId); setPage(1) }}
            className="opacity-0 group-hover:opacity-100 text-[#3b82f6] text-xs ml-1 transition-opacity"
            title="Open in Focus"
          >
            →
          </button>
          <button
            onClick={() => deleteTask(taskId)}
            className="opacity-0 group-hover:opacity-100 text-[#4a4a55] hover:text-[#ef4444] text-xs transition-opacity"
          >
            ×
          </button>
        </div>
      </div>

      {/* Expanded steps */}
      {expanded && hasSteps && (
        <div className="bg-[#0f0f11] border-b border-[#111113] px-10 py-2">
          {task.steps.slice().sort((a, b) => a.order - b.order).map(step => (
            <div key={step.id} className="flex items-center gap-2 py-1">
              <span className={`w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0 text-[9px] ${
                step.completed ? 'border-[#22c55e] text-[#22c55e]' : 'border-[#2a2a31] text-transparent'
              }`}>
                {step.completed ? '✓' : ''}
              </span>
              <span className={`text-xs ${step.completed ? 'line-through text-[#2a2a31]' : 'text-[#6b6b7a]'}`}>
                {step.title}
              </span>
            </div>
          ))}
          <div className="text-xs text-[#2a2a31] mt-1 font-mono">
            {completedSteps}/{task.steps.length} steps
          </div>
        </div>
      )}
    </>
  )
}
