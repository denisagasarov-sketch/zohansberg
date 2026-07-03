// «Сделано сегодня» — раскрывающийся блок под очередью.
// Выполненные задачи больше не «улетают в никуда»: видно список, время,
// и любую можно вернуть в работу одним кликом.
import { useState } from 'react'
import type { Task, Direction } from '../types'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onRestore: (taskId: number) => void
  onTaskClick: (task: Task) => void
}

function isToday(iso: string): boolean {
  const d = new Date(iso)
  const n = new Date()
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate()
}

function formatTime(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

export default function DoneTodayBlock({ tasks, directions, onRestore, onTaskClick }: Props) {
  const [open, setOpen] = useState(false)

  const done = tasks
    .filter(t => t.done_at && !t.deleted_at && isToday(t.done_at))
    .sort((a, b) => (b.done_at ?? '').localeCompare(a.done_at ?? ''))

  if (done.length === 0) return null

  const totalSeconds = done.reduce((s, t) => s + (t.duration_fact || 0), 0)

  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full px-4 py-2.5 flex items-center gap-2 text-left hover:bg-[#252525]/40 transition-colors"
      >
        <span className="text-[#4a9d5f] text-sm">✓</span>
        <span className="text-sm text-[#999]">
          Сделано сегодня: <span className="text-[#f0f0f0] font-medium">{done.length}</span>
        </span>
        {totalSeconds > 0 && <span className="text-xs text-[#5060a0]">{formatTime(totalSeconds)}</span>}
        <span className="ml-auto text-[#666] text-xs">{open ? '▾ свернуть' : '▸ показать'}</span>
      </button>

      {open && (
        <ul className="divide-y divide-[#252525] border-t border-[#252525]">
          {done.map(task => {
            const dir = directions.find(d => d.id === task.direction_id)
            return (
              <li
                key={task.id}
                className="group flex items-center gap-3 px-4 py-2 hover:bg-[#252525]/40 cursor-pointer transition-colors"
                onClick={() => onTaskClick(task)}
              >
                <span className="text-[#4a9d5f]/60 text-xs shrink-0">✓</span>
                <span className="flex-1 text-sm text-[#999] truncate line-through decoration-[#444]">{task.title}</span>
                {task.notes && <span className="text-[10px] shrink-0 opacity-60" title={task.notes}>📝</span>}
                {dir && <span className="text-[10px] text-[#666] shrink-0">{dir.name}</span>}
                {task.duration_fact > 0 && <span className="text-[10px] text-[#5060a0] shrink-0">{formatTime(task.duration_fact)}</span>}
                {task.done_at && (
                  <span className="text-[10px] text-[#383838] shrink-0">
                    {new Date(task.done_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
                <button
                  onClick={e => { e.stopPropagation(); onRestore(task.id) }}
                  className="text-[10px] text-[#777] hover:text-[#8090c8] border border-[#333] hover:border-[#5060a0] rounded px-1.5 py-0.5 shrink-0 transition-colors"
                  title="Вернуть в работу (снимет отметку «выполнена» и положит в «Следом»)"
                >↩ вернуть</button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
