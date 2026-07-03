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
    task_title: string | null
    note: string | null
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

type Session = DashboardData['sessions'][number]

function fmtTime(iso: string) {
  return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function TimelineBlock({
  sessions,
  colorMap,
}: {
  sessions: DashboardData['sessions']
  colorMap: Map<number | null, string>
}) {
  const [selected, setSelected] = useState<Session | null>(null)
  const weekDays = getWeekDays()
  const sessionsByDay = new Map<string, typeof sessions>()
  for (const s of sessions) {
    const day = s.started_at.slice(0, 10)
    if (!sessionsByDay.has(day)) sessionsByDay.set(day, [])
    sessionsByDay.get(day)!.push(s)
  }
  const activeDays = weekDays.filter(day => sessionsByDay.has(day))
  if (activeDays.length === 0) return null
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
              <span key={h} className="absolute text-[9px] text-[#383838] -translate-x-1/2" style={{ left: `${pct}%` }}>
                {h === 24 ? '00' : `${h}`}
              </span>
            )
          })}
        </div>
      </div>

      <div className="space-y-1">
        {activeDays.map(day => {
          const daySessions = sessionsByDay.get(day)!
          const isToday = day === new Date().toISOString().slice(0, 10)
          return (
            <div key={day} className="flex items-center gap-2">
              <span className={`text-[10px] w-10 shrink-0 text-right ${isToday ? 'text-[#8090c8]' : 'text-[#383838]'}`}>
                {getDayLabel(day)}
              </span>
              <div className="flex-1 relative h-5 bg-[#141414] rounded overflow-hidden">
                {hourTicks.slice(1, -1).map(h => (
                  <div key={h} className="absolute top-0 bottom-0 w-px bg-[#252525]"
                    style={{ left: `${((h * 60 - TIMELINE_START) / TIMELINE_SPAN) * 100}%` }} />
                ))}
                {daySessions.map(s => {
                  const left = Math.max(0, ((minutesFromMidnight(s.started_at) - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const right = Math.min(100, ((minutesFromMidnight(s.ended_at) - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const width = Math.max(0.5, right - left)
                  const color = colorMap.get(s.direction_id) ?? '#5060a0'
                  const isSelected = selected?.id === s.id
                  return (
                    <div
                      key={s.id}
                      onClick={e => { e.stopPropagation(); setSelected(isSelected ? null : s) }}
                      className="absolute top-0.5 bottom-0.5 rounded-sm cursor-pointer transition-all duration-150"
                      style={{
                        left: `${left}%`, width: `${width}%`,
                        backgroundColor: color,
                        opacity: selected && !isSelected ? 0.35 : 0.9,
                        outline: isSelected ? `2px solid ${color}` : 'none',
                        outlineOffset: '1px',
                      }}
                    />
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {/* Session detail card */}
      {selected && (
        <div
          className="mt-3 bg-[#141414] border border-[#5060a0]/40 rounded-xl px-4 py-3 animate-fade-in"
          style={{ animation: 'fadeSlideIn 0.18s ease-out' }}
        >
          <div className="flex items-start justify-between gap-2 mb-1">
            <span className="text-sm text-[#e0e0e0] font-medium leading-snug flex-1">
              {selected.task_title ?? '—'}
            </span>
            <button onClick={() => setSelected(null)} className="text-[#555] hover:text-[#999] text-xs shrink-0">✕</button>
          </div>
          <div className="flex items-center gap-3 text-[11px] text-[#555]">
            <span style={{ color: colorMap.get(selected.direction_id) ?? '#5060a0' }}>{selected.direction_name}</span>
            <span>{fmtTime(selected.started_at)} → {fmtTime(selected.ended_at)}</span>
            <span className="font-mono">{fmtDuration(selected.duration_actual)}</span>
          </div>
          {selected.note && (
            <p className="mt-1.5 text-xs text-[#888] italic leading-snug">{selected.note}</p>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Block 3a: Donut ─────────────────────────────────────────────────────────

function DonutChart({
  data,
  colorMap,
  sessions,
}: {
  data: DashboardData['time_by_direction']
  colorMap: Map<number | null, string>
  sessions: DashboardData['sessions']
}) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null)

  const total = data.reduce((s, d) => s + d.total_seconds, 0)
  if (total === 0) {
    return <div className="flex items-center justify-center h-32 text-[#383838] text-sm">Нет данных</div>
  }

  const R = 62, cx = 80, cy = 80, strokeW = 24, POP = 10

  let cumAngle = -Math.PI / 2
  const arcs = data.map((d, i) => {
    const frac = d.total_seconds / total
    const angle = frac * 2 * Math.PI
    const startA = cumAngle
    const x1 = cx + R * Math.cos(startA)
    const y1 = cy + R * Math.sin(startA)
    cumAngle += angle
    const midA = startA + angle / 2
    const x2 = cx + R * Math.cos(cumAngle)
    const y2 = cy + R * Math.sin(cumAngle)
    const large = angle > Math.PI ? 1 : 0
    const color = colorMap.get(d.direction_id) ?? '#5060a0'
    const dx = POP * Math.cos(midA)
    const dy = POP * Math.sin(midA)
    return { x1, y1, x2, y2, large, color, angle, midA, dx, dy, idx: i }
  })

  // Tasks for selected direction
  const selData = selectedIdx !== null ? data[selectedIdx] : null
  const selColor = selData ? (colorMap.get(selData.direction_id) ?? '#5060a0') : null
  const dirTasks = selData
    ? (() => {
        const map = new Map<string, number>()
        sessions
          .filter(s => s.direction_id === selData.direction_id)
          .forEach(s => {
            const k = s.task_title ?? '—'
            map.set(k, (map.get(k) ?? 0) + s.duration_actual)
          })
        return [...map.entries()].sort((a, b) => b[1] - a[1])
      })()
    : null

  return (
    <div className="flex gap-4 items-start">
      <svg
        width={160} height={160}
        className="shrink-0 cursor-pointer"
        onClick={() => setSelectedIdx(null)}
      >
        {arcs.map((arc, i) => {
          if (arc.angle < 0.02) return null
          const isSelected = selectedIdx === i
          const isDimmed = selectedIdx !== null && !isSelected
          const path = `M ${arc.x1} ${arc.y1} A ${R} ${R} 0 ${arc.large} 1 ${arc.x2} ${arc.y2}`
          return (
            <g
              key={i}
              style={{
                transform: isSelected ? `translate(${arc.dx}px, ${arc.dy}px)` : 'translate(0,0)',
                transition: 'transform 0.35s cubic-bezier(0.34,1.56,0.64,1)',
                opacity: isDimmed ? 0.25 : 1,
              }}
              onClick={e => { e.stopPropagation(); setSelectedIdx(isSelected ? null : i) }}
            >
              <path
                d={path}
                fill="none"
                stroke={arc.color}
                strokeWidth={isSelected ? strokeW + 4 : strokeW}
                strokeLinecap="butt"
                style={{ transition: 'stroke-width 0.25s ease, opacity 0.25s ease' }}
              />
            </g>
          )
        })}
        <circle cx={cx} cy={cy} r={R - strokeW / 2 - 2} fill="#1c1c1c" style={{ pointerEvents: 'none' }} />
        {selData ? (
          <>
            <text x={cx} y={cy - 8} textAnchor="middle" fill={selColor!} fontSize={9} fontWeight="600">
              {selData.direction_name.length > 12 ? selData.direction_name.slice(0, 11) + '…' : selData.direction_name}
            </text>
            <text x={cx} y={cy + 7} textAnchor="middle" fill="#f0f0f0" fontSize={13} fontWeight="bold">
              {fmtDuration(selData.total_seconds)}
            </text>
            <text x={cx} y={cy + 19} textAnchor="middle" fill="#555" fontSize={9}>
              {Math.round((selData.total_seconds / total) * 100)}%
            </text>
          </>
        ) : (
          <>
            <text x={cx} y={cy - 5} textAnchor="middle" fill="#f0f0f0" fontSize={12} fontWeight="bold">{fmtDuration(total)}</text>
            <text x={cx} y={cy + 11} textAnchor="middle" fill="#555" fontSize={9}>всего</text>
          </>
        )}
      </svg>

      <div className="flex flex-col gap-1.5 min-w-0 flex-1 overflow-hidden">
        {dirTasks ? (
          <>
            <div className="text-[9px] font-semibold tracking-widest uppercase mb-0.5" style={{ color: selColor! }}>
              {selData!.direction_name}
            </div>
            {dirTasks.slice(0, 7).map(([title, secs], i) => (
              <div key={i} className="flex items-start gap-1.5 animate-fade-in" style={{ animation: `fadeSlideIn 0.15s ease-out ${i * 0.04}s both` }}>
                <span className="text-[#383838] text-[10px] shrink-0 mt-0.5">·</span>
                <span className="text-xs text-[#c0c0c0] flex-1 leading-snug">{title}</span>
                <span className="text-[11px] font-mono text-[#555] shrink-0">{fmtDuration(secs)}</span>
              </div>
            ))}
          </>
        ) : (
          data.slice(0, 6).map((d, i) => (
            <button
              key={i}
              onClick={() => setSelectedIdx(i)}
              className="flex items-center gap-2 hover:opacity-80 transition-opacity text-left w-full"
            >
              <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: colorMap.get(d.direction_id) ?? '#5060a0' }} />
              <span className="text-xs text-[#666] flex-1 truncate">{d.direction_name}</span>
              <span className="text-xs font-mono text-[#f0f0f0] shrink-0">{fmtDuration(d.total_seconds)}</span>
            </button>
          ))
        )}
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

const DAY_NAMES = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']

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
  const BAR_H = 96

  return (
    <div ref={containerRef} className="relative">
      {/* Y-axis label */}
      <div className="absolute -left-1 top-0 flex flex-col justify-between" style={{ height: BAR_H }}>
        <span className="text-[8px] text-[#383838]">{fmtDuration(maxTotal)}</span>
        <span className="text-[8px] text-[#383838]">0</span>
      </div>

      {/* Bars */}
      <div className="flex items-end gap-[3px] ml-6" style={{ height: BAR_H }}>
        {days.map((day, idx) => {
          const rows = byDay.get(day) ?? []
          const total = dayTotals[idx]
          const segH = total > 0 ? Math.max(3, (total / maxTotal) * (BAR_H - 2)) : 0
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

      {/* X-axis labels */}
      <div className="flex gap-[3px] mt-1 ml-6">
        {days.map((day, idx) => {
          const d = new Date(day + 'T12:00:00')
          let label: string
          if (period === 'week') {
            label = DAY_NAMES[d.getDay()]
          } else {
            const show = period === 'month' ? idx % 5 === 0 : idx % 7 === 0
            label = show ? String(d.getDate()) : ''
          }
          return (
            <div key={day} className="flex-1 min-w-0 text-center">
              {label && <span className="text-[8px] text-[#383838]">{label}</span>}
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
            left: Math.min(tooltip.x + 24, 160),
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

// ─── Мотивационный блок (рекорды, динамика, вклад за всё время) ───────────────

interface Motivation {
  lifetime_seconds: number; tasks_done: number; subtasks_done: number
  this_week_seconds: number; last_week_seconds: number; trend_pct: number
  best_day: { day: string; seconds: number } | null; best_week_seconds: number
  active_days: number; avg_per_active_day: number
}

function MotivationHero({ m }: { m: Motivation }) {
  const up = m.trend_pct >= 0
  const bestDayStr = m.best_day ? new Date(m.best_day.day + 'T12:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : '—'
  return (
    <div className="space-y-3">
      {/* Вклад за всё время — крупно */}
      <div className="bg-gradient-to-br from-[#20223a] to-[#1c1c1c] border border-[#2a2d4a] rounded-xl p-5">
        <div className="text-[10px] font-semibold tracking-widest text-[#6a72a0] uppercase mb-1">Всего в фокусе</div>
        <div className="text-4xl font-bold text-[#f0f0f0]">{fmtDuration(m.lifetime_seconds)}</div>
        <div className="text-xs text-[#666] mt-1.5">
          за {m.active_days} {m.active_days % 10 === 1 && m.active_days % 100 !== 11 ? 'активный день' : 'активных дней'} ·
          {' '}{m.tasks_done} задач и {m.subtasks_done} шагов закрыто
        </div>
      </div>

      {/* Динамика недели + рекорды */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Эта неделя</div>
          <div className="text-2xl font-bold text-[#f0f0f0]">{fmtDuration(m.this_week_seconds)}</div>
          <div className={`text-xs mt-1 ${up ? 'text-[#4a9d5f]' : 'text-[#c07a55]'}`}>
            {up ? '▲' : '▼'} {Math.abs(m.trend_pct)}% к прошлой ({fmtDuration(m.last_week_seconds)})
          </div>
        </div>
        <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Рекорд дня</div>
          <div className="text-2xl font-bold text-[#f0f0f0]">{m.best_day ? fmtDuration(m.best_day.seconds) : '—'}</div>
          <div className="text-xs text-[#666] mt-1">{bestDayStr}</div>
        </div>
        <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">В среднем в день</div>
          <div className="text-2xl font-bold text-[#f0f0f0]">{fmtDuration(m.avg_per_active_day)}</div>
          <div className="text-xs text-[#666] mt-1">рекорд недели {fmtDuration(m.best_week_seconds)}</div>
        </div>
      </div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function StatsScreen({ onClose }: Props) {
  const [period, setPeriod] = useState<Period>('week')
  const [data, setData] = useState<DashboardData | null>(null)
  const [motivation, setMotivation] = useState<Motivation | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getStatsDashboard(period).then(d => {
      setData(d as DashboardData)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [period])

  useEffect(() => { api.getMotivation().then(setMotivation).catch(() => {}) }, [])

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

        {motivation && <MotivationHero m={motivation} />}

        {!loading && data && (
          <>
            <MetricsBlock data={data} />
            <TimelineBlock sessions={data.sessions} colorMap={colorMap} />

            <div className="grid grid-cols-2 gap-4">
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">По направлениям</div>
                <DonutChart data={data.time_by_direction} colorMap={colorMap} sessions={data.sessions} />
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

            {/* Export */}
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
              <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Экспорт</div>
              <div className="flex gap-2">
                <a
                  href={`/api/export/sessions.csv?period=${period}`}
                  download
                  className="flex-1 text-center py-2 bg-[#252525] hover:bg-[#383838] rounded-lg text-xs text-[#999] transition-colors"
                >
                  ↓ Сессии (.csv)
                </a>
                <a
                  href="/api/export/tasks.csv"
                  download
                  className="flex-1 text-center py-2 bg-[#252525] hover:bg-[#383838] rounded-lg text-xs text-[#999] transition-colors"
                >
                  ↓ Задачи (.csv)
                </a>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
