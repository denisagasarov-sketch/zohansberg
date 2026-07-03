// Геймификация на главном экране: серия дней (streak) и кольца дня (время + закрытые шаги).
// Тепловая карта года переехала в раздел «Статистика».
import { useState, useEffect, useCallback } from 'react'
import type { Gamification } from '../types'
import { api } from '../api'
import Icon from './Icon'

// Дневная цель по времени в фокусе (секунды) — базовая планка для кольца.
const DAY_GOAL_SECONDS = 4 * 3600

function fmt(s: number): string {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

function Ring({ pct, color, label, value }: { pct: number; color: string; label: string; value: string }) {
  const r = 20, c = 2 * Math.PI * r
  return (
    <div className="flex items-center gap-2">
      <svg width="52" height="52" viewBox="0 0 52 52" className="shrink-0 -rotate-90">
        <circle cx="26" cy="26" r={r} fill="none" stroke="#252525" strokeWidth="5" />
        <circle cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(1, pct))} className="transition-all duration-500" />
      </svg>
      <div>
        <div className="text-sm text-[#f0f0f0] font-semibold leading-tight">{value}</div>
        <div className="text-[10px] text-[#666] uppercase tracking-wide">{label}</div>
      </div>
    </div>
  )
}

export default function GamificationBar() {
  const [g, setG] = useState<Gamification | null>(null)

  const load = useCallback(() => { api.getGamification().then(setG).catch(() => {}) }, [])
  useEffect(() => {
    load()
    const h = () => load()
    window.addEventListener('gamification-updated', h)
    return () => window.removeEventListener('gamification-updated', h)
  }, [load])

  if (!g) return null

  const timePct = g.today.seconds / DAY_GOAL_SECONDS
  const stepsPct = g.today.subtasks_done / 5 // ориентир — 5 шагов в день
  const idleToday = g.today.seconds === 0 && g.today.subtasks_done === 0 && g.today.tasks_done === 0

  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg px-4 py-3">
      {/* Мягкое напоминание: серия под угрозой, но день ещё пустой */}
      {idleToday && g.streak > 0 && (
        <div className="mb-3 flex items-center gap-2 bg-[#241c1c] border border-[#3a2a2a] rounded px-3 py-1.5">
          <span className="text-[#e08a45] shrink-0"><Icon name="flame" size={16} /></span>
          <span className="text-xs text-[#c98a6a]">Сегодня ещё 0 подходов — не разорви цепочку из {g.streak} дн.</span>
        </div>
      )}
      <div className="flex items-center gap-5 flex-wrap">
        {/* Серия */}
        <div className="flex items-center gap-2">
          <Icon name="flame" size={24} style={{ color: g.streak > 0 ? '#e08a45' : '#555' }} />
          <div>
            <div className="text-sm text-[#f0f0f0] font-semibold leading-tight">{g.streak} дн.</div>
            <div className="text-[10px] text-[#666] uppercase tracking-wide">серия{g.best_streak > g.streak ? ` · рекорд ${g.best_streak}` : ''}</div>
          </div>
        </div>
        <div className="w-px h-8 bg-[#252525]" />
        <Ring pct={timePct} color="#5060a0" label="фокус сегодня" value={fmt(g.today.seconds)} />
        <Ring pct={stepsPct} color="#4a9d5f" label="шагов закрыто" value={String(g.today.subtasks_done)} />
      </div>
    </div>
  )
}
