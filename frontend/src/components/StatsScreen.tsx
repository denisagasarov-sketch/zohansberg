import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

interface Props {
  onClose: () => void
}

type Period = 'week' | 'month' | 'all'

interface DashboardData {
  total_seconds: number
  tasks_done_count: number
  top_direction: { direction_name: string; total_seconds: number } | null
  sessions: Array<{
    id: number
    started_at: string
    ended_at: string
    duration_actual: number
    direction_id: number | null
    direction_name: string
  }>
  time_by_direction: Array<{
    direction_id: number | null
    direction_name: string
    total_seconds: number
  }>
  time_by_day_direction: Array<{
    day: string
    direction_id: number | null
    direction_name: string
    total_seconds: number
  }>
  directions: Array<{ id: number; name: string }>
}

const PALETTE = [
  '#5060a0', '#a05060', '#50a070', '#a07050',
  '#5090a0', '#8050a0', '#a09050', '#50a0a0',
]

function buildColorMap(directions: Array<{ id: number }>): Map<number | null, string> {
  const map = new Map<number | null, string>()
  map.set(null, '#383838')
  directions.forEach((d, i) => {
    map.set(d.id, PALETTE[i % PALETTE.length])
  })
  return map
}

function fmtDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0 && m > 0) return `${h}ч ${m}м`
  if (h > 0) return `${h}ч`
  if (m > 0) return `${m}м`
  return `${Math.round(seconds)}с`
}

function minutesFromMidnight(isoStr: string): number {
  const d = new Date(isoStr)
  return d.getHours() * 60 + d.getMinutes()
}

// ─── Block 1 ──────────────────────────────────────────────────────────────────

function MetricsBlock({ data }: { data: DashboardData }) {
  return (
    <div className="grid grid-cols-3 gap-3">
      <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
        <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Время в работе</div>
        <div className="text-2xl font-bold text-[#f0f0f0]">{fmtDuration(data.total_seconds)}</div>
      </div>
      <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
        <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Задач завершено</div>
        <div className="text-2xl font-bold text-[#f0f0f0]">{data.tasks_done_count}</div>
      </div>
      <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
        <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Топ направление</div>
        {data.top_direction ? (
          <>
            <div className="text-sm font-semibold text-[#f0f0f0] truncate">{data.top_direction.direction_name}</div>
            <div className="text-xs text-[#666] mt-1">{fmtDuration(data.top_direction.total_seconds)}</div>
          </>
        ) : (
          <div className="text-sm text-[#383838]">—</div>
        )}
      </div>
    </div>
  )
}

// ─── Block 2 ──────────────────────────────────────────────────────────────────

const TIMELINE_START = 6 * 60
const TIMELINE_END = 24 * 60
const TIMELINE_SPAN = TIMELINE_END - TIMELINE_START

function getWeekDays(): string[] {
  const days: string[] = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }
  return days
}

function getDayLabel(iso: string): string {
  const d = new Date(iso + 'T12:00:00')
  const names = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
  return `${names[d.getDay()]} ${d.getDate()}`
}

function TimelineBlock({
  sessions,
  colorMap,
}: {
  sessions: DashboardData['sessions']
  colorMap: Map<number | null, string>
}) {
  const weekDays = getWeekDays()
  const sessionsByDay = new Map<string, typeof sessions>()
  for (const s of sessions) {
    const day = s.started_at.slice(0, 10)
    if (!sessionsByDay.has(day)) sessionsByDay.set(day, [])
    sessionsByDay.get(day)!.push(s)
  }

  const hourTicks = [6, 9, 12, 15, 18, 21, 24]

  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Временна́я шкала недели</div>

      <div className="flex mb-1 ml-12">
        <div className="flex-1 relative h-3">
          {hourTicks.map(h => {
            const pct = ((h * 60 - TIMELINE_START) / TIMELINE_SPAN) * 100
            if (pct < 0 || pct > 100) return null
            return (
              <span
                key={h}
                className="absolute text-[9px] text-[#383838] -translate-x-1/2"
                style={{ left: `${pct}%` }}
              >
                {h === 24 ? '00' : `${h}`}
              </span>
            )
          })}
        </div>
      </div>

      <div className="space-y-1">
        {weekDays.map(day => {
          const daySessions = sessionsByDay.get(day) ?? []
          const isToday = day === new Date().toISOString().slice(0, 10)
          return (
            <div key={day} className="flex items-center gap-2">
              <span className={`text-[10px] w-10 shrink-0 text-right ${isToday ? 'text-[#8090c8]' : 'text-[#383838]'}`}>
                {getDayLabel(day)}
              </span>
              <div className="flex-1 relative h-5 bg-[#141414] rounded overflow-hidden">
                {hourTicks.slice(1, -1).map(h => {
                  const pct = ((h * 60 - TIMELINE_START) / TIMELINE_SPAN) * 100
                  return (
                    <div
                      key={h}
                      className="absolute top-0 bottom-0 w-px bg-[#252525]"
                      style={{ left: `${pct}%` }}
                    />
                  )
                })}
                {daySessions.map(s => {
                  const startMin = minutesFromMidnight(s.started_at)
                  const endMin = minutesFromMidnight(s.ended_at)
                  const left = Math.max(0, ((startMin - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const right = Math.min(100, ((endMin - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const width = Math.max(0.5, right - left)
                  const color = colorMap.get(s.direction_id) ?? '#5060a0'
                  return (
                    <div
                      key={s.id}
                      title={`${s.direction_name}: ${fmtDuration(s.duration_actual)}`}
                      className="absolute top-0.5 bottom-0.5 rounded-sm opacity-90"
                      style={{ left: `${left}%`, width: `${width}%`, backgroundColor: color }}
                    />
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Block 3a: Donut ─────────────────────────────────────────────────────────

function DonutChart({
  data,
  colorMap,
}: {
  data: DashboardData['time_by_direction']
  colorMap: Map<number | null, string>
}) {
  const total = data.reduce((s, d) => s + d.total_seconds, 0)
  if (total === 0) {
    return <div className="flex items-center justify-center h-32 text-[#383838] text-sm">Нет данных</div>
  }

  const R = 48
  const cx = 62
  const cy = 62
  const strokeW = 16

  let cumAngle = -Math.PI / 2
  const arcs = data.map(d => {
    const frac = d.total_seconds / total
    const angle = frac * 2 * Math.PI
    const x1 = cx + R * Math.cos(cumAngle)
    const y1 = cy + R * Math.sin(cumAngle)
    cumAngle += angle
    const x2 = cx + R * Math.cos(cumAngle)
    const y2 = cy + R * Math.sin(cumAngle)
    const large = angle > Math.PI ? 1 : 0
    const color = colorMap.get(d.direction_id) ?? '#5060a0'
    return { x1, y1, x2, y2, large, color, angle }
  })

  return (
    <div className="flex gap-4 items-start">
      <svg width={124} height={124} className="shrink-0">
        {arcs.map((arc, i) => {
          if (arc.angle < 0.02) return null
          const path = `M ${arc.x1} ${arc.y1} A ${R} ${R} 0 ${arc.large} 1 ${arc.x2} ${arc.y2}`
          return (
            <path
              key={i}
              d={path}
              fill="none"
              stroke={arc.color}
              strokeWidth={strokeW}
              strokeLinecap="butt"
            />
          )
        })}
        <circle cx={cx} cy={cy} r={R - strokeW / 2 - 1} fill="#1c1c1c" />
        <text x={cx} y={cy - 4} textAnchor="middle" fill="#f0f0f0" fontSize={10} fontWeight="bold">
          {fmtDuration(total)}
        </text>
        <text x={cx} y={cy + 9} textAnchor="middle" fill="#555" fontSize={8}>всего</text>
      </svg>

      <div className="flex flex-col gap-1.5 min-w-0 flex-1">
        {data.slice(0, 6).map((d, i) => (
          <div key={i} className="flex items-center gap-2">
            <div
              className="w-2.5 h-2.5 rounded-sm shrink-0"
              style={{ backgroundColor: colorMap.get(d.direction_id) ?? '#5060a0' }}
            />
            <span className="text-xs text-[#666] flex-1 truncate">{d.direction_name}</span>
            <span className="text-xs font-mono text-[#f0f0f0] shrink-0">{fmtDuration(d.total_seconds)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Block 3b: Bar chart ──────────────────────────────────────────────────────

interface TooltipState {
  x: number
  y: number
  day: string
  total: number
  items: Array<{ name: string; seconds: number; color: string }>
}

function BarChart({
  data,
  period,
  colorMap,
}: {
  data: DashboardData['time_by_day_direction']
  period: Period
  colorMap: Map<number | null, string>
}) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const dayCount = period === 'week' ? 7 : period === 'month' ? 30 : 60
  const days: string[] = []
  for (let i = dayCount - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(d.toISOString().slice(0, 10))
  }

  const byDay = new Map<string, Array<{ direction_id: number | null; direction_name: string; total_seconds: number }>>()
  for (const row of data) {
    if (!byDay.has(row.day)) byDay.set(row.day, [])
    byDay.get(row.day)!.push(row)
  }

  const dayTotals = days.map(d => (byDay.get(d) ?? []).reduce((s, r) => s + r.total_seconds, 0))
  const maxTotal = Math.max(...dayTotals, 1)
  const barH = 88

  return (
    <div ref={containerRef} className="relative">
      <div className="flex items-end gap-[2px]" style={{ height: barH }}>
        {days.map((day, idx) => {
          const rows = byDay.get(day) ?? []
          const total = dayTotals[idx]
          const segH = total > 0 ? Math.max(3, (total / maxTotal) * (barH - 4)) : 0
          const items = rows.map(r => ({
            name: r.direction_name,
            seconds: r.total_seconds,
            color: colorMap.get(r.direction_id) ?? '#5060a0',
          }))

          return (
            <div
              key={day}
              className="flex-1 flex flex-col justify-end cursor-default min-w-0"
              style={{ height: '100%' }}
              onMouseEnter={e => {
                if (total === 0) return
                const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
                const containerRect = containerRef.current!.getBoundingClientRect()
                setTooltip({
                  x: rect.left - containerRect.left,
                  y: rect.top - containerRect.top,
                  day,
                  total,
                  items,
                })
              }}
              onMouseLeave={() => setTooltip(null)}
            >
              {segH > 0 && (
                <div
                  className="w-full rounded-t-sm overflow-hidden"
                  style={{ height: segH, display: 'flex', flexDirection: 'column-reverse' }}
                >
                  {items.map((item, i) => {
                    const h = (item.seconds / total) * segH
                    return (
                      <div key={i} style={{ height: h, backgroundColor: item.color, flexShrink: 0 }} />
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Labels */}
      <div className="flex gap-[2px] mt-1">
        {days.map((day, idx) => {
          const showL = period === 'week' ? true : period === 'month' ? idx % 5 === 0 : idx % 7 === 0
          const d = new Date(day + 'T12:00:00')
          return (
            <div key={day} className="flex-1 min-w-0 text-center">
              {showL && <span className="text-[8px] text-[#383838]">{d.getDate()}</span>}
            </div>
          )
        })}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute bg-[#141414] border border-[#333] rounded p-2.5 text-xs shadow-lg pointer-events-none z-20"
          style={{
            top: Math.max(0, tooltip.y - 120),
            left: Math.min(tooltip.x, 160),
            minWidth: 140,
          }}
        >
          <div className="text-[#666] mb-1">
            {new Date(tooltip.day + 'T12:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
          </div>
          <div className="font-semibold text-[#f0f0f0] mb-1.5">{fmtDuration(tooltip.total)}</div>
          <div className="space-y-1">
            {tooltip.items.map((item, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-[#666] truncate flex-1">{item.name}</span>
                <span className="text-[#f0f0f0] font-mono shrink-0">{fmtDuration(item.seconds)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function StatsScreen({ onClose }: Props) {
  const [period, setPeriod] = useState<Period>('week')
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getStatsDashboard(period).then(d => {
      setData(d as DashboardData)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [period])

  const colorMap = data ? buildColorMap(data.directions) : new Map()

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold flex-1">Статистика</h1>
        <div className="flex gap-1">
          {(['week', 'month', 'all'] as Period[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs transition-colors border ${period === p ? 'bg-[#5060a0] border-[#5060a0] text-white' : 'border-[#252525] text-[#666] hover:border-[#5060a0]/50'}`}
            >
              {p === 'week' ? 'Неделя' : p === 'month' ? 'Месяц' : 'Всё время'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {loading && <div className="text-[#666] text-sm">Загрузка…</div>}

        {!loading && !data && (
          <div className="text-[#666] text-sm">Не удалось загрузить данные</div>
        )}

        {!loading && data && (
          <>
            <MetricsBlock data={data} />
            <TimelineBlock sessions={data.sessions} colorMap={colorMap} />

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">По направлениям</div>
                <DonutChart data={data.time_by_direction} colorMap={colorMap} />
              </div>

              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">По дням</div>
                {data.time_by_day_direction.length === 0 ? (
                  <div className="flex items-center justify-center h-24 text-[#383838] text-sm">Нет данных</div>
                ) : (
                  <BarChart data={data.time_by_day_direction} period={period} colorMap={colorMap} />
                )}
                {data.time_by_direction.length > 0 && (
                  <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3">
                    {data.time_by_direction.slice(0, 6).map((d, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: colorMap.get(d.direction_id) ?? '#5060a0' }} />
                        <span className="text-[10px] text-[#383838]">{d.direction_name}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
