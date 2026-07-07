// Фаза «Вечер»: итог дня, рефлексия, миссии на завтра.
import { useState, useEffect, useMemo } from 'react'
import type { Task, Direction } from '../types'
import { api, api2, type Mission } from '../api'
import { playSound } from '../sound'
import DayThreadBlock from '../components/DayThreadBlock'
import { getDirectionColor } from '../utils/directionColors'

interface Props {
  tasks: Task[]
  directions: Direction[]
  missions: Mission[]
  onClose: () => void
}

function fmt(s: number): string {
  if (s < 60) return `${s}с`
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

export default function PhaseEvening({ tasks, directions, missions, onClose }: Props) {
  const [summary, setSummary] = useState<{ done_count: number; time_seconds: number } | null>(null)
  const [reflection, setReflection] = useState('')
  const [tomorrowSel, setTomorrowSel] = useState<number[]>([])
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)

  const missionsDone = missions.filter(m => m.done_at).length

  useEffect(() => {
    api.getTodaySummary()
      .then((d: any) => {
        const s = { done_count: d.done_count, time_seconds: d.time_seconds }
        setSummary(s)
        // Фанфара только над непустым днём — не бьём по RSD в тяжёлый день.
        if (s.done_count > 0 || s.time_seconds > 0 || missionsDone > 0) {
          playSound('fanfare', 1.0)
        }
      })
      .catch(() => {})
  }, [missionsDone])

  // Тёплая строка-итог: ведёт от достигнутого, отличает «выстоял» от «пустого дня».
  const summaryLine = useMemo(() => {
    if (!summary) return null
    const hasFocus = summary.time_seconds > 0
    const hasDone = summary.done_count > 0
    if (missionsDone > 0) {
      return 'Миссии закрыты — ты довёл главное до конца. Это и есть день, который считается.'
    }
    if (hasFocus || hasDone) {
      return hasFocus
        ? `Ты провёл ${fmt(summary.time_seconds)} в фокусе — движение есть, даже если миссии ещё в работе.`
        : 'Задачи сдвинулись с места — это уже вклад, даже если миссии ещё в работе.'
    }
    return 'Сегодня не разогналось — и это ок. Завтра свежий старт.'
  }, [summary, missionsDone])
  const date = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1)
  const tomorrowDate = tomorrow.toISOString().slice(0, 10)
  const tomorrowLabel = tomorrow.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

  const available = useMemo(() => {
    const f = filter.trim().toLowerCase()
    const list = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday)
    return f ? list.filter(t => t.title.toLowerCase().includes(f)) : list
  }, [tasks, filter])

  const toggle = (id: number) => setTomorrowSel(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : prev.length >= 3 ? prev : [...prev, id]
  )

  const handleClose = async () => {
    setSaving(true)
    try {
      if (reflection.trim()) {
        await api.createJournalEntry({ type: 'thought', content: `Итог дня: ${reflection.trim()}` })
        window.dispatchEvent(new CustomEvent('journal-updated'))
      }
      if (tomorrowSel.length > 0) {
        await api2.setMissions(tomorrowDate, tomorrowSel.map(id => ({ task_id: id })))
      }
    } catch (e) { console.error(e) }
    setSaving(false)
    onClose()
  }

  return (
    <div className="h-full overflow-y-auto" style={{ background: 'radial-gradient(80% 60% at 50% 0%, #1d1712 0%, #100f0e 100%)' }}>
      <div className="max-w-xl mx-auto px-8 py-10 min-h-full flex flex-col gap-6 animate-rise-in">

        <div>
          <div className="text-[11px] font-semibold tracking-[0.2em] text-accent/80 uppercase mb-2">Вечер</div>
          <h1 className="text-[26px] font-semibold tracking-tight text-text">Итог дня</h1>
          <p className="text-[13px] text-text-muted capitalize mt-1">{date}</p>
          {summaryLine && <p className="text-[13px] text-text-secondary mt-2">{summaryLine}</p>}
        </div>

        {/* Цифры дня */}
        <div className="grid grid-cols-3 gap-3">
          <div className="card-raised p-4">
            <div className="text-[24px] font-mono font-semibold tabular-nums text-text leading-none">{summary ? fmt(summary.time_seconds) : '—'}</div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">в фокусе</div>
          </div>
          <div className="card-raised p-4">
            <div className="text-[24px] font-mono font-semibold tabular-nums text-text leading-none">{missionsDone}<span className="text-text-muted">/{missions.length || '—'}</span></div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">миссий закрыто</div>
          </div>
          <div className="card-raised p-4">
            <div className="text-[24px] font-mono font-semibold tabular-nums text-text leading-none">{summary?.done_count ?? '—'}</div>
            <div className="text-[10px] text-text-muted mt-1.5 uppercase tracking-[0.1em]">задач сделано</div>
          </div>
        </div>

        {/* Миссии дня */}
        {missions.length > 0 && (
          <div className="space-y-1.5">
            {missions.map(m => {
              const c = m.direction_id != null ? getDirectionColor(m.direction_id) : null
              return (
                <div key={m.id} className="flex items-center gap-3 bg-bg-sunken/60 rounded-lg px-3.5 py-2.5">
                  <span className={`text-[13px] shrink-0 ${m.done_at ? 'text-ok' : 'text-text-faint'}`}>{m.done_at ? '✓' : '·'}</span>
                  <span className={`flex-1 text-[13px] truncate ${m.done_at ? 'text-text-secondary' : 'text-text'}`}>{m.title}</span>
                  {!m.done_at && <span className="text-[11px] text-text-muted shrink-0">в работе</span>}
                  {c && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: c }} />}
                  <span className="text-[11px] text-text-muted tabular-nums shrink-0">{fmt(m.seconds_today)}</span>
                </div>
              )
            })}
          </div>
        )}

        {/* Лента дня */}
        <DayThreadBlock />

        {/* Рефлексия */}
        <div>
          <label className="block text-[13px] text-text-secondary mb-1.5">Как прошёл день? Пара строк для дневника</label>
          <textarea value={reflection} onChange={e => setReflection(e.target.value)} rows={3}
            placeholder="Что получилось, что мешало, что понял…" className="input w-full resize-none" />
        </div>

        {/* Завтра */}
        <div>
          <div className="flex items-baseline justify-between mb-2">
            <span className="text-[13px] text-text-secondary">Миссии на завтра <span className="capitalize text-text-muted">· {tomorrowLabel}</span></span>
            <div className="flex items-center gap-1">
              {[0, 1, 2].map(i => <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < tomorrowSel.length ? 'bg-accent' : 'bg-border-strong'}`} />)}
            </div>
          </div>
          <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Найти задачу…" className="input w-full mb-2" />
          <div className="max-h-56 overflow-y-auto space-y-1 pr-1">
            {available.map(t => {
              const on = tomorrowSel.includes(t.id)
              const c = t.direction_id != null ? getDirectionColor(t.direction_id) : null
              return (
                <button key={t.id} onClick={() => toggle(t.id)}
                  className={`w-full flex items-center gap-3 rounded-lg px-3.5 py-2 text-left transition-colors border
                    ${on ? 'bg-accent/10 border-accent/50' : 'bg-card border-transparent hover:bg-raised'}`}>
                  <span className={`w-4 h-4 rounded-md border flex items-center justify-center text-[10px] shrink-0 ${on ? 'bg-accent border-accent text-[#1c1610]' : 'border-border-strong'}`}>{on ? '✓' : ''}</span>
                  <span className={`flex-1 text-[13px] truncate ${on ? 'text-text' : 'text-[#ddd6cb]'}`}>{t.title}</span>
                  {c && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: c }} />}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center gap-2 pb-4">
          <button onClick={onClose} className="btn-ghost">Позже</button>
          <span className="flex-1" />
          <button onClick={handleClose} disabled={saving} className="btn-primary !px-6 !py-2.5">{saving ? 'Сохраняю…' : 'Закрыть день'}</button>
        </div>
      </div>
    </div>
  )
}
