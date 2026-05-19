import { useRef, useState, useCallback } from 'react'
import type { Task, Direction } from '../types'
import { DRAG_TASK_KEY } from '../hooks/useDragDrop'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onTaskClick: (task: Task) => void
  onReorder: (slot: string, orderedIds: number[]) => void
  onReorderInDirection: (directionId: number | null, orderedIds: number[]) => void
  onMoveToQueue: (taskId: number) => void
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
  const dimmed = focusMode && task.id !== nowTaskId
  return (
    <div
      draggable
      onDragStart={e => onDragStart(e, task.id)}
      onDragOver={e => onDragOver(e, task.id)}
      onDrop={e => onDrop(e, task.id)}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors ${draggingId === task.id ? 'opacity-40' : ''} ${dimmed ? 'opacity-30 blur-[3px]' : ''}`}
    >
      <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
      <span className="text-[#505050] text-[10px] font-mono w-3 shrink-0 select-none">{index}</span>
      <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
      {task.deadline && (
        <span className="text-[10px] text-[#666] shrink-0">
          {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
        </span>
      )}
      {task.duration_plan && (
        <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
      )}
      {task.slot === 'now' && <span className="text-[10px] text-[#5060a0] shrink-0">▶</span>}
    </div>
  )
}

function loadCollapsed(): Set<number | 'none'> {
  try { return new Set(JSON.parse(localStorage.getItem('collapsed_dirs') ?? '[]')) }
  catch { return new Set() }
}

function saveCollapsed(s: Set<number | 'none'>) {
  localStorage.setItem('collapsed_dirs', JSON.stringify([...s]))
}

export default function DirectionsPanel({ tasks, directions, onTaskClick, onReorder, onReorderInDirection, onMoveToQueue, focusMode, nowTaskId }: Props) {
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [collapsed, setCollapsed] = useState<Set<number | 'none'>>(loadCollapsed)

  const toggleCollapse = useCallback((key: number | 'none') => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      saveCollapsed(next)
      return next
    })
  }, [])

  const activeTasks = (tasks ?? []).filter(t => !t.done_at && !t.deleted_at)

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

    // Cross-direction drop: move 'now' task to queue
    if (sourceTask.slot === 'now') {
      onMoveToQueue(sourceId)
    }
  }

  const sortedDirs = [...(directions ?? [])].sort((a, b) => a.order_index - b.order_index)

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase px-1 mb-3 sticky top-0 bg-[#181818] py-1">Направления</div>

      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {sortedDirs.map(dir => {
          const color = getDirectionColor(dir.id)
          const dirTasks = sortDirectionTasks(activeTasks.filter(t => t.direction_id === dir.id))
          const isCollapsed = collapsed.has(dir.id)
          return (
            <div key={dir.id} className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div
                className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
                style={{ backgroundColor: color + '1a' }}
                onClick={() => toggleCollapse(dir.id)}
              >
                <span className="text-xs font-semibold" style={{ color }}>{dir.name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px]" style={{ color: color + '80' }}>{dirTasks.length}</span>
                  <span className="text-[10px]" style={{ color: color + '80' }}>{isCollapsed ? '▶' : '▼'}</span>
                </div>
              </div>
              {!isCollapsed && (
                <>
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
                </>
              )}
            </div>
          )
        })}

        {/* Tasks without direction */}
        {(() => {
          const noDirTasks = sortDirectionTasks(activeTasks.filter(t => t.direction_id === null))
          if (noDirTasks.length === 0) return null
          const isCollapsed = collapsed.has('none')
          return (
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div
                className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
                onClick={() => toggleCollapse('none')}
              >
                <span className="text-xs font-medium text-[#666]">Без направления</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[#383838]">{noDirTasks.length}</span>
                  <span className="text-[10px] text-[#383838]">{isCollapsed ? '▶' : '▼'}</span>
                </div>
              </div>
              {!isCollapsed && (
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
              )}
            </div>
          )
        })()}
      </div>
    </div>
  )
}
