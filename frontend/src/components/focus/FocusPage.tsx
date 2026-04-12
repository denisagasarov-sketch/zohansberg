import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import { StepList } from './StepList'
import { Timer } from './Timer'
import { formatDeadline, isOverdue } from '../../utils/time'

const STATUS_COLORS: Record<string, string> = {
  active: 'text-[#3b82f6] bg-[#3b82f6]/10 border-[#3b82f6]/20',
  completed: 'text-[#22c55e] bg-[#22c55e]/10 border-[#22c55e]/20',
  overdue: 'text-[#ef4444] bg-[#ef4444]/10 border-[#ef4444]/20',
  stuck: 'text-[#f59e0b] bg-[#f59e0b]/10 border-[#f59e0b]/20',
  inbox: 'text-[#8b8b9a] bg-[#8b8b9a]/10 border-[#8b8b9a]/20',
  'no-next-step': 'text-[#a855f7] bg-[#a855f7]/10 border-[#a855f7]/20',
}

const STATUS_LABELS: Record<string, string> = {
  active: 'Active', completed: 'Done', overdue: 'Overdue',
  stuck: 'Stuck', inbox: 'Inbox', 'no-next-step': 'No next step',
}

export function FocusPage() {
  const {
    tasks, focusTaskId, setFocusTask, updateTask, deleteTask, addTask,
    directions, subGoals, goals, getGoalByDirection, getSubGoalsByGoal, getTasksBySubGoal,
    selectedDirectionId, setSelectedDirection,
  } = useStore()

  const [showPicker, setShowPicker] = useState(false)

  const task = tasks[focusTaskId]

  if (!task) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-[#4a4a55]">No task selected</p>
        <button
          onClick={() => setShowPicker(true)}
          className="text-sm text-[#3b82f6] border border-[#3b82f6]/30 px-4 py-2 rounded hover:bg-[#3b82f6]/10 transition-colors"
        >
          Select task
        </button>
      </div>
    )
  }

  const dir = directions.find(d => d.id === task.directionId)
  const goal = getGoalByDirection(task.directionId)
  const sg = subGoals[task.subGoalId]
  const deadlineStr = task.deadline ? formatDeadline(task.deadline) : null
  const overdue = isOverdue(task.deadline)

  return (
    <div className="flex flex-col h-full">
      {/* Header breadcrumb */}
      <div className="flex items-center gap-1.5 text-xs text-[#4a4a55] font-mono mb-4 flex-wrap">
        <span className="text-[#2a2a31]">//</span>
        <span>{dir?.name}</span>
        <span className="text-[#2a2a31]">/</span>
        <span className="truncate max-w-[120px]">{goal?.title.slice(0, 30)}…</span>
        <span className="text-[#2a2a31]">/</span>
        <span className="text-[#6b6b7a]">{sg?.title}</span>
      </div>

      {/* Task title + meta */}
      <div className="mb-4">
        <div className="flex items-start gap-3 mb-2">
          <InlineEdit
            value={task.title}
            onSave={(v) => updateTask(task.id, { title: v })}
            className="text-xl font-semibold text-[#e8e8f0] leading-tight flex-1"
          />
          <button
            onClick={() => setShowPicker(!showPicker)}
            className="flex-shrink-0 text-xs text-[#4a4a55] hover:text-[#8b8b9a] border border-[#2a2a31] rounded px-2 py-1 transition-colors font-mono"
          >
            switch
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Status selector */}
          <select
            value={task.status}
            onChange={e => updateTask(task.id, { status: e.target.value as Task['status'] })}
            className={`text-xs border rounded px-2 py-0.5 bg-transparent outline-none cursor-pointer font-mono ${STATUS_COLORS[task.status] ?? ''}`}
          >
            {Object.entries(STATUS_LABELS).map(([k, v]) => (
              <option key={k} value={k} className="bg-[#0a0a0b] text-[#c8c8d4]">{v}</option>
            ))}
          </select>

          {/* Deadline */}
          {task.deadline && (
            <span className={`text-xs font-mono px-2 py-0.5 rounded border ${
              overdue ? 'text-[#ef4444] border-[#ef4444]/30 bg-[#ef4444]/5' : 'text-[#6b6b7a] border-[#2a2a31]'
            }`}>
              {deadlineStr}
            </span>
          )}

          {/* Deadline edit */}
          <input
            type="date"
            value={task.deadline ?? ''}
            onChange={e => updateTask(task.id, { deadline: e.target.value || undefined })}
            className="text-xs text-[#4a4a55] bg-transparent outline-none cursor-pointer w-[120px]"
          />
        </div>
      </div>

      {/* Timer */}
      <div className="mb-5">
        <Timer taskId={task.id} />
      </div>

      {/* Steps header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs uppercase tracking-widest text-[#4a4a55] font-mono">Steps</h3>
        <span className="text-xs text-[#4a4a55] font-mono">
          {task.steps.filter(s => s.completed).length}/{task.steps.length}
        </span>
      </div>

      {/* Step list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <StepList taskId={task.id} />
      </div>

      {/* Task picker */}
      {showPicker && (
        <TaskPicker onSelect={(id) => { setFocusTask(id); setShowPicker(false) }} onClose={() => setShowPicker(false)} />
      )}
    </div>
  )
}

// ─── Task Picker overlay ──────────────────────────────────────────────────────
import type { Task } from '../../types'

function TaskPicker({ onSelect, onClose }: { onSelect: (id: string) => void; onClose: () => void }) {
  const { tasks, directions, subGoals, goals } = useStore()
  const [q, setQ] = useState('')

  const filtered = Object.values(tasks)
    .filter(t => t.status !== 'completed')
    .filter(t => !q || t.title.toLowerCase().includes(q.toLowerCase()))

  return (
    <div className="fixed inset-0 z-50 bg-black/70 flex items-end justify-center" onClick={onClose}>
      <div
        className="bg-[#111113] border border-[#2a2a31] rounded-t-xl w-full max-w-2xl max-h-[70vh] flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        <div className="p-4 border-b border-[#2a2a31]">
          <input
            autoFocus
            type="text"
            placeholder="Search tasks..."
            value={q}
            onChange={e => setQ(e.target.value)}
            className="w-full bg-[#18181b] border border-[#2a2a31] rounded px-3 py-2 text-sm text-[#e8e8f0] outline-none focus:border-[#3b82f6]"
          />
        </div>
        <div className="overflow-y-auto flex-1">
          {filtered.map(t => {
            const dir = directions.find(d => d.id === t.directionId)
            const sg = subGoals[t.subGoalId]
            return (
              <button
                key={t.id}
                onClick={() => onSelect(t.id)}
                className="w-full text-left px-4 py-3 border-b border-[#1f1f23] hover:bg-[#1f1f23] transition-colors"
              >
                <div className="text-sm text-[#c8c8d4]">{t.title}</div>
                <div className="text-xs text-[#4a4a55] mt-0.5 font-mono">
                  {dir?.name} · {sg?.title}
                </div>
              </button>
            )
          })}
          {filtered.length === 0 && (
            <div className="p-6 text-center text-[#4a4a55] text-sm">No tasks found</div>
          )}
        </div>
      </div>
    </div>
  )
}
