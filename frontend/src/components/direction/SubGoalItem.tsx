import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import { TaskItem } from './TaskItem'
import { formatDuration } from '../../utils/time'

interface Props {
  subGoalId: string
  goalId: string
}

export function SubGoalItem({ subGoalId, goalId }: Props) {
  const {
    subGoals, getTasksBySubGoal, updateSubGoal, deleteSubGoal,
    addTask, totalTimeForSubGoal, selectedDirectionId,
  } = useStore()

  const sg = subGoals[subGoalId]
  const [expanded, setExpanded] = useState(true)
  const [addingTask, setAddingTask] = useState(false)
  const [newTaskTitle, setNewTaskTitle] = useState('')

  if (!sg) return null

  const tasks = getTasksBySubGoal(subGoalId)
  const time = totalTimeForSubGoal(subGoalId)
  const completedCount = tasks.filter(t => t.status === 'completed').length

  const commitNewTask = () => {
    const t = newTaskTitle.trim()
    if (!t) return
    addTask({ title: t, subGoalId, directionId: selectedDirectionId })
    setNewTaskTitle('')
    setAddingTask(false)
  }

  return (
    <div className="border border-[#1f1f23] rounded-lg overflow-hidden">
      {/* Sub-goal header */}
      <div className="flex items-center gap-2 px-3 py-2.5 bg-[#111113] group">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[#4a4a55] hover:text-[#8b8b9a] transition-colors flex-shrink-0 w-4 h-4 flex items-center justify-center"
        >
          <span className={`text-xs transition-transform ${expanded ? 'rotate-90' : ''} inline-block`}>▶</span>
        </button>

        <div className="flex-1 min-w-0">
          <InlineEdit
            value={sg.title}
            onSave={(v) => updateSubGoal(subGoalId, { title: v })}
            className="text-sm font-medium text-[#c8c8d4]"
          />
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Task count */}
          <span className="text-xs font-mono text-[#4a4a55]">
            {completedCount}/{tasks.length}
          </span>
          {/* Time */}
          {time > 0 && (
            <span className="text-xs font-mono text-[#4a4a55]">{formatDuration(time)}</span>
          )}
          {/* Add task */}
          <button
            onClick={() => { setAddingTask(true); setExpanded(true) }}
            className="opacity-0 group-hover:opacity-100 text-xs text-[#3b82f6] border border-[#3b82f6]/30 px-1.5 py-0.5 rounded hover:bg-[#3b82f6]/10 transition-all"
          >
            +
          </button>
          {/* Delete sub-goal */}
          <button
            onClick={() => deleteSubGoal(subGoalId)}
            className="opacity-0 group-hover:opacity-100 text-[#4a4a55] hover:text-[#ef4444] text-xs transition-all"
          >
            ×
          </button>
        </div>
      </div>

      {/* Tasks */}
      {expanded && (
        <div className="bg-[#0a0a0b]">
          {tasks.map(task => (
            <TaskItem key={task.id} taskId={task.id} />
          ))}

          {tasks.length === 0 && !addingTask && (
            <div
              className="px-8 py-3 text-xs text-[#2a2a31] cursor-pointer hover:text-[#4a4a55] transition-colors"
              onClick={() => setAddingTask(true)}
            >
              No tasks — click to add
            </div>
          )}

          {addingTask && (
            <div className="px-8 py-2 flex items-center gap-2 border-t border-[#1f1f23]">
              <input
                autoFocus
                type="text"
                value={newTaskTitle}
                onChange={e => setNewTaskTitle(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter') commitNewTask()
                  if (e.key === 'Escape') { setAddingTask(false); setNewTaskTitle('') }
                }}
                placeholder="Task title..."
                className="flex-1 bg-transparent border-b border-[#3b82f6]/50 outline-none text-sm text-[#c8c8d4] placeholder-[#2a2a31] py-1"
              />
              <button onClick={commitNewTask} className="text-xs text-[#3b82f6] font-mono">Add</button>
              <button onClick={() => { setAddingTask(false); setNewTaskTitle('') }} className="text-xs text-[#4a4a55] font-mono">Cancel</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
