import type { Task, Direction } from '../types'
import { getDirectionColor } from '../utils/directionColors'
import { priorityLabel, priorityColor } from '../utils/priority'

interface Props {
  planTaskIds: number[]
  tasks: Task[]
  directions: Direction[]
  onTakeNow: (taskId: number) => void
  onMarkDone: (taskId: number) => void
}

export default function DayPlanBlock({ planTaskIds, tasks, directions, onTakeNow, onMarkDone }: Props) {
  const planTasks = planTaskIds
    .map(id => tasks.find(t => t.id === id))
    .filter((t): t is Task => !!t && !t.done_at && !t.deleted_at && t.slot !== 'now')

  if (planTasks.length === 0) return null

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
                className="group flex items-center gap-3 px-4 py-2 hover:bg-[#252525]/40 transition-colors"
              >
                {task.priority && task.priority !== 'none' && (
                  <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>
                    {priorityLabel(task.priority)}
                  </span>
                )}
                <span className="flex-1 text-sm text-[#f0f0f0] truncate">{task.title}</span>
                {dir && c && (
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0 font-medium"
                    style={{ color: c, backgroundColor: c + '28' }}
                  >
                    {dir.name}
                  </span>
                )}
                <button
                  onClick={() => onTakeNow(task.id)}
                  className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#5060a0] text-[10px] leading-none shrink-0 transition-opacity px-0.5"
                  title="Взять сейчас"
                >▶</button>
                <button
                  onClick={() => onMarkDone(task.id)}
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
