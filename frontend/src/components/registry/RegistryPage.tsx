import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { TaskRow } from './TaskRow'
import { formatDuration } from '../../utils/time'
import type { TaskStatus } from '../../types'

const STATUS_FILTERS: { value: TaskStatus | 'all'; label: string; color: string }[] = [
  { value: 'all',          label: 'All',          color: 'text-[#8b8b9a]' },
  { value: 'active',       label: 'Active',       color: 'text-[#3b82f6]' },
  { value: 'overdue',      label: 'Overdue',      color: 'text-[#ef4444]' },
  { value: 'stuck',        label: 'Stuck',        color: 'text-[#f59e0b]' },
  { value: 'inbox',        label: 'Inbox',        color: 'text-[#6b6b7a]' },
  { value: 'no-next-step', label: 'No next step', color: 'text-[#a855f7]' },
  { value: 'completed',    label: 'Done',         color: 'text-[#22c55e]' },
]

export function RegistryPage() {
  const {
    directions, filteredTasks, searchQuery, statusFilter, directionFilter,
    setSearchQuery, setStatusFilter, setDirectionFilter,
    addTask, subGoals, totalTimeForTask,
  } = useStore()

  const [addingTask, setAddingTask] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newDirId, setNewDirId] = useState(directions[0]?.id ?? '')

  const tasks = filteredTasks()
  const totalFilteredTime = tasks.reduce((acc, t) => acc + totalTimeForTask(t.id), 0)

  // Group by direction
  const grouped = directions
    .map(dir => ({
      dir,
      tasks: tasks.filter(t => t.directionId === dir.id),
    }))
    .filter(g => g.tasks.length > 0 || directionFilter === 'all')

  const handleAddTask = () => {
    const t = newTitle.trim()
    if (!t || !newDirId) return
    // Find first subgoal for this direction
    const sg = Object.values(subGoals).find(sg => sg.directionId === newDirId)
    if (!sg) return
    addTask({ title: t, subGoalId: sg.id, directionId: newDirId })
    setNewTitle('')
    setAddingTask(false)
  }

  // Summary counts
  const counts: Record<string, number> = {}
  Object.values(useStore.getState().tasks).forEach(t => {
    counts[t.status] = (counts[t.status] ?? 0) + 1
  })

  return (
    <div className="flex flex-col h-full">
      {/* Summary bar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        {STATUS_FILTERS.slice(1).map(sf => {
          const count = counts[sf.value] ?? 0
          if (count === 0) return null
          return (
            <button
              key={sf.value}
              onClick={() => setStatusFilter(statusFilter === sf.value ? 'all' : sf.value as TaskStatus)}
              className={`text-xs font-mono flex items-center gap-1.5 transition-opacity ${sf.color} ${
                statusFilter !== 'all' && statusFilter !== sf.value ? 'opacity-30' : ''
              }`}
            >
              <span>{count}</span>
              <span className="text-[#4a4a55]">{sf.label.toLowerCase()}</span>
            </button>
          )
        })}
        {totalFilteredTime > 0 && (
          <div className="ml-auto text-xs font-mono text-[#4a4a55]">
            {formatDuration(totalFilteredTime)} total
          </div>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 mb-4">
        {/* Search */}
        <div className="flex-1 relative">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4a4a55] text-xs">⌕</span>
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search tasks..."
            className="w-full bg-[#111113] border border-[#2a2a31] rounded-lg pl-7 pr-3 py-2 text-sm text-[#c8c8d4] placeholder-[#2a2a31] outline-none focus:border-[#3a3a44] transition-colors"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[#4a4a55] hover:text-[#8b8b9a] text-xs"
            >
              ×
            </button>
          )}
        </div>

        {/* Direction filter */}
        <select
          value={directionFilter}
          onChange={e => setDirectionFilter(e.target.value)}
          className="bg-[#111113] border border-[#2a2a31] rounded-lg px-3 py-2 text-sm text-[#8b8b9a] outline-none cursor-pointer"
        >
          <option value="all" className="bg-[#0a0a0b]">All directions</option>
          {directions.map(d => (
            <option key={d.id} value={d.id} className="bg-[#0a0a0b]">{d.name}</option>
          ))}
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value as TaskStatus | 'all')}
          className="bg-[#111113] border border-[#2a2a31] rounded-lg px-3 py-2 text-sm text-[#8b8b9a] outline-none cursor-pointer"
        >
          {STATUS_FILTERS.map(sf => (
            <option key={sf.value} value={sf.value} className="bg-[#0a0a0b]">{sf.label}</option>
          ))}
        </select>

        {/* Add task */}
        <button
          onClick={() => setAddingTask(!addingTask)}
          className="px-3 py-2 text-xs font-mono text-[#3b82f6] border border-[#3b82f6]/30 rounded-lg hover:bg-[#3b82f6]/10 transition-colors"
        >
          + New
        </button>
      </div>

      {/* Add task form */}
      {addingTask && (
        <div className="mb-4 flex items-center gap-2 bg-[#111113] border border-[#3b82f6]/30 rounded-lg px-4 py-3">
          <input
            autoFocus
            type="text"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') handleAddTask()
              if (e.key === 'Escape') { setAddingTask(false); setNewTitle('') }
            }}
            placeholder="Task title..."
            className="flex-1 bg-transparent outline-none text-sm text-[#e8e8f0] placeholder-[#4a4a55]"
          />
          <select
            value={newDirId}
            onChange={e => setNewDirId(e.target.value)}
            className="text-xs bg-[#1f1f23] border border-[#2a2a31] rounded px-2 py-1 text-[#8b8b9a] outline-none"
          >
            {directions.map(d => (
              <option key={d.id} value={d.id} className="bg-[#0a0a0b]">{d.name}</option>
            ))}
          </select>
          <button onClick={handleAddTask} className="text-xs text-[#3b82f6] font-mono px-2">Add</button>
          <button onClick={() => { setAddingTask(false); setNewTitle('') }} className="text-xs text-[#4a4a55]">Cancel</button>
        </div>
      )}

      {/* Task table */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {/* Header */}
        <div className="grid grid-cols-[1fr_100px_90px_80px_64px] gap-2 px-3 py-1.5 text-[10px] uppercase tracking-widest text-[#2a2a31] font-mono border-b border-[#1f1f23] sticky top-0 bg-[#0a0a0b] z-10">
          <span>Task</span>
          <span>Direction</span>
          <span>Status</span>
          <span>Deadline</span>
          <span className="text-right">Time</span>
        </div>

        {directionFilter === 'all' ? (
          // Grouped by direction
          grouped.map(({ dir, tasks: dirTasks }) => (
            <DirectionGroup key={dir.id} dirName={dir.name} tasks={dirTasks} />
          ))
        ) : (
          // Flat list when direction filtered
          tasks.map(t => <TaskRow key={t.id} taskId={t.id} />)
        )}

        {tasks.length === 0 && (
          <div className="py-12 text-center text-[#2a2a31] text-sm">
            {searchQuery || statusFilter !== 'all' ? 'No tasks match your filters' : 'No tasks'}
          </div>
        )}
      </div>
    </div>
  )
}

import type { Task } from '../../types'

function DirectionGroup({ dirName, tasks }: { dirName: string; tasks: Task[] }) {
  const { totalTimeForTask } = useStore()
  const [collapsed, setCollapsed] = useState(false)
  const groupTime = tasks.reduce((a, t) => a + totalTimeForTask(t.id), 0)

  if (tasks.length === 0) return null

  return (
    <div>
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-1.5 bg-[#0f0f11] border-b border-[#1f1f23] hover:bg-[#111113] transition-colors group"
      >
        <span className={`text-[10px] text-[#4a4a55] transition-transform ${collapsed ? '' : 'rotate-90'} inline-block`}>▶</span>
        <span className="text-xs font-mono text-[#6b6b7a] uppercase tracking-wider">{dirName}</span>
        <span className="text-xs font-mono text-[#2a2a31] ml-1">{tasks.length}</span>
        {groupTime > 0 && (
          <span className="ml-auto text-xs font-mono text-[#2a2a31]">{formatDuration(groupTime)}</span>
        )}
      </button>
      {!collapsed && tasks.map(t => <TaskRow key={t.id} taskId={t.id} />)}
    </div>
  )
}
