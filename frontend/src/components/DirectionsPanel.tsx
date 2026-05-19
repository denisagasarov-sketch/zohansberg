import { useRef, useState } from 'react'
import type { Task, Direction } from '../types'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getQuadrant } from '../utils/quadrant'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onTaskClick: (task: Task) => void
  onReorder: (slot: string, orderedIds: number[]) => void
  onReorderInDirection: (directionId: number | null, orderedIds: number[]) => void
  onMoveToLater: (taskId: number) => void
  focusMode?: boolean
  nowTaskId?: number
}

function sortDirectionTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    const diff = (a.direction_order ?? 0) - (b.direction_order ?? 0)
    return diff !== 0 ? diff : a.id - b.id
  })
}

interface TaskRowProps {
  task: Task
  index: number
  onClick: () => void
  onDragStart: (e: React.DragEvent, taskId: number) => void
  onDragOver: (e: React.DragEvent, taskId: number) => void
  onDrop: (e: React.DragEvent, taskId: number) => void
  draggingId: number | null
  focusMode?: boolean
  nowTaskId?: number
}

function TaskRow({ task, index, onClick, onDragStart, onDragOver, onDrop, draggingId, focusMode, nowTaskId }: TaskRowProps) {
  const q = getQuadrant(task.is_important ?? 0, task.is_urgent ?? 0)
  const dimmed = focusMode && task.id !== nowTaskId
  return (
    <div
      draggable
      onDragStart={e => onDragStart(e, task.id)}
      onDragOver={e => onDragOver(e, task.id)}
      onDrop={e => onDrop(e, task.id)}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-[3px] ${draggingId === task.id ? 'opacity-40' : ''} ${dimmed ? 'opacity-30 blur-[3px]' : ''}`}
      style={{ borderLeftColor: q.border }}
    >
      <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
      <span className="text-[#505050] text-[10px] font-mono w-3 shrink-0 select-none">{index}</span>
      <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
      {task.deadline && (
        <span className="text-[10px] shrink-0" style={{ color: q.color }}>
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

export default function DirectionsPanel({ tasks, directions, onTaskClick, onReorder, onReorderInDirection, onMoveToLater, focusMode, nowTaskId }: Props) {
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [somedayExpanded, setSomedayExpanded] = useState(false)

  const activeTasks = (tasks ?? []).filter(t =>
    !t.done_at && !t.deleted_at && t.slot !== 'someday'
  )

  const handleDragStart = (e: React.DragEvent, taskId: number) => {
    draggingIdRef.current = taskId
    setDraggingId(taskId)
    e.dataTransfer.setData(DRAG_TASK_KEY, String(taskId))
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent, _taskId: number) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }

  const handleDrop = (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    const raw = e.dataTransfer.getData(DRAG_TASK_KEY)
    const sourceId = parseInt(raw, 10) || draggingIdRef.current
    draggingIdRef.current = null
    setDraggingId(null)
    if (!sourceId || sourceId === targetId) return

    const sourceTask = tasks.find(t => t.id === sourceId)
    const targetTask = tasks.find(t => t.id === targetId)
    if (!sourceTask || !targetTask) return

    // Same direction → reorder within direction
    if (sourceTask.direction_id === targetTask.direction_id) {
      const dirTasks = sortDirectionTasks(
        activeTasks.filter(t => t.direction_id === sourceTask.direction_id)
      )
      const ids = dirTasks.map(t => t.id).filter(id => id !== sourceId)
      const targetIdx = ids.indexOf(targetId)
      if (targetIdx === -1) ids.push(sourceId)
      else ids.splice(targetIdx, 0, sourceId)
      onReorderInDirection(sourceTask.direction_id, ids)
      return
    }

    // Cross-slot drop (different directions or slots) → move to later
    if (sourceTask.slot === 'now' || sourceTask.slot === 'next') {
      onMoveToLater(sourceId)
    }
  }

  const somedayTasks = (tasks ?? []).filter(t => t.slot === 'someday' && !t.done_at && !t.deleted_at)
  const somedayVisible = somedayExpanded ? somedayTasks : somedayTasks.slice(0, 3)
  const somedayRest = somedayTasks.length - somedayVisible.length

  const sortedDirs = [...(directions ?? [])].sort((a, b) => a.order_index - b.order_index)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase px-1 mb-3 sticky top-0 bg-[#181818] py-1">Направления</div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {sortedDirs.map(dir => {
          const color = getDirectionColor(dir.id)
          const dirTasks = sortDirectionTasks(activeTasks.filter(t => t.direction_id === dir.id))
          return (
            <div key={dir.id} className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              {/* Colored header */}
              <div
                className="flex items-center justify-between px-3 py-2 border-b border-[#252525]"
                style={{ backgroundColor: color + '1a' }}
              >
                <span className="text-xs font-semibold" style={{ color }}>{dir.name}</span>
                <span className="text-[10px]" style={{ color: color + '80' }}>{dirTasks.length}</span>
              </div>
              {dirTasks.length === 0 ? (
                <div className="px-3 py-2 text-[10px] text-[#383838]">Нет активных задач</div>
              ) : (
                <div className="divide-y divide-[#252525]/50">
                  {dirTasks.map((task, idx) => (
                    <TaskRow
                      key={task.id}
                      task={task}
                      index={idx + 1}
                      onClick={() => onTaskClick(task)}
                      onDragStart={handleDragStart}
                      onDragOver={handleDragOver}
                      onDrop={handleDrop}
                      draggingId={draggingId}
                      focusMode={focusMode}
                      nowTaskId={nowTaskId}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {/* Tasks without direction */}
        {(() => {
          const noDirTasks = sortDirectionTasks(activeTasks.filter(t => t.direction_id === null))
          if (noDirTasks.length === 0) return null
          return (
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b border-[#252525]">
                <span className="text-xs font-medium text-[#666]">Без направления</span>
                <span className="text-[10px] text-[#383838]">{noDirTasks.length}</span>
              </div>
              <div className="divide-y divide-[#252525]/50">
                {noDirTasks.map((task, idx) => (
                  <TaskRow
                    key={task.id}
                    task={task}
                    index={idx + 1}
                    onClick={() => onTaskClick(task)}
                    onDragStart={handleDragStart}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    draggingId={draggingId}
                    focusMode={focusMode}
                    nowTaskId={nowTaskId}
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
              {somedayVisible.map(task => {
                const q = getQuadrant(task.is_important ?? 0, task.is_urgent ?? 0)
                const dimmed = focusMode && task.id !== nowTaskId
                return (
                  <div
                    key={task.id}
                    onClick={() => onTaskClick(task)}
                    className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-[3px] ${dimmed ? 'opacity-30 blur-[3px]' : ''}`}
                    style={{ borderLeftColor: q.border }}
                  >
                    <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
                  </div>
                )
              })}
            </div>
            {somedayRest > 0 && (
              <button
                onClick={() => setSomedayExpanded(true)}
                className="w-full px-3 py-1.5 text-left text-[10px] text-[#505050] hover:text-[#999] transition-colors"
              >
                ещё {somedayRest} ↓
              </button>
            )}
            {somedayExpanded && somedayRest === 0 && (
              <button
                onClick={() => setSomedayExpanded(false)}
                className="w-full px-3 py-1.5 text-left text-[10px] text-[#505050] hover:text-[#999] transition-colors"
              >
                свернуть ↑
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
