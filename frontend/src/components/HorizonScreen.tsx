import { useState, useMemo } from 'react'
import type { Task, Direction } from '../types'
import { getDirectionColor } from '../utils/directionColors'
import { priorityColor } from '../utils/priority'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onClose: () => void
  onTaskClick: (task: Task) => void
}

type Range = 'week' | 'month' | 'quarter'

function addDays(d: Date, n: number) {
  const r = new Date(d); r.setDate(r.getDate() + n); return r
}

function dateStr(d: Date) { return d.toISOString().slice(0, 10) }

function daysBetween(a: Date, b: Date) {
  return Math.round((b.getTime() - a.getTime()) / 86400000)
}

function fmtDate(iso: string) {
  const d = new Date(iso + 'T12:00:00')
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

const RANGE_DAYS: Record<Range, number> = { week: 7, month: 30, quarter: 90 }

export default function HorizonScreen({ tasks, directions, onClose, onTaskClick }: Props) {
  const [range, setRange] = useState<Range>('month')
  const [filterDirId, setFilterDirId] = useState<number | null | 'all'>('all')

  const today = new Date(); today.setHours(0, 0, 0, 0)
  const endDate = addDays(today, RANGE_DAYS[range])

  // Tasks with deadlines in range, not done
  const deadlineTasks = useMemo(() => {
    return tasks.filter(t => {
      if (t.done_at || t.deleted_at || !t.deadline) return false
      const d = new Date(t.deadline + 'T12:00:00')
      if (filterDirId !== 'all' && t.direction_id !== filterDirId) return false
      return d >= today && d <= endDate
    }).sort((a, b) => (a.deadline ?? '').localeCompare(b.deadline ?? ''))
  }, [tasks, range, filterDirId])

  // Tasks without deadlines (backlog in plan horizon context)
  const noDeadline = useMemo(() => {
    return tasks.filter(t => {
      if (t.done_at || t.deleted_at || t.someday || t.deadline) return false
      if (filterDirId !== 'all' && t.direction_id !== filterDirId) return false
      return true
    })
  }, [tasks, filterDirId])

  // Overdue
  const overdue = useMemo(() => {
    return tasks.filter(t => {
      if (t.done_at || t.deleted_at || !t.deadline) return false
      const d = new Date(t.deadline + 'T12:00:00')
      if (filterDirId !== 'all' && t.direction_id !== filterDirId) return false
      return d < today
    }).sort((a, b) => (a.deadline ?? '').localeCompare(b.deadline ?? ''))
  }, [tasks, filterDirId])

  const renderTask = (task: Task) => {
    const dir = task.direction_id != null ? directions.find(d => d.id === task.direction_id) : null
    const c = dir ? getDirectionColor(dir.id) : '#383838'
    const daysLeft = task.deadline ? daysBetween(today, new Date(task.deadline + 'T12:00:00')) : null
    const urgent = daysLeft !== null && daysLeft <= 3
    return (
      <div key={task.id}
        onClick={() => onTaskClick(task)}
        className="flex items-center gap-3 px-4 py-2.5 hover:bg-[#252525]/50 cursor-pointer transition-colors rounded-lg group">
        {task.priority && task.priority !== 'none' && (
          <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>
            {task.priority === 'I' ? 'Ⅰ' : task.priority === 'II' ? 'Ⅱ' : 'Ⅲ'}
          </span>
        )}
        <span className="flex-1 text-sm text-[#e0e0e0] truncate">{task.title}</span>
        {task.recurrence && <span className="text-[10px] text-[#5060a0]/60 shrink-0">↺</span>}
        {dir && <span className="text-[9px] px-1.5 py-0.5 rounded-full shrink-0" style={{ color: c, backgroundColor: c + '28' }}>{dir.name}</span>}
        {task.deadline && (
          <span className={`text-[11px] font-mono shrink-0 ${urgent ? 'text-red-400 font-bold' : 'text-[#b8900a]'}`}>
            {daysLeft === 0 ? 'сегодня' : daysLeft === 1 ? 'завтра' : `${fmtDate(task.deadline)}`}
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold flex-1">Горизонт планирования</h1>
        <div className="flex gap-1">
          {(['week', 'month', 'quarter'] as Range[]).map(r => (
            <button key={r} onClick={() => setRange(r)}
              className={`px-3 py-1 rounded text-xs transition-colors border ${range === r ? 'bg-[#5060a0] border-[#5060a0] text-white' : 'border-[#252525] text-[#666] hover:border-[#5060a0]/50'}`}>
              {r === 'week' ? '7 дней' : r === 'month' ? '30 дней' : '90 дней'}
            </button>
          ))}
        </div>
      </div>

      {/* Direction filter */}
      <div className="px-6 py-2 flex gap-1.5 flex-wrap shrink-0 border-b border-[#252525]">
        <button onClick={() => setFilterDirId('all')}
          className={`px-2.5 py-1 rounded-lg text-xs transition-colors ${filterDirId === 'all' ? 'bg-[#5060a0]/20 text-[#8090c8] border border-[#5060a0]/40' : 'text-[#555] hover:text-[#999]'}`}>
          Все
        </button>
        {directions.map(dir => {
          const c = getDirectionColor(dir.id)
          const active = filterDirId === dir.id
          return (
            <button key={dir.id} onClick={() => setFilterDirId(active ? 'all' : dir.id)}
              className="px-2.5 py-1 rounded-lg text-xs transition-colors border"
              style={{ color: active ? c : '#555', borderColor: active ? c + '60' : '#252525', backgroundColor: active ? c + '18' : 'transparent' }}>
              {dir.name}
            </button>
          )
        })}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {/* Overdue */}
        {overdue.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-semibold tracking-widest text-red-500 uppercase">Просрочено</span>
              <span className="text-[10px] text-red-500/60">{overdue.length}</span>
            </div>
            <div className="bg-[#1c1c1c] border border-red-900/30 rounded-xl overflow-hidden divide-y divide-[#252525]">
              {overdue.map(renderTask)}
            </div>
          </section>
        )}

        {/* Timeline buckets */}
        {(() => {
          const buckets: { label: string; from: Date; to: Date }[] = []
          if (range === 'week') {
            for (let i = 0; i < 7; i++) {
              const d = addDays(today, i)
              buckets.push({ label: d.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'short' }), from: d, to: d })
            }
          } else if (range === 'month') {
            buckets.push({ label: 'Эта неделя', from: today, to: addDays(today, 6) })
            buckets.push({ label: 'Следующая неделя', from: addDays(today, 7), to: addDays(today, 13) })
            buckets.push({ label: 'Через 2 недели', from: addDays(today, 14), to: addDays(today, 20) })
            buckets.push({ label: 'Конец месяца', from: addDays(today, 21), to: addDays(today, 30) })
          } else {
            buckets.push({ label: 'Этот месяц', from: today, to: addDays(today, 29) })
            buckets.push({ label: 'Следующий месяц', from: addDays(today, 30), to: addDays(today, 59) })
            buckets.push({ label: 'Через 2–3 месяца', from: addDays(today, 60), to: addDays(today, 89) })
          }
          return buckets.map(bucket => {
            const bStr = dateStr(bucket.from)
            const eStr = dateStr(bucket.to)
            const bt = deadlineTasks.filter(t => t.deadline! >= bStr && t.deadline! <= eStr)
            if (bt.length === 0) return null
            return (
              <section key={bucket.label}>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase">{bucket.label}</span>
                  <span className="text-[10px] text-[#383838]">{bt.length}</span>
                </div>
                <div className="bg-[#1c1c1c] border border-[#252525] rounded-xl overflow-hidden divide-y divide-[#252525]">
                  {bt.map(renderTask)}
                </div>
              </section>
            )
          })
        })()}

        {/* No deadline */}
        {noDeadline.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase">Без дедлайна</span>
              <span className="text-[10px] text-[#383838]">{noDeadline.length}</span>
            </div>
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-xl overflow-hidden divide-y divide-[#252525]">
              {noDeadline.slice(0, 20).map(renderTask)}
              {noDeadline.length > 20 && (
                <p className="px-4 py-2 text-xs text-[#555]">и ещё {noDeadline.length - 20}…</p>
              )}
            </div>
          </section>
        )}

        {deadlineTasks.length === 0 && overdue.length === 0 && (
          <div className="flex items-center justify-center h-32 text-[#383838] text-sm">
            Нет задач с дедлайнами в этом периоде
          </div>
        )}
      </div>
    </div>
  )
}
