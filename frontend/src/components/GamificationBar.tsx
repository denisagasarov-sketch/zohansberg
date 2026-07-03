// Геймификация на главном экране: серия дней (streak), кольца дня (время + закрытые шаги),
// разворачиваемая тепловая карта за год. Всё — «насколько хорошо я поработал» одним взглядом.
import { useState, useEffect, useCallback } from 'react'
import type { Gamification } from '../types'
import { api } from '../api'

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

function heatColor(seconds: number): string {
  if (!seconds) return '#1e1e1e'
  const h = seconds / 3600
  if (h < 1) return '#1d3a24'
  if (h < 2.5) return '#2e6b3f'
  if (h < 4.5) return '#3f9d57'
  return '#5ed17a'
}

// 53 недели × 7 дней, столбцы = недели (как на GitHub)
function Heatmap({ data }: { data: { day: string; seconds: number }[] }) {
  const map = new Map(data.map(d => [d.day, d.seconds]))
  const cells: { date: string; seconds: number }[] = []
  const today = new Date()
  const start = new Date(today); start.setDate(start.getDate() - 364)
  start.setDate(start.getDate() - start.getDay()) // выровнять на начало недели (вс)
  for (let d = new Date(start); d <= today; d.setDate(d.getDate() + 1)) {
    const key = d.toISOString().slice(0, 10)
    cells.push({ date: key, seconds: map.get(key) ?? 0 })
  }
  const weeks: typeof cells[] = []
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7))

  return (
    <div className="flex gap-[3px] overflow-x-auto pb-1">
      {weeks.map((w, i) => (
        <div key={i} className="flex flex-col gap-[3px]">
          {w.map(c => (
            <div key={c.date} title={`${c.date}: ${fmt(c.seconds)}`}
              className="w-[9px] h-[9px] rounded-[2px]" style={{ backgroundColor: heatColor(c.seconds) }} />
          ))}
        </div>
      ))}
    </div>
  )
}

export default function GamificationBar() {
  const [g, setG] = useState<Gamification | null>(null)
  const [showHeatmap, setShowHeatmap] = useState(false)

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
          <span className="text-base leading-none">🔥</span>
          <span className="text-xs text-[#c98a6a]">Сегодня ещё 0 подходов — не разорви цепочку из {g.streak} дн.</span>
        </div>
      )}
      <div className="flex items-center gap-5 flex-wrap">
        {/* Серия */}
        <div className="flex items-center gap-2">
          <span className="text-2xl leading-none">{g.streak > 0 ? '🔥' : '·'}</span>
          <div>
            <div className="text-sm text-[#f0f0f0] font-semibold leading-tight">{g.streak} дн.</div>
            <div className="text-[10px] text-[#666] uppercase tracking-wide">серия{g.best_streak > g.streak ? ` · рекорд ${g.best_streak}` : ''}</div>
          </div>
        </div>
        <div className="w-px h-8 bg-[#252525]" />
        <Ring pct={timePct} color="#5060a0" label="фокус сегодня" value={fmt(g.today.seconds)} />
        <Ring pct={stepsPct} color="#4a9d5f" label="шагов закрыто" value={String(g.today.subtasks_done)} />
        <button
          onClick={() => setShowHeatmap(v => !v)}
          className="ml-auto text-[10px] text-[#666] hover:text-[#8090c8] transition-colors self-start"
        >{showHeatmap ? 'скрыть карту' : 'карта года ▸'}</button>
      </div>
      {showHeatmap && (
        <div className="mt-3 pt-3 border-t border-[#252525]">
          <Heatmap data={g.heatmap} />
          <div className="text-[10px] text-[#555] mt-1">{g.active_days_total} активных дней всего</div>
        </div>
      )}
    </div>
  )
}
