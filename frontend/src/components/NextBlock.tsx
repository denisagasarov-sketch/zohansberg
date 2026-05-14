import type { Task, Recommendation } from '../types'

interface Props {
  tasks: Task[]
  onTaskClick: (task: Task) => void
  recommendation: Recommendation | null
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

export default function NextBlock({ tasks, onTaskClick, recommendation }: Props) {
  const nextTasks = (tasks ?? []).filter(t => t.slot === 'next' && !t.done_at && !t.deleted_at).slice(0, 3)

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
                className={`flex items-center gap-3 px-4 py-2 cursor-pointer hover:bg-[#252525]/40 transition-colors border-l-3 ${priorityBorder(task.priority)} border-l-[3px]`}
                onClick={() => onTaskClick(task)}
              >
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
