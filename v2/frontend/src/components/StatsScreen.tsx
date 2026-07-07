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
  '#e0a458', '#a05060', '#50a070', '#a07050',
  '#5090a0', '#8050a0', '#a09050', '#50a0a0',
]

function buildColorMap(directions: Array<{ id: number }>): Map<number | null, string> {
  const map = new Map<number | null, string>()
  map.set(null, '#4a463f')
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
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="section-label mb-3">Временна́я шкала недели</div>

      <div className="flex mb-1 ml-12">
        <div className="flex-1 relative h-3">
          {hourTicks.map(h => {
            const pct = ((h * 60 - TIMELINE_START) / TIMELINE_SPAN) * 100
            if (pct < 0 || pct > 100) return null
            return (
              <span key={h} className="absolute text-[9px] text-[#4a463f] -translate-x-1/2" style={{ left: `${pct}%` }}>
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
              <span className={`text-[10px] w-10 shrink-0 text-right ${isToday ? 'text-[#eab26c]' : 'text-[#4a463f]'}`}>
                {getDayLabel(day)}
              </span>
              <div className="flex-1 relative h-5 bg-[#0f0e0d] rounded overflow-hidden">
                {hourTicks.slice(1, -1).map(h => (
                  <div key={h} className="absolute top-0 bottom-0 w-px bg-[#2a2723]"
                    style={{ left: `${((h * 60 - TIMELINE_START) / TIMELINE_SPAN) * 100}%` }} />
                ))}
                {daySessions.map(s => {
                  const left = Math.max(0, ((minutesFromMidnight(s.started_at) - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const right = Math.min(100, ((minutesFromMidnight(s.ended_at) - TIMELINE_START) / TIMELINE_SPAN) * 100)
                  const width = Math.max(0.5, right - left)
                  const color = colorMap.get(s.direction_id) ?? '#e0a458'
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
          className="mt-3 bg-[#0f0e0d] border border-[#e0a458]/40 rounded-xl px-4 py-3 animate-fade-in"
          style={{ animation: 'fadeSlideIn 0.18s ease-out' }}
        >
          <div className="flex items-start justify-between gap-2 mb-1">
            <span className="text-sm text-[#ddd6cb] font-medium leading-snug flex-1">
              {selected.task_title ?? '—'}
            </span>
            <button onClick={() => setSelected(null)} className="text-[#6f695f] hover:text-[#a49d90] text-xs shrink-0">✕</button>
          </div>
          <div className="flex items-center gap-3 text-[11px] text-[#6f695f]">
            <span style={{ color: colorMap.get(selected.direction_id) ?? '#e0a458' }}>{selected.direction_name}</span>
            <span>{fmtTime(selected.started_at)} → {fmtTime(selected.ended_at)}</span>
            <span className="font-mono">{fmtDuration(selected.duration_actual)}</span>
          </div>
          {selected.note && (
            <p className="mt-1.5 text-xs text-[#8d8679] italic leading-snug">{selected.note}</p>
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
    return <div className="flex items-center justify-center h-32 text-[#4a463f] text-sm">Нет данных</div>
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
    const color = colorMap.get(d.direction_id) ?? '#e0a458'
    const dx = POP * Math.cos(midA)
    const dy = POP * Math.sin(midA)
    return { x1, y1, x2, y2, large, color, angle, midA, dx, dy, idx: i }
  })

  // Tasks for selected direction
  const selData = selectedIdx !== null ? data[selectedIdx] : null
  const selColor = selData ? (colorMap.get(selData.direction_id) ?? '#e0a458') : null
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
        <circle cx={cx} cy={cy} r={R - strokeW / 2 - 2} fill="#1b1a18" style={{ pointerEvents: 'none' }} />
        {selData ? (
          <>
            <text x={cx} y={cy - 8} textAnchor="middle" fill={selColor!} fontSize={9} fontWeight="600">
              {selData.direction_name.length > 12 ? selData.direction_name.slice(0, 11) + '…' : selData.direction_name}
            </text>
            <text x={cx} y={cy + 7} textAnchor="middle" fill="#ece7df" fontSize={13} fontWeight="bold">
              {fmtDuration(selData.total_seconds)}
            </text>
            <text x={cx} y={cy + 19} textAnchor="middle" fill="#6f695f" fontSize={9}>
              {Math.round((selData.total_seconds / total) * 100)}%
            </text>
          </>
        ) : (
          <>
            <text x={cx} y={cy - 5} textAnchor="middle" fill="#ece7df" fontSize={12} fontWeight="bold">{fmtDuration(total)}</text>
            <text x={cx} y={cy + 11} textAnchor="middle" fill="#6f695f" fontSize={9}>всего</text>
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
                <span className="text-[#4a463f] text-[10px] shrink-0 mt-0.5">·</span>
                <span className="text-xs text-[#b5aea1] flex-1 leading-snug">{title}</span>
                <span className="text-[11px] font-mono text-[#6f695f] shrink-0">{fmtDuration(secs)}</span>
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
              <div className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ backgroundColor: colorMap.get(d.direction_id) ?? '#e0a458' }} />
              <span className="text-xs text-[#9c958a] flex-1 truncate">{d.direction_name}</span>
              <span className="text-xs font-mono text-[#ece7df] shrink-0">{fmtDuration(d.total_seconds)}</span>
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
        <span className="text-[8px] text-[#4a463f]">{fmtDuration(maxTotal)}</span>
        <span className="text-[8px] text-[#4a463f]">0</span>
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
            color: colorMap.get(r.direction_id) ?? '#e0a458',
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
              {label && <span className="text-[8px] text-[#4a463f]">{label}</span>}
            </div>
          )
        })}
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute bg-[#0f0e0d] border border-[#38342e] rounded p-2.5 text-xs shadow-lg pointer-events-none z-20"
          style={{
            top: Math.max(0, tooltip.y - 120),
            left: Math.min(tooltip.x + 24, 160),
            minWidth: 140,
          }}
        >
          <div className="text-[#9c958a] mb-1">
            {new Date(tooltip.day + 'T12:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
          </div>
          <div className="font-semibold text-[#ece7df] mb-1.5">{fmtDuration(tooltip.total)}</div>
          <div className="space-y-1">
            {tooltip.items.map((item, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-sm shrink-0" style={{ backgroundColor: item.color }} />
                <span className="text-[#9c958a] truncate flex-1">{item.name}</span>
                <span className="text-[#ece7df] font-mono shrink-0">{fmtDuration(item.seconds)}</span>
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
  yesterday_seconds: number; yday_trend_pct: number
  best_day: { day: string; seconds: number } | null; best_week_seconds: number
  active_days: number; avg_per_active_day: number
}

function TodayCard({ m }: { m: Motivation }) {
  // Переключатель базы сравнения: тот же день недели назад ↔ вчера
  const [base, setBase] = useState<'week' | 'yday'>(() => (localStorage.getItem('today_compare_base') as any) || 'week')
  const setB = (b: 'week' | 'yday') => { setBase(b); localStorage.setItem('today_compare_base', b) }
  const pct = base === 'week' ? m.day_trend_pct : m.yday_trend_pct
  const prevVal = base === 'week' ? m.same_day_last_week_seconds : m.yesterday_seconds
  const prevLabel = base === 'week' ? 'этому дню неделю назад' : 'вчера'
  const up = pct >= 0
  return (
    <div className="bg-[#1b1a18] border border-[#2a2723] rounded-xl p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="section-label">Сегодня</div>
        <div className="flex gap-1">
          {([['week', 'нед. назад'], ['yday', 'вчера']] as const).map(([v, l]) => (
            <button key={v} onClick={() => setB(v)}
              className={`text-[10px] px-2 py-0.5 rounded transition-colors ${base === v ? 'bg-[#e0a458] text-white' : 'text-[#9c958a] hover:text-[#a49d90]'}`}>{l}</button>
          ))}
        </div>
      </div>
      <div className="text-3xl font-bold text-[#ece7df]">{fmtDuration(m.today_seconds)}</div>
      <div className={`text-sm mt-2 ${up ? 'text-[#82a877]' : 'text-[#c07a55]'}`}>
        {up ? '▲' : '▼'} {Math.abs(pct)}%<span className="text-[#9c958a]"> к {prevLabel} ({fmtDuration(prevVal)})</span>
      </div>
    </div>
  )
}

function MotivationHero({ m }: { m: Motivation }) {
  const up = m.trend_pct >= 0
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="bg-[#1b1a18] border border-[#2a2723] rounded-xl p-5">
        <div className="section-label mb-2">Эта неделя</div>
        <div className="text-3xl font-bold text-[#ece7df]">{fmtDuration(m.this_week_seconds)}</div>
        <div className={`text-sm mt-2 ${up ? 'text-[#82a877]' : 'text-[#c07a55]'}`}>
          {up ? '▲' : '▼'} {Math.abs(m.trend_pct)}%<span className="text-[#9c958a]"> к прошлой неделе ({fmtDuration(m.last_week_seconds)})</span>
        </div>
      </div>
      <TodayCard m={m} />
    </div>
  )
}

// Понедельник недели, содержащей дату d
function mondayOf(d: Date): Date {
  const x = new Date(d); const dow = (x.getDay() + 6) % 7 // пн=0
  x.setDate(x.getDate() - dow); x.setHours(0, 0, 0, 0); return x
}
function ymd(d: Date) { return d.toISOString().slice(0, 10) }

const DOW = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']

// Круг недели: 7 секторов, радиус дня = часы (общая шкала), цвета = направления.
// showLabels — крупный круг с подписями дней; иначе чистый мини-круг для выбора.
function WeekWheelSvg({ weekStart, byDay, colorMap, maxTotal, size, showLabels }: {
  weekStart: Date; byDay: Map<string, { dir: number | null; s: number }[]>
  colorMap: Map<number | null, string>; maxTotal: number; size: number; showLabels: boolean
}) {
  const cx = size / 2, cy = size / 2, rInner = size * 0.11, rMax = size * (showLabels ? 0.38 : 0.46)
  const seg = (2 * Math.PI) / 7, gap = 0.05
  const M = showLabels ? 18 : 3
  const todayStr = ymd(new Date())
  const arcs: JSX.Element[] = [], labels: JSX.Element[] = []
  for (let i = 0; i < 7; i++) {
    const day = new Date(weekStart); day.setDate(day.getDate() + i)
    const ds = ymd(day)
    const a0 = -Math.PI / 2 + i * seg + gap, a1 = -Math.PI / 2 + (i + 1) * seg - gap, am = (a0 + a1) / 2
    const parts = (byDay.get(ds) ?? []).slice().sort((a, b) => b.s - a.s)
    const total = parts.reduce((a, b) => a + b.s, 0)
    const rOuter = rInner + (rMax - rInner) * Math.min(1, total / maxTotal)
    if (total === 0) { arcs.push(<path key={`e${i}`} d={annular(cx, cy, rInner, rInner + 2, a0, a1)} fill="#2a2a2a" />) }
    else { let rCur = rInner; parts.forEach((p, j) => { const rNext = rCur + (rOuter - rInner) * (p.s / total); arcs.push(<path key={`${i}-${j}`} d={annular(cx, cy, rCur, rNext, a0, a1)} fill={colorMap.get(p.dir) ?? '#e0a458'} />); rCur = rNext }) }
    if (showLabels) {
      const lr = rMax + 10, isToday = ds === todayStr
      labels.push(<text key={`l${i}`} x={cx + lr * Math.cos(am)} y={cy + lr * Math.sin(am)} textAnchor="middle" dominantBaseline="middle" fontSize="10" fill={isToday ? '#eab26c' : '#7a7367'} fontWeight={isToday ? 600 : 400}>{DOW[i]}</text>)
    }
  }
  return <svg width={size} height={size} viewBox={`${-M} ${-M} ${size + 2 * M} ${size + 2 * M}`} className="shrink-0">{arcs}{labels}</svg>
}

// Крупный круг выбранной недели + список дней с часами, снизу — недели-переключатели.
function WeeksSprints({ rows, directions }: {
  rows: { day: string; direction_id: number | null; seconds: number }[]
  directions: { id: number; name: string }[]
}) {
  const colorMap = buildColorMap(directions)
  const byDay = new Map<string, { dir: number | null; s: number }[]>()
  rows.forEach(r => { if (!byDay.has(r.day)) byDay.set(r.day, []); byDay.get(r.day)!.push({ dir: r.direction_id, s: r.seconds }) })

  const WEEKS = 4
  const thisMon = mondayOf(new Date())
  const weekStarts: Date[] = []
  for (let i = WEEKS - 1; i >= 0; i--) { const d = new Date(thisMon); d.setDate(d.getDate() - i * 7); weekStarts.push(d) }
  const [sel, setSel] = useState(WEEKS - 1) // по умолчанию текущая неделя

  let maxTotal = 1
  weekStarts.forEach(ws => { for (let i = 0; i < 7; i++) { const d = new Date(ws); d.setDate(d.getDate() + i); const t = (byDay.get(ymd(d)) ?? []).reduce((a, b) => a + b.s, 0); if (t > maxTotal) maxTotal = t } })

  const weekLabel = (ws: Date) => { const e = new Date(ws); e.setDate(e.getDate() + 6); return `${ws.getDate()}–${e.getDate()} ${MON[e.getMonth()]}` }
  const weekTotal = (ws: Date) => { let s = 0; for (let i = 0; i < 7; i++) { const d = new Date(ws); d.setDate(d.getDate() + i); s += (byDay.get(ymd(d)) ?? []).reduce((a, b) => a + b.s, 0) } return s }

  const selWeek = weekStarts[sel]
  const selDays = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(selWeek); d.setDate(d.getDate() + i)
    return { i, date: d, total: (byDay.get(ymd(d)) ?? []).reduce((a, b) => a + b.s, 0) }
  })
  const todayStr = ymd(new Date())
  const usedDirs = directions.filter(d => rows.some(r => r.direction_id === d.id))

  return (
    <div>
      {/* Крупный круг выбранной недели + дни с часами */}
      <div className="flex items-center gap-6 flex-wrap">
        <WeekWheelSvg weekStart={selWeek} byDay={byDay} colorMap={colorMap} maxTotal={maxTotal} size={150} showLabels />
        <div className="flex-1 min-w-[180px]">
          <div className="text-sm text-[#ece7df] mb-2">{weekLabel(selWeek)} · {fmtDuration(weekTotal(selWeek))}</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            {selDays.map(d => {
              const isToday = ymd(d.date) === todayStr
              return (
                <div key={d.i} className="flex items-center justify-between text-xs">
                  <span className={isToday ? 'text-[#eab26c]' : 'text-[#8d8679]'}>{DOW[d.i]} {d.date.getDate()}</span>
                  <span className={d.total > 0 ? 'text-[#ccc]' : 'text-[#6f695f]'}>{d.total > 0 ? fmtDuration(d.total) : '—'}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* Недели-переключатели */}
      <div className="flex justify-around gap-2 mt-4 pt-4 border-t border-[#2a2723]">
        {weekStarts.map((ws, i) => (
          <button key={i} onClick={() => setSel(i)} className={`flex flex-col items-center rounded-lg px-2 py-1 transition-colors ${i === sel ? 'bg-[#2a2723]' : 'hover:bg-[#211f1c]'}`}>
            <WeekWheelSvg weekStart={ws} byDay={byDay} colorMap={colorMap} maxTotal={maxTotal} size={58} showLabels={false} />
            <div className={`text-[10px] mt-1 ${i === sel ? 'text-[#eab26c]' : 'text-[#7a7367]'}`}>{weekLabel(ws)}</div>
            <div className="text-[10px] text-[#6f695f]">{fmtDuration(weekTotal(ws))}</div>
          </button>
        ))}
      </div>

      {/* Легенда направлений */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-4 pt-3 border-t border-[#2a2723]">
        {usedDirs.map(d => (
          <div key={d.id} className="flex items-center gap-1.5 text-xs">
            <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: colorMap.get(d.id) ?? '#e0a458' }} />
            <span className="text-[#a49d90]">{d.name}</span>
          </div>
        ))}
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
  if (total === 0) return <div className="text-xs text-[#9c958a]">Пока нет данных о времени работы.</div>
  return (
    <div>
      <div className="grid grid-cols-4 gap-3">
        {parts.map(p => (
          <div key={p.key} className="text-center">
            <div className="h-24 flex items-end justify-center mb-2">
              <div className="w-8 rounded-t-md transition-all" style={{ height: `${Math.max(4, (p.seconds / max) * 100)}%`, backgroundColor: p.key === best.key ? '#e0a458' : '#3a352d' }} />
            </div>
            <div className="text-sm text-[#ece7df]">{fmtDuration(p.seconds)}</div>
            <div className="text-[11px] text-[#8d8679]">{p.label}</div>
            <div className="text-[10px] text-[#6f695f]">{p.sub}</div>
          </div>
        ))}
      </div>
      <div className="text-xs text-[#eab26c] mt-3">Продуктивнее всего — {best.label.toLowerCase()} ({best.sub}). Ставь сложное на это время.</div>
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
  const [dayDir, setDayDir] = useState<{ rows: { day: string; direction_id: number | null; seconds: number }[]; directions: { id: number; name: string }[] } | null>(null)
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
    api.getDayDirection(28).then(setDayDir).catch(() => {})
  }, [])

  return (
    <div className="h-full flex flex-col bg-[#141312] text-[#ece7df]">
      <div className="flex items-center gap-3 px-6 py-3.5 border-b border-border bg-header/40 shrink-0">
        <button onClick={onClose} className="btn-ghost -ml-2 !px-2 !py-1 text-[13px]">← Назад</button>
        <h1 className="text-[17px] font-semibold tracking-tight flex-1">Статистика</h1>
        <div className="flex gap-1">
          {(['week', 'month', 'all'] as Period[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs transition-colors border ${period === p ? 'bg-[#e0a458] border-[#e0a458] text-white' : 'border-[#2a2723] text-[#9c958a] hover:border-[#e0a458]/50'}`}
            >
              {p === 'week' ? 'Неделя' : p === 'month' ? 'Месяц' : 'Всё время'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {loading && <div className="text-[#9c958a] text-sm">Загрузка…</div>}

        {!loading && !data && (
          <div className="text-[#9c958a] text-sm">Не удалось загрузить данные</div>
        )}

        {motivation && <MotivationHero m={motivation} />}

        {!loading && data && (
          <>
            {/* Недели как спринты: круги дни × направления */}
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="section-label mb-4">Недели по направлениям</div>
              {!dayDir || dayDir.rows.length === 0 ? (
                <div className="flex items-center justify-center h-32 text-[#4a463f] text-sm">Нет данных</div>
              ) : (
                <WeeksSprints rows={dayDir.rows} directions={dayDir.directions} />
              )}
            </div>

            {/* Когда я продуктивен */}
            {byHour.some(h => h.seconds > 0) && (
              <div className="bg-card border border-border rounded-xl p-4">
                <div className="section-label mb-4">Когда я продуктивен</div>
                <ByPartOfDay data={byHour} />
              </div>
            )}

            {/* Календарь постоянства */}
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="flex items-center justify-between mb-4">
                <div className="section-label">Календарь постоянства</div>
                {consistency && (
                  <div className="text-[10px] text-[#9c958a]">
                    серия {consistency.streak} · рекорд {consistency.best} · {consistency.active} активных дней
                  </div>
                )}
              </div>
              <ConsistencyHeatmap data={heatmap} />
            </div>

            {/* Export */}
            <div className="bg-card border border-border rounded-xl p-4">
              <div className="section-label mb-3">Экспорт</div>
              <div className="flex gap-2">
                <a
                  href={`/api/export/sessions.csv?period=${period}`}
                  download
                  className="flex-1 text-center py-2 bg-[#2a2723] hover:bg-[#4a463f] rounded-lg text-xs text-[#a49d90] transition-colors"
                >
                  ↓ Сессии (.csv)
                </a>
                <a
                  href="/api/export/tasks.csv"
                  download
                  className="flex-1 text-center py-2 bg-[#2a2723] hover:bg-[#4a463f] rounded-lg text-xs text-[#a49d90] transition-colors"
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
