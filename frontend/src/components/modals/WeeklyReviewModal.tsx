import { useState, useEffect } from 'react'
import type { Task, Direction } from '../../types'
import { api } from '../../api'
import { playSound } from '../../sound'
import { getDirectionColor } from '../../utils/directionColors'
import { priorityLabel, priorityColor } from '../../utils/priority'

interface Props {
  tasks: Task[]
  directions: Direction[]
  onClose: () => void
  onLater: () => void
}

function fmt(s: number) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  if (h > 0 && m > 0) return `${h}ч ${m}м`
  if (h > 0) return `${h}ч`
  return `${m}м`
}

export default function WeeklyReviewModal({ tasks, directions, onClose, onLater }: Props) {
  const [step, setStep] = useState<1 | 2>(1)
  const [data, setData] = useState<any>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  useEffect(() => {
    playSound('fanfare', 0.7)
    api.getWeeklySummary().then(setData).catch(() => {})
  }, [])

  const weekRange = (() => {
    const end = new Date()
    const start = new Date(); start.setDate(start.getDate() - 6)
    const fmt2 = (d: Date) => d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
    return `${fmt2(start)} — ${fmt2(end)}`
  })()

  const nextMonday = (() => {
    const d = new Date()
    const day = d.getDay()
    const diff = day === 0 ? 1 : 8 - day
    d.setDate(d.getDate() + diff)
    return d.toISOString().slice(0, 10)
  })()

  const available = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday)
  const byDir: { dir: Direction | null; tasks: Task[] }[] = []
  directions.forEach(dir => {
    const dt = available.filter(t => t.direction_id === dir.id)
    if (dt.length > 0) byDir.push({ dir, tasks: dt })
  })
  const noDir = available.filter(t => t.direction_id == null)
  if (noDir.length > 0) byDir.push({ dir: null, tasks: noDir })

  const toggle = (id: number) => setSelected(p => {
    const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n
  })

  const handleSavePlan = async () => {
    if (selected.size > 0) await api.setDayPlan(nextMonday, [...selected]).catch(() => {})
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80" onClick={onLater} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">

        {/* Header bar */}
        <div className="px-6 pt-5 pb-3 shrink-0" style={{ background: 'linear-gradient(180deg,#1a2030 0%,#1c1c1c 100%)' }}>
          <div className="text-xs text-[#5060a0] font-semibold tracking-widest uppercase mb-1">
            Шаг {step} из 2 · Еженедельный обзор
          </div>
          <h2 className="text-xl font-bold text-[#f0f0f0]">
            {step === 1 ? 'Итог недели' : 'Что на следующей неделе?'}
          </h2>
          <p className="text-sm text-[#555] mt-0.5">{weekRange}</p>
        </div>

        {step === 1 ? (
          <>
            <div className="px-6 py-3 shrink-0">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{data?.done_count ?? '…'}</div>
                  <div className="text-xs text-[#555] mt-0.5">задач выполнено</div>
                </div>
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{data ? fmt(data.time_seconds) : '…'}</div>
                  <div className="text-xs text-[#555] mt-0.5">время в работе</div>
                </div>
              </div>
            </div>

            <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0 space-y-3">
              {/* Time by direction */}
              {data?.by_direction?.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">По направлениям</div>
                  <div className="space-y-1.5">
                    {data.by_direction.map((d: any, i: number) => {
                      const dir = directions.find(x => x.id === d.direction_id)
                      const c = dir ? getDirectionColor(dir.id) : '#5060a0'
                      const maxSec = data.by_direction[0]?.seconds ?? 1
                      return (
                        <div key={i} className="bg-[#141414] rounded-lg px-3 py-2">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-medium" style={{ color: c }}>{d.direction_name}</span>
                            <span className="text-xs font-mono text-[#999]">{fmt(d.seconds)}</span>
                          </div>
                          <div className="h-1 bg-[#252525] rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${(d.seconds / maxSec) * 100}%`, backgroundColor: c }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Done tasks */}
              {data?.done_tasks?.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Выполнено</div>
                  <div className="space-y-1">
                    {data.done_tasks.map((t: any, i: number) => (
                      <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-[#141414] rounded-lg">
                        <span className="text-[#4a7a4a] text-xs shrink-0">✓</span>
                        <span className="flex-1 text-sm text-[#c0c0c0] truncate">{t.title}</span>
                        {t.direction && <span className="text-[10px] text-[#555] shrink-0">{t.direction}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 shrink-0 border-t border-[#252525] flex gap-2">
              <button onClick={onLater} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">Позже</button>
              <button onClick={() => setStep(2)} className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors">Планировать неделю →</button>
            </div>
          </>
        ) : (
          <>
            <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0 pt-2">
              {byDir.map(({ dir, tasks: dt }) => {
                const c = dir ? getDirectionColor(dir.id) : null
                return (
                  <div key={dir?.id ?? 'none'} className="mb-4">
                    <div className="text-[10px] font-semibold tracking-widest uppercase mb-1.5" style={{ color: c ?? '#383838' }}>
                      {dir?.name ?? 'Без направления'}
                    </div>
                    <div className="space-y-1">
                      {dt.map(task => {
                        const active = selected.has(task.id)
                        return (
                          <button key={task.id} onClick={() => toggle(task.id)}
                            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-colors ${active ? 'bg-[#5060a0]/20 border border-[#5060a0]/40' : 'bg-[#141414] border border-transparent hover:bg-[#1a1a1a]'}`}>
                            <span className={`w-4 h-4 rounded shrink-0 border flex items-center justify-center text-[10px] ${active ? 'border-[#5060a0] bg-[#5060a0] text-white' : 'border-[#333]'}`}>{active ? '✓' : ''}</span>
                            {task.priority && task.priority !== 'none' && (
                              <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(task.priority) }}>{priorityLabel(task.priority)}</span>
                            )}
                            <span className="flex-1 text-sm text-[#c0c0c0] truncate">{task.title}</span>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
            <div className="px-6 py-4 shrink-0 border-t border-[#252525] flex gap-2">
              <button onClick={onClose} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">Пропустить</button>
              <button onClick={handleSavePlan} className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors">
                Сохранить план {selected.size > 0 ? `(${selected.size})` : ''}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
