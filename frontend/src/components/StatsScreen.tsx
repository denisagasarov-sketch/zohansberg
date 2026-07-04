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
  today_seconds: number; same_day_last_week_seconds: number; day_trend_pct: number
  best_day: { day: string; seconds: number } | null; best_week_seconds: number
  active_days: number; avg_per_active_day: number
}

function CompareCard({ label, value, pct, prevLabel, prevValue }: {
  label: string; value: number; pct: number; prevLabel: string; prevValue: number
}) {
  const up = pct >= 0
  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-xl p-5">
      <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">{label}</div>
      <div className="text-3xl font-bold text-[#f0f0f0]">{fmtDuration(value)}</div>
      <div className={`text-sm mt-2 ${up ? 'text-[#4a9d5f]' : 'text-[#c07a55]'}`}>
        {up ? '▲' : '▼'} {Math.abs(pct)}%
        <span className="text-[#666]"> к {prevLabel} ({fmtDuration(prevValue)})</span>
      </div>
    </div>
  )
}

function MotivationHero({ m }: { m: Motivation }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <CompareCard label="Эта неделя" value={m.this_week_seconds} pct={m.trend_pct}
        prevLabel="прошлой неделе" prevValue={m.last_week_seconds} />
      <CompareCard label="Сегодня" value={m.today_seconds} pct={m.day_trend_pct}
        prevLabel="этому дню неделю назад" prevValue={m.same_day_last_week_seconds} />
    </div>
  )
}

// Круг-неделя: 7 секторов (дни), длина сектора = часы за день, цвета = направления
function WeekWheel({ data, colorMap, directions }: {
  data: DashboardData['time_by_day_direction']
  colorMap: Map<number | null, string>
  directions: { id: number; name: string }[]
}) {
  // Последние 7 дней (Пн..Вс порядок от сегодня назад)
  const days: string[] = []
  for (let i = 6; i >= 0; i--) { const d = new Date(); d.setDate(d.getDate() - i); days.push(d.toISOString().slice(0, 10)) }
  const names = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
  const byDay = new Map<string, { dir: number | null; s: number }[]>()
  data.forEach(r => {
    if (!byDay.has(r.day)) byDay.set(r.day, [])
    byDay.get(r.day)!.push({ dir: r.direction_id, s: r.total_seconds })
  })
  const dayTotal = (d: string) => (byDay.get(d) ?? []).reduce((a, b) => a + b.s, 0)
  const maxTotal = Math.max(1, ...days.map(dayTotal))

  const cx = 130, cy = 130, rInner = 34, rMax = 120
  const seg = (2 * Math.PI) / 7
  const gap = 0.06
  const arcs: JSX.Element[] = []
  const labels: JSX.Element[] = []

  days.forEach((d, i) => {
    const a0 = -Math.PI / 2 + i * seg + gap
    const a1 = -Math.PI / 2 + (i + 1) * seg - gap
    const total = dayTotal(d)
    const rOuter = rInner + (rMax - rInner) * (total / maxTotal)
    // стек по направлениям от центра наружу
    const parts = (byDay.get(d) ?? []).slice().sort((a, b) => b.s - a.s)
    let rCur = rInner
    parts.forEach((p, j) => {
      const frac = total > 0 ? p.s / total : 0
      const rNext = rCur + (rOuter - rInner) * frac
      arcs.push(<path key={`${i}-${j}`} d={annular(cx, cy, rCur, rNext, a0, a1)} fill={colorMap.get(p.dir) ?? '#5060a0'} />)
      rCur = rNext
    })
    // фон-дуга пустого дня
    if (total === 0) arcs.push(<path key={`${i}-e`} d={annular(cx, cy, rInner, rInner + 3, a0, a1)} fill="#252525" />)
    const am = (a0 + a1) / 2
    const lr = rMax + 12
    labels.push(<text key={`l${i}`} x={cx + lr * Math.cos(am)} y={cy + lr * Math.sin(am)} textAnchor="middle" dominantBaseline="middle" fontSize="11" fill={d === days[6] ? '#8090c8' : '#666'}>{names[new Date(d + 'T12:00:00').getDay()]}</text>)
  })

  return (
    <div className="flex items-center gap-5 flex-wrap">
      <svg width="260" height="260" viewBox="0 0 260 260" className="shrink-0">{arcs}{labels}</svg>
      <div className="space-y-1.5 min-w-[140px]">
        {directions.filter(d => data.some(r => r.direction_id === d.id)).map(d => {
          const total = data.filter(r => r.direction_id === d.id).reduce((a, b) => a + b.total_seconds, 0)
          return (
            <div key={d.id} className="flex items-center gap-2 text-xs">
              <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: colorMap.get(d.id) ?? '#5060a0' }} />
              <span className="text-[#ccc] flex-1">{d.name}</span>
              <span className="text-[#666]">{fmtDuration(total)}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// SVG-путь кольцевого сектора (annular sector)
function annular(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const p = (r: number, a: number) => `${cx + r * Math.cos(a)} ${cy + r * Math.sin(a)}`
  const large = a1 - a0 > Math.PI ? 1 : 0
  return `M ${p(r0, a0)} L ${p(r1, a0)} A ${r1} ${r1} 0 ${large} 1 ${p(r1, a1)} L ${p(r0, a1)} A ${r0} ${r0} 0 ${large} 0 ${p(r0, a0)} Z`
}

// ─── Когда я продуктивен (части суток) ────────────────────────────────────────
const DAY_PARTS = [
  { key: 'morning', label: 'Утро', sub: '6–12', from: 6, to: 12 },
  { key: 'day', label: 'День', sub: '12–18', from: 12, to: 18 },
  { key: 'evening', label: 'Вечер', sub: '18–24', from: 18, to: 24 },
  { key: 'night', label: 'Ночь', sub: '0–6', from: 0, to: 6 },
]
function ByPartOfDay({ data }: { data: { hour: number; seconds: number }[] }) {
  const parts = DAY_PARTS.map(p => ({
    ...p, seconds: data.filter(d => d.hour >= p.from && d.hour < p.to).reduce((a, b) => a + b.seconds, 0),
  }))
  const total = parts.reduce((a, b) => a + b.seconds, 0)
  const max = Math.max(1, ...parts.map(p => p.seconds))
  const best = parts.reduce((a, b) => (b.seconds > a.seconds ? b : a), parts[0])
  if (total === 0) return <div className="text-xs text-[#666]">Пока нет данных о времени работы.</div>
  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        {parts.map(p => (
          <div key={p.key} className="text-center">
            <div className="h-24 flex items-end justify-center mb-2">
              <div className="w-8 rounded-t-md transition-all" style={{ height: `${Math.max(4, (p.seconds / max) * 100)}%`, backgroundColor: p.key === best.key ? '#5060a0' : '#33384d' }} />
            </div>
            <div className="text-sm text-[#f0f0f0]">{fmtDuration(p.seconds)}</div>
            <div className="text-[11px] text-[#888]">{p.label}</div>
            <div className="text-[10px] text-[#555]">{p.sub}</div>
          </div>
        ))}
      </div>
      <div className="text-xs text-[#8090c8] mt-3">Продуктивнее всего — {best.label.toLowerCase()} ({best.sub}). Ставь сложное на это время.</div>
    </div>
  )
}

// ─── Календарь постоянства (тепловая карта года) ──────────────────────────────
function heatColor(seconds: number): string {
  if (!seconds) return '#1e1e1e'
  const h = seconds / 3600
  if (h < 1) return '#1d3a24'
  if (h < 2.5) return '#2e6b3f'
  if (h < 4.5) return '#3f9d57'
  return '#5ed17a'
}
function ConsistencyHeatmap({ data }: { data: { day: string; seconds: number }[] }) {
  const map = new Map(data.map(d => [d.day, d.seconds]))
  const cells: { date: string; seconds: number }[] = []
  const today = new Date()
  const start = new Date(today); start.setDate(start.getDate() - 364)
  start.setDate(start.getDate() - start.getDay())
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
            <div key={c.date} title={`${c.date}: ${fmtDuration(c.seconds)}`}
              className="w-[9px] h-[9px] rounded-[2px]" style={{ backgroundColor: heatColor(c.seconds) }} />
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function StatsScreen({ onClose }: Props) {
  const [period, setPeriod] = useState<Period>('week')
  const [data, setData] = useState<DashboardData | null>(null)
  const [motivation, setMotivation] = useState<Motivation | null>(null)
  const [byHour, setByHour] = useState<{ hour: number; seconds: number }[]>([])
  const [heatmap, setHeatmap] = useState<{ day: string; seconds: number }[]>([])
  const [consistency, setConsistency] = useState<{ streak: number; best: number; active: number } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getStatsDashboard(period).then(d => {
      setData(d as DashboardData)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [period])

  useEffect(() => {
    api.getMotivation().then(setMotivation).catch(() => {})
    api.getByHour().then(setByHour).catch(() => {})
    api.getGamification().then(g => { setHeatmap(g.heatmap); setConsistency({ streak: g.streak, best: g.best_streak, active: g.active_days_total }) }).catch(() => {})
  }, [])

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
            {/* Круг недели: дни × направления */}
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
              <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">Неделя по направлениям</div>
              {data.time_by_day_direction.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-[#383838] text-sm">Нет данных за период</div>
              ) : (
                <WeekWheel data={data.time_by_day_direction} colorMap={colorMap} directions={data.directions} />
              )}
            </div>

            {/* Когда я продуктивен */}
            {byHour.some(h => h.seconds > 0) && (
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">Когда я продуктивен</div>
                <ByPartOfDay data={byHour} />
              </div>
            )}

            {/* Календарь постоянства */}
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase">Календарь постоянства</div>
                {consistency && (
                  <div className="text-[10px] text-[#666]">
                    серия {consistency.streak} · рекорд {consistency.best} · {consistency.active} активных дней
                  </div>
                )}
              </div>
              <ConsistencyHeatmap data={heatmap} />
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
