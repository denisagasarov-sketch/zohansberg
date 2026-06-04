import { useRef, useState } from 'react'
import type { Task, Direction } from '../types'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getDirectionColor } from '../utils/directionColors'
import { priorityLabel, priorityColor } from '../utils/priority'

interface Props {
  planTaskIds: number[]
  tasks: Task[]
  directions: Direction[]
  onTakeNow: (taskId: number) => void
  onMarkDone: (taskId: number) => void
  onTaskClick: (task: Task) => void
  onReorder: (newIds: number[]) => void
  onAddToPlan: (taskId: number) => void
}

// Internal reorder uses its own key; tasks dragged in from DirectionsPanel use DRAG_TASK_KEY
const DRAG_KEY = 'dayplan-task-id'

export default function DayPlanBlock({ planTaskIds, tasks, directions, onTakeNow, onMarkDone, onTaskClick, onReorder, onAddToPlan }: Props) {
  const planTasks = planTaskIds
    .map(id => tasks.find(t => t.id === id))
    .filter((t): t is Task => !!t && !t.done_at && !t.deleted_at && t.slot !== 'now')

  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)
  const draggingIdRef = useRef<number | null>(null)

  const planIdSet = new Set(planTasks.map(t => t.id))

  const handleDragStart = (e: React.DragEvent, taskId: number) => {
    e.stopPropagation()
    draggingIdRef.current = taskId
    setDraggingId(taskId)
    e.dataTransfer.setData(DRAG_KEY, String(taskId))
    // Also expose the shared key so the task can be dragged out into Сейчас/Следом/directions
    e.dataTransfer.setData(DRAG_TASK_KEY, String(taskId))
    e.dataTransfer.effectAllowed = 'move'
  }

  // Drop on a specific row: internal reorder, or external add positioned before target
  const handleRowDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragOver(false)
    const internalId = parseInt(e.dataTransfer.getData(DRAG_KEY), 10)
    if (!isNaN(internalId)) {
      draggingIdRef.current = null
      setDraggingId(null)
      if (internalId === targetId) return
      const ids = planTasks.map(t => t.id).filter(id => id !== internalId)
      const idx = ids.indexOf(targetId)
      if (idx === -1) ids.push(internalId)
      else ids.splice(idx, 0, internalId)
      onReorder(ids)
      return
    }
    // External task from DirectionsPanel
    const externalId = parseInt(e.dataTransfer.getData(DRAG_TASK_KEY), 10)
    if (!isNaN(externalId) && !planIdSet.has(externalId)) onAddToPlan(externalId)
  }

  // Drop on the container (empty area): external add to the end
  const handleContainerDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
    const internalId = parseInt(e.dataTransfer.getData(DRAG_KEY), 10)
    if (!isNaN(internalId)) return // internal reorder handled by row
    const externalId = parseInt(e.dataTransfer.getData(DRAG_TASK_KEY), 10)
    if (!isNaN(externalId) && !planIdSet.has(externalId)) onAddToPlan(externalId)
  }

  const handleDragEnd = () => { draggingIdRef.current = null; setDraggingId(null); setIsDragOver(false) }

  return (
    <div>
      <div className="border-t border-[#252525] border-dashed my-3" />
      <div
        className={`bg-[#1c1c1c] border rounded-lg overflow-hidden transition-colors ${isDragOver ? 'border-[#5060a0]' : 'border-[#252525]'}`}
        onDragOver={e => { e.preventDefault(); setIsDragOver(true) }}
        onDragLeave={e => { if (!(e.currentTarget as Element).contains(e.relatedTarget as Node)) setIsDragOver(false) }}
        onDrop={handleContainerDrop}
      >
        <div className="px-4 pt-3 pb-1">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">На сегодня</div>
        </div>

        {planTasks.length === 0 ? (
          <div className="px-4 pb-3 text-xs text-[#555]">
            {isDragOver ? 'Отпустите, чтобы добавить в план' : 'Перетащите задачи из направлений'}
          </div>
        ) : (
          <ul className="divide-y divide-[#252525]">
            {planTasks.map(task => {
              const dir = task.direction_id != null ? directions.find(d => d.id === task.direction_id) : null
              const c = dir ? getDirectionColor(dir.id) : null
              return (
                <li
                  key={task.id}
                  draggable
                  onDragStart={e => handleDragStart(e, task.id)}
                  onDragOver={e => { e.preventDefault(); e.stopPropagation() }}
                  onDrop={e => handleRowDrop(e, task.id)}
                  onDragEnd={handleDragEnd}
                  className={`group relative flex items-center gap-3 px-4 py-2 hover:bg-[#252525]/40 transition-colors ${draggingId === task.id ? 'opacity-40' : ''}`}
                >
                  {c && <div className="absolute left-0 top-0 bottom-0 w-1 rounded-r" style={{ backgroundColor: c }} />}
                  <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
                  {task.priority && task.priority !== 'none' && (
                    <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>
                      {priorityLabel(task.priority)}
                    </span>
                  )}
                  <span
                    className="flex-1 text-sm text-[#f0f0f0] truncate cursor-pointer"
                    onClick={() => onTaskClick(task)}
                  >
                    {task.title}
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); onTakeNow(task.id) }}
                    className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-[10px] leading-none shrink-0 transition-opacity px-0.5"
                    title="Взять сейчас"
                  >▶</button>
                  <button
                    onClick={e => { e.stopPropagation(); onMarkDone(task.id) }}
                    className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-xs leading-none shrink-0 transition-opacity px-0.5"
                    title="Выполнено"
                  >✓</button>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
