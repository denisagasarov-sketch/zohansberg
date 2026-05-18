import { useRef, useState } from 'react'
import type { Task, Recommendation } from '../types'

interface Props {
  tasks: Task[]
  onTaskClick: (task: Task) => void
  recommendation: Recommendation | null
  onReorder: (slot: string, orderedIds: number[]) => void
}

function priorityBorder(p: string) {
  if (p === 'high') return 'border-l-[#6a3030]'
  if (p === 'medium') return 'border-l-[#4a3a1e]'
  return 'border-l-[#252525]'
}

function priorityText(p: string) {
  if (p === 'high') return 'text-[#b07070]'
  if (p === 'medium') return 'text-[#a08850]'
  return 'text-[#555]'
}

function priorityLabel(p: string) {
  if (p === 'high') return 'Высокий'
  if (p === 'medium') return 'Средний'
  return 'Низкий'
}

export default function NextBlock({ tasks, onTaskClick, recommendation, onReorder }: Props) {
  const nextTasks = (tasks ?? []).filter(t => t.slot === 'next' && !t.done_at && !t.deleted_at).slice(0, 5)
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)

  const handleDragStart = (e: React.DragEvent, taskId: number) => {
    e.stopPropagation()
    draggingIdRef.current = taskId
    setDraggingId(taskId)
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    const sourceId = draggingIdRef.current
    draggingIdRef.current = null
    setDraggingId(null)
    if (!sourceId || sourceId === targetId) return
    const ids = nextTasks.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) ids.push(sourceId)
    else ids.splice(targetIdx, 0, sourceId)
    onReorder('next', ids)
  }

  const handleDragEnd = () => {
    draggingIdRef.current = null
    setDraggingId(null)
  }

  return (
    <div>
      <div className="relative flex items-center mb-3">
        <div className="flex-1 border-t border-[#252525] border-dashed" />
        <span className="px-3 text-[10px] font-semibold tracking-widest text-[#383838] uppercase whitespace-nowrap">затем</span>
        <div className="flex-1 border-t border-[#252525] border-dashed" />
      </div>

      <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
        <div className="px-4 pt-3 pb-1">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Следом</div>
        </div>

        {nextTasks.length === 0 ? (
          recommendation ? (
            <div className="px-4 pb-3">
              <div className="text-xs text-[#666]">Нет задач в очереди</div>
            </div>
          ) : (
            <div className="px-4 pb-3 text-xs text-[#666]">Очередь пуста</div>
          )
        ) : (
          <ul className="divide-y divide-[#252525]">
            {nextTasks.map((task, idx) => (
              <li
                key={task.id}
                draggable
                onDragStart={e => handleDragStart(e, task.id)}
                onDragOver={handleDragOver}
                onDrop={e => handleDrop(e, task.id)}
                onDragEnd={handleDragEnd}
                className={`flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-[3px] ${priorityBorder(task.priority)} ${draggingId === task.id ? 'opacity-40' : ''}`}
                onClick={() => onTaskClick(task)}
              >
                <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
                <span className="text-[#383838] text-xs font-mono w-4 shrink-0">{idx + 1}</span>
                <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
                <span className={`text-[10px] ${priorityText(task.priority)} shrink-0`}>{priorityLabel(task.priority)}</span>
                {task.duration_plan && (
                  <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
