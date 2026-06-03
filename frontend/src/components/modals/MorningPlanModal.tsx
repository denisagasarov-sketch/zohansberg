import type { Direction } from '../../types'
import { getDirectionColor } from '../../utils/directionColors'
import { priorityLabel, priorityColor } from '../../utils/priority'

interface PlanTask {
  task_id: number
  title: string
  priority: string | null
  direction_id: number | null
  done_at: string | null
}

interface Props {
  planTasks: PlanTask[]
  directions: Direction[]
  onTakeNow: (taskId: number) => void
  onClose: () => void
}

export default function MorningPlanModal({ planTasks, directions, onTakeNow, onClose }: Props) {
  const pending = planTasks.filter(t => !t.done_at)
  const done = planTasks.filter(t => t.done_at)

  const today = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80" onClick={onClose} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="px-6 pt-6 pb-4" style={{ background: 'linear-gradient(180deg, #1a1a2e 0%, #1c1c1c 100%)' }}>
          <div className="text-xs text-[#5060a0] font-semibold tracking-widest uppercase mb-1">Доброе утро</div>
          <h2 className="text-xl font-bold text-[#f0f0f0]">Твой план на сегодня</h2>
          <p className="text-sm text-[#555] capitalize mt-0.5">{today}</p>
        </div>

        {/* Task list */}
        <div className="px-6 py-4 max-h-80 overflow-y-auto">
          {pending.length === 0 ? (
            <p className="text-sm text-[#555] text-center py-4">Все задачи выполнены 🎉</p>
          ) : (
            <div className="space-y-1.5">
              {pending.map(task => {
                const dir = task.direction_id != null ? directions.find(d => d.id === task.direction_id) : null
                const c = dir ? getDirectionColor(dir.id) : null
                return (
                  <div key={task.task_id} className="group flex items-center gap-3 bg-[#141414] rounded-xl px-4 py-3">
                    {task.priority && task.priority !== 'none' && (
                      <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>
                        {priorityLabel(task.priority)}
                      </span>
                    )}
                    <span className="flex-1 text-sm text-[#e0e0e0] truncate">{task.title}</span>
                    {dir && c && (
                      <span
                        className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0 font-medium"
                        style={{ color: c, backgroundColor: c + '28' }}
                      >
                        {dir.name}
                      </span>
                    )}
                    <button
                      onClick={() => { onTakeNow(task.task_id); onClose() }}
                      className="opacity-0 group-hover:opacity-100 text-[10px] text-[#5060a0] hover:text-[#8090c8] shrink-0 transition-opacity whitespace-nowrap"
                    >
                      ▶ Взять
                    </button>
                  </div>
                )
              })}
              {done.length > 0 && (
                <p className="text-[11px] text-[#383838] pt-1">
                  Уже выполнено: {done.length}
                </p>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="px-6 py-4 border-t border-[#252525]">
          <button
            onClick={onClose}
            className="w-full py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors"
          >
            Начать день
          </button>
        </div>
      </div>
    </div>
  )
}
