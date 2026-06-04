import { useRef, useState } from 'react'
import type { Task, Direction } from '../types'
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
}

const DRAG_KEY = 'dayplan-task-id'

export default function DayPlanBlock({ planTaskIds, tasks, directions, onTakeNow, onMarkDone, onTaskClick, onReorder }: Props) {
  const planTasks = planTaskIds
    .map(id => tasks.find(t => t.id === id))
    .filter((t): t is Task => !!t && !t.done_at && !t.deleted_at && t.slot !== 'now')

  const [draggingId, setDraggingId] = useState<number | null>(null)
  const draggingIdRef = useRef<number | null>(null)

  if (planTasks.length === 0) return null

  const handleDragStart = (e: React.DragEvent, taskId: number) => {
    e.stopPropagation()
    draggingIdRef.current = taskId
    setDraggingId(taskId)
    e.dataTransfer.setData(DRAG_KEY, String(taskId))
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    e.stopPropagation()
    const sourceId = parseInt(e.dataTransfer.getData(DRAG_KEY), 10)
    draggingIdRef.current = null
    setDraggingId(null)
    if (isNaN(sourceId) || sourceId === targetId) return
    const ids = planTasks.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) ids.push(sourceId)
    else ids.splice(targetIdx, 0, sourceId)
    onReorder(ids)
  }

  const handleDragEnd = () => { draggingIdRef.current = null; setDraggingId(null) }

  return (
    <div>
      <div className="border-t border-[#252525] border-dashed my-3" />
      <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
        <div className="px-4 pt-3 pb-1">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">На сегодня</div>
        </div>
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
                onDrop={e => handleDrop(e, task.id)}
                onDragEnd={handleDragEnd}
                className={`group flex items-center gap-3 px-4 py-2 hover:bg-[#252525]/40 transition-colors ${draggingId === task.id ? 'opacity-40' : ''}`}
              >
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
                {dir && c && (
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0 font-medium"
                    style={{ color: c, backgroundColor: c + '28' }}
                  >
                    {dir.name}
                  </span>
                )}
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
      </div>
    </div>
  )
}
