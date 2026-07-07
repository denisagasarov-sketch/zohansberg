import { useRef, useState } from 'react'
import type { Task, Direction } from '../types'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getDirectionColor } from '../utils/directionColors'
import { PriorityBadge } from './PriorityPicker'
import Icon from './Icon'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onTaskClick: (task: Task) => void
  onReorder: (slot: string, orderedIds: number[]) => void
  onDropFromOutside: (taskId: number) => void
  onRemoveFromQueue: (taskId: number) => void
  onMarkDone: (taskId: number) => void
  onTakeNow: (taskId: number) => void
  onPriorityChange: (taskId: number, priority: string) => void
  planTaskIds?: number[]
  focusMode?: boolean
  nowTaskId?: number
}

export default function QueueBlock({ tasks, directions, onTaskClick, onReorder, onDropFromOutside, onRemoveFromQueue, onMarkDone, onTakeNow, onPriorityChange, planTaskIds = [], focusMode, nowTaskId }: Props) {
  function focusDimmed(task: Task) { return !!(focusMode && task.id !== nowTaskId) }
  // Exclude tasks that are in today's plan — they show in «На сегодня» instead
  const queueTasks = (tasks ?? []).filter(t => t.in_queue && !t.someday && !t.done_at && !t.deleted_at && t.slot !== 'now' && !planTaskIds.includes(t.id))
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [isDragOver, setIsDragOver] = useState(false)

  const isQueueTask = (id: number) => queueTasks.some(t => t.id === id)

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

    if (!isQueueTask(sourceId)) {
      draggingIdRef.current = null
      setDraggingId(null)
      onDropFromOutside(sourceId)
      return
    }

    draggingIdRef.current = null
    setDraggingId(null)
    if (!targetId || sourceId === targetId) return
    const ids = queueTasks.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) ids.push(sourceId)
    else ids.splice(targetIdx, 0, sourceId)
    onReorder('queue', ids)
  }

  const handleDragEnd = () => {
    draggingIdRef.current = null
    setDraggingId(null)
    setIsDragOver(false)
  }

  return (
    <div>
      <div className="border-t border-[#252525] border-dashed my-3" />
    <div
      className={`bg-[#1c1c1c] border rounded-lg overflow-hidden transition-colors ${isDragOver ? 'border-[#5060a0]' : 'border-[#252525]'}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={e => handleDrop(e)}
    >
      <div className="px-4 pt-3 pb-1">
        <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Следом</div>
      </div>

      {queueTasks.length === 0 ? (
        isDragOver ? (
          <div className="px-4 pb-3 text-xs text-[#5060a0]">Отпустите, чтобы добавить в очередь</div>
        ) : (
          <div className="px-4 pb-3 text-xs text-[#666]">Очередь пуста — добавьте задачи из направлений</div>
        )
      ) : (
        <ul className="divide-y divide-[#252525]">
          {queueTasks.map((task, idx) => {
            const dir = task.direction_id != null ? directions.find(d => d.id === task.direction_id) : null
            const c = dir ? getDirectionColor(dir.id) : null
            return (
              <li
                key={task.id}
                draggable
                onDragStart={e => handleDragStart(e, task.id)}
                onDragOver={e => { e.preventDefault(); e.stopPropagation() }}
                onDrop={e => { e.stopPropagation(); handleDrop(e, task.id) }}
                onDragEnd={handleDragEnd}
                className={`group relative flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#252525]/40 transition-colors ${draggingId === task.id ? 'opacity-40' : ''} ${focusDimmed(task) ? 'opacity-30 blur-[3px]' : ''}`}
                onClick={() => onTaskClick(task)}
              >
                {/* Direction color stripe (left edge); fallback to a faint mark if task was worked on */}
                {c ? (
                  <div className="absolute left-0 top-0 bottom-0 w-1 rounded-r" style={{ backgroundColor: c }} />
                ) : task.duration_fact > 0 ? (
                  <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-[#5060a0]/40 rounded-r" />
                ) : null}
                <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
                <span className="text-[#383838] text-xs font-mono w-4 shrink-0">{idx + 1}</span>
                <PriorityBadge priority={task.priority} onChange={v => onPriorityChange(task.id, v)} />
                <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
                {task.notes && <span className="text-[#666] shrink-0" title={task.notes}><Icon name="note" size={12} /></span>}
                {task.recurrence && <span className="text-[10px] text-[#5060a0]/60 shrink-0" title="Повторяющаяся задача">↺</span>}
                {task.deadline && (
                  <span className="text-[10px] text-[#666] shrink-0">
                    {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                  </span>
                )}
                {task.duration_plan != null && task.duration_plan > 0 && (
                  <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
                )}
                <button
                  onClick={e => { e.stopPropagation(); onTakeNow(task.id) }}
                  className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-[10px] leading-none shrink-0 transition-opacity px-0.5"
                  title="Взять сейчас"
                >▶</button>
                <button
                  onClick={e => { e.stopPropagation(); onMarkDone(task.id) }}
                  className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-xs leading-none shrink-0 transition-opacity px-0.5"
                  title="Отметить выполненной"
                >✓</button>
                <button
                  onClick={e => { e.stopPropagation(); onRemoveFromQueue(task.id) }}
                  className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#f0f0f0] text-base leading-none shrink-0 transition-opacity px-0.5"
                  title="Убрать из очереди"
                >×</button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
    </div>
  )
}
