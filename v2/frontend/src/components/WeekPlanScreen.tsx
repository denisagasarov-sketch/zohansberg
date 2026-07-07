// План недели по направлениям: сколько часов хочу вложить в каждое направление
// vs сколько уже вложил на этой неделе. Цели редактируются прямо здесь —
// это и есть недельное планирование, которого раньше не было видно.
import { useState, useEffect, useCallback } from 'react'
import type { Direction } from '../types'
import { api } from '../api'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  directions: Direction[]
  onClose: () => void
  onChanged: () => void
}

function fmt(sec: number): string {
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

export default function WeekPlanScreen({ directions, onClose, onChanged }: Props) {
  const [actual, setActual] = useState<Record<number, number>>({})
  const [goals, setGoals] = useState<Record<number, string>>({})

  const load = useCallback(() => {
    api.getWeeklyTime().then(rows => {
      const m: Record<number, number> = {}
      rows.forEach(r => { if (r.direction_id != null) m[r.direction_id] = r.seconds })
      setActual(m)
    }).catch(() => {})
  }, [])
  useEffect(() => { load() }, [load])
  useEffect(() => {
    setGoals(Object.fromEntries(directions.map(d => [d.id, d.weekly_goal_seconds ? String(Math.round(d.weekly_goal_seconds / 3600)) : ''])))
  }, [directions])

  const saveGoal = async (id: number) => {
    const h = parseFloat(goals[id] || '0')
    await api.updateDirection(id, { weekly_goal_seconds: Math.round((Number.isFinite(h) ? h : 0) * 3600) }).catch(() => {})
    onChanged()
  }

  const active = directions.filter(d => !d.archived)
  const totalGoal = active.reduce((s, d) => s + (parseFloat(goals[d.id] || '0') || 0), 0)
  const totalActual = active.reduce((s, d) => s + (actual[d.id] ?? 0), 0)

  return (
    <div className="h-full flex flex-col bg-[#141312] text-[#ece7df]">
      <div className="flex items-center gap-3 px-6 py-3.5 border-b border-border bg-header/40 shrink-0">
        <button onClick={onClose} className="btn-ghost -ml-2 !px-2 !py-1 text-[13px]">← Назад</button>
        <h1 className="text-[17px] font-semibold tracking-tight flex-1">План недели</h1>
        <span className="text-xs text-[#9c958a]">{fmt(totalActual)} из {totalGoal}ч цели</span>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <p className="text-xs text-[#9c958a] mb-4">
          Сколько времени хочешь вложить в каждое направление за неделю. Полоса — сколько уже вложил (Пн–Вс).
        </p>
        <div className="space-y-3 max-w-2xl">
          {active.map(d => {
            const done = actual[d.id] ?? 0
            const goalSec = (parseFloat(goals[d.id] || '0') || 0) * 3600
            const pct = goalSec > 0 ? Math.min(100, Math.round((done / goalSec) * 100)) : 0
            const color = getDirectionColor(d.id)
            const over = goalSec > 0 && done > goalSec
            return (
              <div key={d.id} className="bg-card border border-border rounded-xl px-4 py-3">
                <div className="flex items-center gap-2 mb-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-sm text-[#ece7df] flex-1">{d.name}</span>
                  <span className="text-xs text-[#9c958a]">{fmt(done)}</span>
                  <span className="text-[#453f37]">/</span>
                  <input
                    type="number" min={0} value={goals[d.id] ?? ''}
                    onChange={e => setGoals(g => ({ ...g, [d.id]: e.target.value }))}
                    onBlur={() => saveGoal(d.id)}
                    onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
                    placeholder="0"
                    className="w-12 bg-[#0f0e0d] border border-[#2a2723] rounded px-1.5 py-0.5 text-xs text-[#ece7df] text-center focus:outline-none focus:border-[#e0a458]"
                  />
                  <span className="text-xs text-[#9c958a]">ч/нед</span>
                </div>
                <div className="h-2 bg-[#2a2723] rounded-full overflow-hidden">
                  <div className="h-full transition-all duration-300" style={{ width: `${pct}%`, backgroundColor: over ? '#82a877' : color }} />
                </div>
                {goalSec > 0 && (
                  <div className="text-[10px] text-[#6f695f] mt-1">
                    {over ? `цель выполнена (+${fmt(done - goalSec)})` : `осталось ${fmt(goalSec - done)} · ${pct}%`}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {active.length === 0 && <p className="text-sm text-[#9c958a]">Нет направлений. Добавь их в настройках.</p>}
      </div>
    </div>
  )
}
