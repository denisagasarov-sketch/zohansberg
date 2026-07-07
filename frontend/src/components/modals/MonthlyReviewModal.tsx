import { useState, useEffect } from 'react'
import type { Task, Direction } from '../../types'
import { api } from '../../api'
import { playSound } from '../../sound'
import { getDirectionColor } from '../../utils/directionColors'
import { priorityLabel, priorityColor } from '../../utils/priority'

interface Props {
  isQuarterly?: boolean
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

export default function MonthlyReviewModal({ isQuarterly = false, tasks, directions, onClose, onLater }: Props) {
  const [step, setStep] = useState<1 | 2>(1)
  const [data, setData] = useState<any>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const months = isQuarterly ? 3 : 1

  useEffect(() => {
    playSound('fanfare', 0.6)
    api.getMonthlySummary(months).then(setData).catch(() => {})
  }, [months])

  const title = isQuarterly ? 'Квартальный обзор' : 'Месячный обзор'
  const periodLabel = isQuarterly ? 'за квартал' : 'за месяц'

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

  const nextMonth = new Date()
  nextMonth.setMonth(nextMonth.getMonth() + 1, 1)
  const nextMonthDate = nextMonth.toISOString().slice(0, 10)

  const handleSavePlan = async () => {
    if (selected.size > 0) await api.setDayPlan(nextMonthDate, [...selected]).catch(() => {})
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/80" onClick={onLater} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">

        <div className="px-6 pt-5 pb-3 shrink-0" style={{ background: 'linear-gradient(180deg,#201520 0%,#1c1c1c 100%)' }}>
          <div className="text-xs text-[#a050a0] font-semibold tracking-widest uppercase mb-1">
            Шаг {step} из 2 · {title}
          </div>
          <h2 className="text-xl font-bold text-[#f0f0f0]">
            {step === 1 ? `Итог ${periodLabel}` : 'Приоритеты на следующий период'}
          </h2>
        </div>

        {step === 1 ? (
          <>
            <div className="px-6 py-3 shrink-0">
              <div className="grid grid-cols-3 gap-3">
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{data?.done_count ?? '…'}</div>
                  <div className="text-xs text-[#555] mt-0.5">задач</div>
                </div>
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{data ? fmt(data.time_seconds) : '…'}</div>
                  <div className="text-xs text-[#555] mt-0.5">в работе</div>
                </div>
                <div className="bg-[#141414] rounded-xl p-3">
                  <div className="text-2xl font-bold text-[#f0f0f0]">{data?.active_days ?? '…'}</div>
                  <div className="text-xs text-[#555] mt-0.5">рабочих дней</div>
                </div>
              </div>
            </div>

            <div className="px-6 pb-2 overflow-y-auto flex-1 min-h-0 space-y-4">
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
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-[#555]">{d.task_count} задач</span>
                              <span className="text-xs font-mono text-[#999]">{fmt(d.seconds)}</span>
                            </div>
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

              {data?.done_tasks?.length > 0 && (
                <div>
                  <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">
                    Выполнено ({data.done_tasks.length})
                  </div>
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
              <button onClick={() => setStep(2)} className="flex-1 py-2.5 bg-[#a050a0] hover:bg-[#c070c0] rounded-xl text-sm text-white font-medium transition-colors">
                Приоритеты →
              </button>
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
                            className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-left transition-colors ${active ? 'bg-[#a050a0]/20 border border-[#a050a0]/40' : 'bg-[#141414] border border-transparent hover:bg-[#1a1a1a]'}`}>
                            <span className={`w-4 h-4 rounded shrink-0 border flex items-center justify-center text-[10px] ${active ? 'border-[#a050a0] bg-[#a050a0] text-white' : 'border-[#333]'}`}>{active ? '✓' : ''}</span>
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
              <button onClick={handleSavePlan} className="flex-1 py-2.5 bg-[#a050a0] hover:bg-[#c070c0] rounded-xl text-sm text-white font-medium transition-colors">
                Сохранить {selected.size > 0 ? `(${selected.size})` : ''}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
