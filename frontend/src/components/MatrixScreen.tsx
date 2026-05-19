import { useCallback } from 'react'
import type { Task } from '../types'
import { getQuadrant } from '../utils/quadrant'

interface Props {
  tasks: Task[]
  onClose: () => void
  onTaskClick: (task: Task) => void
}

const QUADRANTS = [
  { imp: 1, urg: 1 },
  { imp: 1, urg: 0 },
  { imp: 0, urg: 1 },
  { imp: 0, urg: 0 },
] as const

export default function MatrixScreen({ tasks, onClose, onTaskClick }: Props) {
  const activeTasks = tasks.filter(t => !t.done_at && !t.deleted_at)
  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold">Матрица Эйзенхауэра</h1>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <div className="grid grid-cols-2 gap-3 h-full" style={{ gridTemplateRows: '1fr 1fr' }}>
          {QUADRANTS.map(({ imp, urg }) => {
            const q = getQuadrant(imp, urg)
            const qTasks = activeTasks.filter(t => (t.is_important ?? 0) === imp && (t.is_urgent ?? 0) === urg)
            return (
              <div key={q.label} className="bg-[#1c1c1c] border rounded-xl overflow-hidden flex flex-col" style={{ borderColor: q.border }}>
                <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: q.border, backgroundColor: q.border + '30' }}>
                  <span className="text-sm font-semibold" style={{ color: q.color }}>{q.label}</span>
                  <span className="text-[10px] text-[#383838]">{qTasks.length}</span>
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-[#252525]/50">
                  {qTasks.length === 0 ? (
                    <div className="px-4 py-3 text-[11px] text-[#383838]">Нет задач</div>
                  ) : qTasks.map(task => (
                    <div
                      key={task.id}
                      onClick={() => onTaskClick(task)}
                      className="px-4 py-2.5 cursor-pointer hover:bg-[#252525]/40 transition-colors"
                    >
                      <div className="text-sm text-[#f0f0f0] truncate">{task.title}</div>
                      {task.deadline && (
                        <div className="text-[10px] text-[#555] mt-0.5">{new Date(task.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
