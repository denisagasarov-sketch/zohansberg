import { useRef, useState, useCallback, useEffect } from 'react'
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
  onAddToQueue: (taskId: number) => void
  onPriorityChange: (taskId: number, priority: string) => void
  focusMode?: boolean
  nowTaskId?: number
}

type CollapseKey = number | 'none' | 'someday'

const PRIORITY_OPTIONS = [
  { value: 'I',    label: 'Ⅰ', color: '#F97316' },
  { value: 'II',   label: 'Ⅱ', color: '#94A3B8' },
  { value: 'III',  label: 'Ⅲ', color: '#475569' },
  { value: 'none', label: '–', color: '#555'     },
] as const

function priorityLabel(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.label ?? '–' }
function priorityColor(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.color ?? '#555' }

function PriorityPicker({ current, onChange, onClose }: {
  current: string
  onChange: (v: string) => void
  onClose: () => void
}) {
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const el = document.getElementById('priority-picker')
      if (el && !el.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose])

  return (
    <div
      id="priority-picker"
      className="absolute z-40 left-0 top-full mt-0.5 bg-[#1c1c1c] border border-[#383838] rounded shadow-xl py-0.5 min-w-[56px]"
      onMouseDown={e => e.stopPropagation()}
    >
      {PRIORITY_OPTIONS.map(o => (
        <button
          key={o.value}
          onClick={() => { onChange(o.value); onClose() }}
          className={`flex items-center justify-center w-full px-3 py-1 text-xs hover:bg-[#252525] transition-colors ${current === o.value ? 'bg-[#252525]' : ''}`}
          style={{ color: o.color }}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
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
  onAddToQueue: (taskId: number) => void
  onPriorityChange: (taskId: number, priority: string) => void
  draggingId: number | null
  focusMode?: boolean
  nowTaskId?: number
}

function TaskRow({ task, index, onClick, onDragStart, onDragOver, onDrop, onAddToQueue, onPriorityChange, draggingId, focusMode, nowTaskId }: TaskRowProps) {
  const dimmed = focusMode && task.id !== nowTaskId
  const [showPicker, setShowPicker] = useState(false)

  return (
    <div
      draggable
      onDragStart={e => onDragStart(e, task.id)}
      onDragOver={e => onDragOver(e, task.id)}
      onDrop={e => onDrop(e, task.id)}
      onClick={onClick}
      className={`group flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors ${draggingId === task.id ? 'opacity-40' : ''} ${dimmed ? 'opacity-30 blur-[3px]' : ''}`}
    >
      <span className="text-[#383838] text-[10px] cursor-grab select-none shrink-0">⠿</span>
      <span className="text-[#505050] text-[10px] font-mono w-3 shrink-0 select-none">{index}</span>

      {/* Priority symbol */}
      <div className="relative shrink-0">
        <button
          onClick={e => { e.stopPropagation(); setShowPicker(v => !v) }}
          className="text-[11px] font-mono w-4 text-center leading-none transition-opacity hover:opacity-100"
          style={{ color: priorityColor(task.priority) }}
          title="Приоритет"
        >
          {priorityLabel(task.priority)}
        </button>
        {showPicker && (
          <PriorityPicker
            current={task.priority}
            onChange={v => onPriorityChange(task.id, v)}
            onClose={() => setShowPicker(false)}
          />
        )}
      </div>

      <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
      {task.deadline && (
        <span className="text-[10px] text-[#666] shrink-0">
          {new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
        </span>
      )}
      {task.duration_plan != null && (
        <span className="text-[10px] text-[#666] shrink-0">{task.duration_plan}ч</span>
      )}
      {task.slot === 'now' && <span className="text-[10px] text-[#5060a0] shrink-0">▶</span>}
      <button
        onClick={e => { e.stopPropagation(); onAddToQueue(task.id) }}
        className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-xs shrink-0 transition-opacity px-0.5 font-bold"
        title="Добавить в очередь"
      >+</button>
    </div>
  )
}

function loadCollapsed(): Set<CollapseKey> {
  try { return new Set(JSON.parse(localStorage.getItem('collapsed_dirs') ?? '[]')) }
  catch { return new Set() }
}

function saveCollapsed(s: Set<CollapseKey>) {
  localStorage.setItem('collapsed_dirs', JSON.stringify([...s]))
}

export default function DirectionsPanel({ tasks, directions, onTaskClick, onReorder, onReorderInDirection, onMoveToQueue, onAddToQueue, onPriorityChange, focusMode, nowTaskId }: Props) {
  const draggingIdRef = useRef<number | null>(null)
  const [draggingId, setDraggingId] = useState<number | null>(null)
  const [collapsed, setCollapsed] = useState<Set<CollapseKey>>(loadCollapsed)

  const toggleCollapse = useCallback((key: CollapseKey) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      saveCollapsed(next)
      return next
    })
  }, [])

  const activeTasks = (tasks ?? []).filter(t => !t.in_queue && !t.someday && !t.done_at && !t.deleted_at)
  const somedayTasks = (tasks ?? []).filter(t => t.someday && !t.done_at && !t.deleted_at)

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

    // Only same-direction reordering; ignore queue tasks and cross-direction
    if (sourceTask.in_queue || sourceTask.direction_id !== targetTask.direction_id) return

    const dirTasks = sortDirectionTasks(
      activeTasks.filter(t => t.direction_id === sourceTask.direction_id)
    )
    const ids = dirTasks.map(t => t.id).filter(id => id !== sourceId)
    const targetIdx = ids.indexOf(targetId)
    if (targetIdx === -1) ids.push(sourceId)
    else ids.splice(targetIdx, 0, sourceId)
    onReorderInDirection(sourceTask.direction_id, ids)
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
                    <div className="px-3 py-2 text-[10px] text-[#383838]">Нет задач вне очереди</div>
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
                          onAddToQueue={onAddToQueue}
                          onPriorityChange={onPriorityChange}
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
                      onAddToQueue={onAddToQueue}
                      onPriorityChange={onPriorityChange}
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

        {/* Someday section */}
        {(() => {
          if (somedayTasks.length === 0) return null
          const isCollapsed = collapsed.has('someday')
          return (
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
              <div
                className="flex items-center justify-between px-3 py-2 cursor-pointer select-none"
                onClick={() => toggleCollapse('someday')}
              >
                <span className="text-xs font-medium text-[#555]">☁ Когда-нибудь</span>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-[#383838]">{somedayTasks.length}</span>
                  <span className="text-[10px] text-[#383838]">{isCollapsed ? '▶' : '▼'}</span>
                </div>
              </div>
              {!isCollapsed && (
                <div className="divide-y divide-[#252525]/50">
                  {somedayTasks.map(task => {
                    const dir = task.direction_id != null ? directions.find(d => d.id === task.direction_id) : null
                    return (
                      <div
                        key={task.id}
                        onClick={() => onTaskClick(task)}
                        className="flex items-center gap-2 px-3 py-1.5 cursor-pointer hover:bg-[#252525]/40 transition-colors"
                      >
                        <span className="flex-1 text-[12px] italic text-[#f0f0f0] opacity-60 truncate">{task.title}</span>
                        {dir && <span className="text-[10px] text-[#555] shrink-0">{dir.name}</span>}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })()}
      </div>
    </div>
  )
}
