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
        <circle cx="26" cy="26" r={r} fill="none" stroke="#2a2723" strokeWidth="5" />
        <circle cx="26" cy="26" r={r} fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - Math.min(1, pct))} className="transition-all duration-500" />
      </svg>
      <div>
        <div className="text-sm text-[#ece7df] font-semibold leading-tight">{value}</div>
        <div className="text-[10px] text-[#9c958a] uppercase tracking-wide">{label}</div>
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
    <div className="bg-card border border-border rounded-xl px-4 py-3">
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
          <Icon name="flame" size={24} style={{ color: g.streak > 0 ? '#e08a45' : '#6f695f' }} />
          <div>
            <div className="text-sm text-[#ece7df] font-semibold leading-tight">{g.streak} дн.</div>
            <div className="text-[10px] text-[#9c958a] uppercase tracking-wide">серия{g.best_streak > g.streak ? ` · рекорд ${g.best_streak}` : ''}</div>
          </div>
        </div>
        <div className="w-px h-8 bg-[#2a2723]" />
        <Ring pct={timePct} color="#e0a458" label="фокус сегодня" value={fmt(g.today.seconds)} />
        <Ring pct={stepsPct} color="#82a877" label="шагов закрыто" value={String(g.today.subtasks_done)} />
      </div>
    </div>
  )
}
