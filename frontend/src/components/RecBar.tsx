import { useState } from 'react'
import type { Recommendation, Task } from '../types'

interface Props {
  recommendation: Recommendation | null
  onGetNext: (skipId?: number) => void
  onSetNext: (taskId: number) => void
  onTaskClick: (task: Task) => void
}

function formatDeadline(d: string | null) {
  if (!d) return 'не задан'
  const date = new Date(d)
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

function daysSince(dateStr: string | null | undefined) {
  if (!dateStr) return 0
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / 86400_000)
}

export default function RecBar({ recommendation, onGetNext, onSetNext, onTaskClick }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!recommendation?.task) {
    return (
      <div className="border-t border-[#252525] pt-3">
        <div className="text-xs text-[#383838]">Нет задач для рекомендации</div>
      </div>
    )
  }

  const { task, reason } = recommendation

  return (
    <div className="border-t border-[#252525] pt-3">
      <div className="text-xs text-[#383838] mb-1.5">↳ Рекомендую</div>
      <div
        className="text-sm text-[#f0f0f0] cursor-pointer hover:text-[#8090c8] transition-colors mb-1.5 truncate"
        onClick={() => onTaskClick(task)}
        title={task.title}
      >
        {task.title}
      </div>
      {reason && <div className="text-xs text-[#666] mb-2 line-clamp-1">{reason}</div>}

      {expanded && (
        <div className="bg-[#141414] border border-[#252525] rounded p-2.5 mb-2 text-xs space-y-1">
          <div className="flex justify-between">
            <span className="text-[#666]">Приоритет:</span>
            <span className="text-[#f0f0f0]">{task.priority === 'high' ? 'Высокий' : task.priority === 'medium' ? 'Средний' : 'Низкий'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#666]">Без движения:</span>
            <span className="text-[#f0f0f0]">{daysSince(task.updated_at)} д.</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#666]">Дедлайн:</span>
            <span className="text-[#f0f0f0]">{formatDeadline(task.deadline)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#666]">Слот:</span>
            <span className="text-[#f0f0f0]">{task.slot}</span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-1.5">
        <button
          onClick={() => setExpanded(e => !e)}
          className="px-2 py-1 text-[10px] bg-[#252525] hover:bg-[#383838] rounded transition-colors text-[#666]"
        >
          {expanded ? 'Скрыть' : 'Почему?'}
        </button>
        <button
          onClick={() => onGetNext(recommendation.task.id)}
          className="px-2 py-1 text-[10px] bg-[#252525] hover:bg-[#383838] rounded transition-colors text-[#666]"
        >
          Другую
        </button>
        <button
          onClick={() => onSetNext(task.id)}
          className="px-2 py-1 text-[10px] bg-[#5060a0]/30 hover:bg-[#5060a0] rounded transition-colors text-[#8090c8]"
        >
          Следом →
        </button>
      </div>
    </div>
  )
}
