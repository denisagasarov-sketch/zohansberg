// «Пульс» — живая статистика: карта фокуса час×день, инсайты потока, орбиты направлений.
import { useState, useEffect } from 'react'
import type { Direction } from '../types'
import { api2 } from '../api'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  directions: Direction[]
  onClose: () => void
  onClassic: () => void
}

const WEEKDAYS = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
const ORDER = [1, 2, 3, 4, 5, 6, 0] // пн..вс
const HOURS = Array.from({ length: 18 }, (_, i) => i + 6) // 6..23

function fmt(s: number): string {
  if (s < 60) return `${Math.round(s)}с`
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

function heatColor(v: number): string {
  // 0..1 → прозрачный янтарь → плотный янтарь
  if (v <= 0) return 'rgba(255,255,255,0.03)'
  const a = 0.10 + v * 0.85
  return `rgba(224, 164, 88, ${a.toFixed(2)})`
}

export default function LiveStats({ directions, onClose, onClassic }: Props) {
  const [heatmap, setHeatmap] = useState<{ weekday: number; hour: number; seconds: number }[]>([])
  const [flow, setFlow] = useState<Awaited<ReturnType<typeof api2.getFlow>> | null>(null)
  const [balance, setBalance] = useState<{ direction_id: number | null; seconds: number }[]>([])

  useEffect(() => {
    api2.getHeatmap(90).then(r => setHeatmap(r.rows)).catch(() => {})
    api2.getFlow().then(setFlow).catch(() => {})
    api2.getDirectionBalance(30).then(r => setBalance(r.rows)).catch(() => {})
  }, [])

  const cell = new Map<string, number>()
  let maxSec = 1
  heatmap.forEach(r => {
    cell.set(`${r.weekday}:${r.hour}`, r.seconds)
    if (r.seconds > maxSec) maxSec = r.seconds
  })

  const bestHourSet = new Set((flow?.best_hours ?? []).map(h => h.hour))
  const totalBalance = balance.reduce((s, b) => s + b.seconds, 0) || 1
  const sortedBalance = [...balance].sort((a, b) => b.seconds - a.seconds)

  return (
    <div className="absolute inset-0 z-40 bg-bg overflow-y-auto animate-fade-in">
      <div className="flex items-center gap-3 px-6 py-3.5 border-b border-border bg-header/40 sticky top-0 backdrop-blur z-10">
        <button onClick={onClose} className="btn-ghost -ml-2 !px-2 !py-1 text-[13px]">← Назад</button>
        <h1 className="text-[17px] font-semibold tracking-tight flex-1">Пульс</h1>
        <button onClick={onClassic} className="btn-ghost text-[12px]">Классическая статистика →</button>
      </div>

      <div className="max-w-[1000px] mx-auto px-6 py-6 flex flex-col gap-5">

        {/* Инсайты потока */}
        <div className="grid grid-cols-4 max-md:grid-cols-2 gap-3">
          <div className="card p-4">
            <div className="text-[22px] font-mono font-semibold tabular-nums text-accent-light leading-none">
              {flow?.best_hours?.[0] != null ? `${flow.best_hours[0].hour}:00` : '—'}
            </div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">твой звёздный час</div>
          </div>
          <div className="card p-4">
            <div className="text-[22px] font-mono font-semibold tabular-nums text-text leading-none">
              {flow?.best_weekday ? WEEKDAYS[flow.best_weekday.weekday] : '—'}
            </div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">самый мощный день</div>
          </div>
          <div className="card p-4">
            <div className="text-[22px] font-mono font-semibold tabular-nums text-text leading-none">{flow ? fmt(flow.median_seconds) : '—'}</div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">типичная сессия</div>
          </div>
          <div className="card p-4">
            <div className="text-[22px] font-mono font-semibold tabular-nums text-text leading-none">{flow ? fmt(flow.total_seconds) : '—'}</div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">фокуса за 90 дней</div>
          </div>
        </div>

        {/* Карта фокуса */}
        <div className="card p-5">
          <div className="flex items-baseline gap-2 mb-4">
            <span className="section-label">Карта фокуса</span>
            <span className="text-[11px] text-text-muted">90 дней · когда ты реально работаешь</span>
          </div>
          <div className="grid" style={{ gridTemplateColumns: `34px repeat(${HOURS.length}, 1fr)`, gap: '3px' }}>
            <div />
            {HOURS.map(h => (
              <div key={h} className={`text-center text-[9px] tabular-nums ${bestHourSet.has(h) ? 'text-accent-light font-semibold' : 'text-text-faint'}`}>{h}</div>
            ))}
            {ORDER.map(wd => (
              [
                <div key={`l${wd}`} className={`text-[10px] pr-1 flex items-center ${flow?.best_weekday?.weekday === wd ? 'text-accent-light font-semibold' : 'text-text-muted'}`}>{WEEKDAYS[wd]}</div>,
                ...HOURS.map(h => {
                  const s = cell.get(`${wd}:${h}`) ?? 0
                  return (
                    <div
                      key={`${wd}:${h}`}
                      title={s > 0 ? `${WEEKDAYS[wd]} ${h}:00 — ${fmt(s)}` : `${WEEKDAYS[wd]} ${h}:00`}
                      className="aspect-square rounded-[3px] transition-transform hover:scale-125"
                      style={{ backgroundColor: heatColor(s / maxSec) }}
                    />
                  )
                }),
              ]
            ))}
          </div>
          <div className="flex items-center gap-1.5 mt-3 justify-end">
            <span className="text-[9px] text-text-faint">меньше</span>
            {[0, 0.25, 0.5, 0.75, 1].map(v => <span key={v} className="w-3 h-3 rounded-[3px]" style={{ backgroundColor: heatColor(v) }} />)}
            <span className="text-[9px] text-text-faint">больше</span>
          </div>
        </div>

        {/* Баланс направлений */}
        <div className="card p-5">
          <div className="flex items-baseline gap-2 mb-4">
            <span className="section-label">Баланс направлений</span>
            <span className="text-[11px] text-text-muted">30 дней</span>
          </div>
          {sortedBalance.length === 0 ? (
            <div className="text-[13px] text-text-muted py-4 text-center">Пока нет сессий</div>
          ) : (
            <div className="space-y-2.5">
              {sortedBalance.map(b => {
                const dir = b.direction_id != null ? directions.find(d => d.id === b.direction_id) : null
                const c = dir ? getDirectionColor(dir.id) : '#6f695f'
                const pct = (b.seconds / totalBalance) * 100
                return (
                  <div key={String(b.direction_id)} className="flex items-center gap-3">
                    <span className="w-28 text-[12px] truncate shrink-0" style={{ color: dir ? c : '#9c958a' }}>{dir?.name ?? 'Без направления'}</span>
                    <div className="flex-1 h-[18px] bg-bg-sunken rounded-md overflow-hidden">
                      <div className="h-full rounded-md transition-all duration-700 flex items-center" style={{ width: `${Math.max(2, pct)}%`, backgroundColor: c + 'cc' }} />
                    </div>
                    <span className="w-20 text-right text-[11px] text-text-secondary tabular-nums shrink-0">{fmt(b.seconds)} · {Math.round(pct)}%</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Доп. инсайты */}
        {flow && flow.sessions > 0 && (
          <div className="text-[12px] text-text-muted leading-relaxed px-1 pb-6">
            За 90 дней — {flow.sessions} сессий, самая длинная {fmt(flow.longest_seconds)}, в среднем {fmt(flow.avg_seconds)}.
            Лучшие часы: {flow.best_hours.map(h => `${h.hour}:00`).join(', ')} — планируй сложное туда.
          </div>
        )}
      </div>
    </div>
  )
}
