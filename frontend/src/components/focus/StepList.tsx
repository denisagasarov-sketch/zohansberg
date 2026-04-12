import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import type { Step } from '../../types'

interface Props {
  taskId: string
}

export function StepList({ taskId }: Props) {
  const { tasks, toggleStep, updateStep, deleteStep, addStep, reorderSteps } = useStore()
  const task = tasks[taskId]
  const [newStepTitle, setNewStepTitle] = useState('')
  const [dragging, setDragging] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState<string | null>(null)

  if (!task) return null

  const steps = [...task.steps].sort((a, b) => a.order - b.order)
  const completedCount = steps.filter(s => s.completed).length
  const nextActive = steps.find(s => !s.completed)

  const handleAdd = () => {
    const t = newStepTitle.trim()
    if (!t) return
    addStep(taskId, t)
    setNewStepTitle('')
  }

  const handleDragStart = (id: string) => setDragging(id)
  const handleDragOver = (e: React.DragEvent, id: string) => {
    e.preventDefault()
    setDragOver(id)
  }
  const handleDrop = (e: React.DragEvent, targetId: string) => {
    e.preventDefault()
    if (!dragging || dragging === targetId) { setDragging(null); setDragOver(null); return }
    const fromIdx = steps.findIndex(s => s.id === dragging)
    const toIdx = steps.findIndex(s => s.id === targetId)
    const reordered = [...steps]
    const [moved] = reordered.splice(fromIdx, 1)
    reordered.splice(toIdx, 0, moved)
    reorderSteps(taskId, reordered.map((s, i) => ({ ...s, order: i })))
    setDragging(null)
    setDragOver(null)
  }

  return (
    <div className="flex flex-col gap-1">
      {/* Progress bar */}
      {steps.length > 0 && (
        <div className="flex items-center gap-3 mb-3">
          <div className="flex-1 h-1 bg-[#1f1f23] rounded-full overflow-hidden">
            <div
              className="h-full bg-[#22c55e] transition-all duration-300"
              style={{ width: `${steps.length ? (completedCount / steps.length) * 100 : 0}%` }}
            />
          </div>
          <span className="text-xs font-mono text-[#4a4a55] tabular-nums whitespace-nowrap">
            {completedCount}/{steps.length}
          </span>
        </div>
      )}

      {/* Steps */}
      {steps.map((step) => {
        const isNext = step.id === nextActive?.id
        const isDragged = dragging === step.id
        const isOver = dragOver === step.id

        return (
          <div
            key={step.id}
            draggable
            onDragStart={() => handleDragStart(step.id)}
            onDragOver={(e) => handleDragOver(e, step.id)}
            onDrop={(e) => handleDrop(e, step.id)}
            onDragEnd={() => { setDragging(null); setDragOver(null) }}
            className={`
              group flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-all
              ${isDragged ? 'opacity-30' : ''}
              ${isOver ? 'border-[#3b82f6]/50 bg-[#3b82f6]/5' : ''}
              ${isNext && !step.completed
                ? 'border-[#3a3a44] bg-[#1f1f23]'
                : step.completed
                  ? 'border-[#1f1f23] bg-transparent'
                  : 'border-[#1f1f23] bg-[#111113]/50'
              }
            `}
          >
            {/* Drag handle */}
            <span className="cursor-grab opacity-0 group-hover:opacity-30 text-[#4a4a55] select-none text-xs flex-shrink-0">
              ⠿
            </span>

            {/* Checkbox */}
            <button
              onClick={() => toggleStep(taskId, step.id)}
              className={`flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center transition-all ${
                step.completed
                  ? 'border-[#22c55e] bg-[#22c55e]/15 text-[#22c55e]'
                  : isNext
                    ? 'border-[#3b82f6]/60 hover:border-[#3b82f6]'
                    : 'border-[#2a2a31] hover:border-[#3a3a44]'
              }`}
            >
              {step.completed && <span className="text-[10px]">✓</span>}
            </button>

            {/* Title */}
            <div className="flex-1 min-w-0">
              <InlineEdit
                value={step.title}
                onSave={(v) => updateStep(taskId, step.id, { title: v })}
                className={`text-sm ${
                  step.completed
                    ? 'text-[#4a4a55] line-through'
                    : isNext
                      ? 'text-[#e8e8f0] font-medium'
                      : 'text-[#8b8b9a]'
                }`}
              />
            </div>

            {/* Active badge */}
            {isNext && (
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#3b82f6] bg-[#3b82f6]/10 border border-[#3b82f6]/20 px-1.5 py-0.5 rounded flex-shrink-0">
                next
              </span>
            )}

            {/* Delete */}
            <button
              onClick={() => deleteStep(taskId, step.id)}
              className="opacity-0 group-hover:opacity-100 text-[#4a4a55] hover:text-[#ef4444] transition-all text-xs flex-shrink-0 ml-1"
            >
              ×
            </button>
          </div>
        )
      })}

      {/* Add step */}
      <div className="flex items-center gap-2 mt-2">
        <input
          type="text"
          value={newStepTitle}
          onChange={e => setNewStepTitle(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleAdd() }}
          placeholder="+ Add step..."
          className="flex-1 bg-transparent border-b border-[#2a2a31] focus:border-[#3b82f6] outline-none text-sm text-[#8b8b9a] placeholder-[#2a2a31] py-1.5 transition-colors"
        />
        {newStepTitle.trim() && (
          <button
            onClick={handleAdd}
            className="text-xs text-[#3b82f6] hover:text-[#60a5fa] font-mono"
          >
            Add
          </button>
        )}
      </div>
    </div>
  )
}
