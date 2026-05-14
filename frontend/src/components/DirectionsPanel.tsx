import { useRef, useState } from 'react'
import type { Task, Direction } from '../types'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onTaskClick: (task: Task) => void
  onReorder: (slot: string, orderedIds: number[]) => void
}

const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 }

function sortTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    const po = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
    if (po !== 0) return po
    if (a.deadline && b.deadline) return a.deadline.localeCompare(b.deadline)
    if (a.deadline) return -1
    if (b.deadline) return 1
    return a.created_at.localeCompare(b.created_at)
  })
}

function priorityBorderColor(p: string) {
  if (p === 'high') return '#6a3030'
  if (p === 'medium') return '#4a3a1e'
  return '#252525'
}

function priorityTextColor(p: string) {
  if (p === 'high') return '#b07070'
  if (p === 'medium') return '#a08850'
  return '#555'
}

interface TaskRowProps {
  task: Task
  onClick: () => void
  onDragStart: (e: React.DragEvent, taskId: number) => void
  onDragOver: (e: React.DragEvent, taskId: number) => void
  onDrop: (e: React.DragEvent, taskId: number) => void
  draggingId: number | null
}

function TaskRow({ task, onClick, onDragStart, onDragOver, onDrop, draggingId }: TaskRowProps) {
  return (
    <div
      draggable
      onDragStart={e => onDragStart(e, task.id)}
      onDragOver={e => onDragOver(e, task.id)}
      onDrop={e => onDrop(e, task.id)}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-[3px] ${draggingId === task.id ? 'opacity-40' : ''}`}
      style={{ borderLeftColor: priorityBorderColor(task.priority) }}
    >
      <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
      {task.deadline && (
        <span className="text-[10px] shrink-0" style={{ color: priorityTextColor(task.priority) }}>
          {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
        </span>
      )}
      {task.duration_plan && (
        <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
      )}
      {task.slot === 'now' && <span className="text-[10px] text-[#5060a0] shrink-0">▶</span>}
      {task.slot === 'next' && <span className="text-[10px] text-[#666] shrink-0">→</span>}
    </div>
  )
}

export default function DirectionsPanel({ tasks, directions, onTaskClick, onReorder }: Props) {
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)

  const activeTasks = tasks.filter(t => !t.done_at && !t.deleted_at && t.slot !== 'someday')

  const handleDragStart = (_e: React.DragEvent, taskId: number) => {
    draggingIdRef.current = taskId
    setDraggingId(taskId)
  }

  const handleDragOver = (e: React.DragEvent, _taskId: number) => {
    e.preventDefault()
  }

  const handleDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    const sourceId = draggingIdRef.current
    if (!sourceId || sourceId === targetId) {
      draggingIdRef.current = null
      setDraggingId(null)
      return
    }
    const sourceTask = tasks.find(t => t.id === sourceId)
    const targetTask = tasks.find(t => t.id === targetId)
    if (!sourceTask || !targetTask || sourceTask.slot !== targetTask.slot) {
      draggingIdRef.current = null
      setDraggingId(null)
      return
    }
    const slotTasks = activeTasks.filter(t => t.slot === sourceTask.slot && t.direction_id === sourceTask.direction_id)
    const sorted = sortTasks(slotTasks)
    const ids = sorted.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) {
      ids.push(sourceId)
    } else {
      ids.splice(targetIdx, 0, sourceId)
    }
    onReorder(sourceTask.slot, ids)
    draggingIdRef.current = null
    setDraggingId(null)
  }

  const somedayTasks = tasks.filter(t => t.slot === 'someday' && !t.done_at && !t.deleted_at)
  const somedayVisible = somedayTasks.slice(0, 3)
  const somedayRest = somedayTasks.length - somedayVisible.length

  const sortedDirs = [...directions].sort((a, b) => a.order_index - b.order_index)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase px-1 mb-3 sticky top-0 bg-[#181818] py-1">Направления</div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {sortedDirs.map(dir => {
          const dirTasks = sortTasks(activeTasks.filter(t => t.direction_id === dir.id))
          return (
            <div key={dir.id} className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-[#252525]">
                <span className="text-xs font-medium text-[#f0f0f0]">{dir.name}</span>
                <span className="text-[10px] text-[#383838]">{dirTasks.length}</span>
              </div>
              {dirTasks.length === 0 ? (
                <div className="px-3 py-2 text-[10px] text-[#383838]">Нет задач</div>
              ) : (
                <div className="divide-y divide-[#252525]/50">
                  {dirTasks.map(task => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      onClick={() => onTaskClick(task)}
                      onDragStart={handleDragStart}
                      onDragOver={handleDragOver}
                      onDrop={handleDrop}
                      draggingId={draggingId}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {/* Tasks without direction */}
        {(() => {
          const noDirTasks = sortTasks(activeTasks.filter(t => t.direction_id === null))
          if (noDirTasks.length === 0) return null
          return (
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-[#252525]">
                <span className="text-xs font-medium text-[#666]">Без направления</span>
                <span className="text-[10px] text-[#383838]">{noDirTasks.length}</span>
              </div>
              <div className="divide-y divide-[#252525]/50">
                {noDirTasks.map(task => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    onClick={() => onTaskClick(task)}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    draggingId={draggingId}
                  />
                ))}
              </div>
            </div>
          )
        })()}

        {/* Someday section */}
        {somedayTasks.length > 0 && (
          <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
            <div className="px-3 py-2 border-b border-[#252525]">
              <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase">Когда-нибудь</span>
            </div>
            <div className="divide-y divide-[#252525]/50">
              {somedayVisible.map(task => (
                <TaskRow
                  key={task.id}
                  task={task}
                  onClick={() => onTaskClick(task)}
                  onDragStart={handleDragStart}
                  onDragOver={handleDragOver}
                  onDrop={handleDrop}
                  draggingId={draggingId}
                />
              ))}
            </div>
            {somedayRest > 0 && (
              <div className="px-3 py-1.5 text-[10px] text-[#383838]">ещё {somedayRest}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
