import { useRef, useState } from 'react'
import type { Task, Direction, Recommendation } from '../types'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getQuadrant } from '../utils/quadrant'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onTaskClick: (task: Task) => void
  recommendation: Recommendation | null
  onReorder: (slot: string, orderedIds: number[]) => void
  onDropFromOutside: (taskId: number) => void
  focusMode?: boolean
  nowTaskId?: number
}

export default function NextBlock({ tasks, directions, onTaskClick, recommendation, onReorder, onDropFromOutside, focusMode, nowTaskId }: Props) {
  function focusDimmed(task: Task) { return !!(focusMode && task.id !== nowTaskId) }
  const nextTasks = (tasks ?? []).filter(t => t.slot === 'next' && !t.done_at && !t.deleted_at).slice(0, 5)
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const isNextTask = (id: number) => nextTasks.some(t => t.id === id)

  const handleDragStart = (e: React.DragEvent, taskId: number) => {
    e.stopPropagation()
    draggingIdRef.current = taskId
    setDraggingId(taskId)
    e.dataTransfer.setData(DRAG_TASK_KEY, String(taskId))
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setIsDragOver(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    // Only clear if leaving the block itself, not child elements
    if (!(e.currentTarget as Element).contains(e.relatedTarget as Node)) {
      setIsDragOver(false)
    }
  }

  const handleDrop = (e: React.DragEvent, targetId?: number) => {
    e.preventDefault()
    setIsDragOver(false)
    const raw = e.dataTransfer.getData(DRAG_TASK_KEY)
    const sourceId = parseInt(raw, 10)
    if (isNaN(sourceId)) { draggingIdRef.current = null; setDraggingId(null); return }

    // Drop from outside the next-list → move to 'next' slot
    if (!isNextTask(sourceId)) {
      draggingIdRef.current = null
      setDraggingId(null)
      onDropFromOutside(sourceId)
      return
    }

    // Reorder within next-list
    draggingIdRef.current = null
    setDraggingId(null)
    if (!targetId || sourceId === targetId) return
    const ids = nextTasks.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) ids.push(sourceId)
    else ids.splice(targetIdx, 0, sourceId)
    onReorder('next', ids)
  }

  const handleDragEnd = () => {
    draggingIdRef.current = null
    setDraggingId(null)
    setIsDragOver(false)
  }

  return (
    <div>
      <div className="relative flex items-center mb-3">
        <div className="flex-1 border-t border-[#252525] border-dashed" />
        <span className="px-3 text-[10px] font-semibold tracking-widest text-[#383838] uppercase whitespace-nowrap">затем</span>
        <div className="flex-1 border-t border-[#252525] border-dashed" />
      </div>

      <div
        className={`bg-[#1c1c1c] border rounded-lg overflow-hidden transition-colors ${isDragOver ? 'border-[#5060a0]' : 'border-[#252525]'}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={e => handleDrop(e)}
      >
        <div className="px-4 pt-3 pb-1">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Следом</div>
        </div>

        {nextTasks.length === 0 ? (
          isDragOver ? (
            <div className="px-4 pb-3 text-xs text-[#5060a0]">Отпустите, чтобы поставить следом</div>
          ) : recommendation ? (
            <div className="px-4 pb-3 text-xs text-[#666]">Нет задач в очереди</div>
          ) : (
            <div className="px-4 pb-3 text-xs text-[#666]">Очередь пуста</div>
          )
        ) : (
          <ul className="divide-y divide-[#252525]">
            {nextTasks.map((task, idx) => {
              const q = getQuadrant(task.is_important ?? 0, task.is_urgent ?? 0)
              return (
                <li
                  key={task.id}
                  draggable
                  onDragStart={e => handleDragStart(e, task.id)}
                  onDragOver={e => { e.preventDefault(); e.stopPropagation() }}
                  onDrop={e => { e.stopPropagation(); handleDrop(e, task.id) }}
                  onDragEnd={handleDragEnd}
                  className={`flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-[3px] ${draggingId === task.id ? 'opacity-40' : ''} ${focusDimmed(task) ? 'opacity-30 blur-[3px]' : ''}`}
                  style={{ borderLeftColor: q.border }}
                  onClick={() => onTaskClick(task)}
                >
                  <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
                  <span className="text-[#383838] text-xs font-mono w-4 shrink-0">{idx + 1}</span>
                  <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
                  {task.direction_id != null && (() => {
                    const dir = directions.find(d => d.id === task.direction_id)
                    if (!dir) return null
                    const c = getDirectionColor(dir.id)
                    return (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0 font-medium"
                        style={{ color: c, backgroundColor: c + '28' }}
                      >
                        {dir.name}
                      </span>
                    )
                  })()}
                  <span className="text-[10px] shrink-0" style={{ color: q.color }}>{q.short}</span>
                  {task.duration_plan && (
                    <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
