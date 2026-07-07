// Утренний визард: настроение и цель → выбор миссий (1–3).
import { useState, useMemo, useEffect } from 'react'
import type { Task, Direction } from '../types'
import { api, api2 } from '../api'
import { playSound } from '../sound'
import { MoodIcon } from '../components/Icon'
import { getDirectionColor } from '../utils/directionColors'
import { groupBySprint, fmtDM, thisMondayKey } from '../utils/sprint'
import { priorityLabel, priorityColor } from '../utils/priority'

interface Props {
  tasks: Task[]
  directions: Direction[]
  checkin: { exists: boolean; mood?: number | null; goal?: string | null } | null
  onDone: () => void
  onSkip: () => void
  onCheckinSaved: (mood: number, goal: string) => void
}

const todayStr = () => new Date().toISOString().slice(0, 10)

export default function MorningWizard({ tasks, directions, checkin, onDone, onSkip, onCheckinSaved }: Props) {
  const [step, setStep] = useState<1 | 2>(checkin?.exists ? 2 : 1)
  const [mood, setMood] = useState<number | null>(checkin?.mood ?? null)
  const [goal, setGoal] = useState(checkin?.goal ?? '')
  const [content, setContent] = useState('')
  const [selected, setSelected] = useState<number[]>([])
  const [newTitle, setNewTitle] = useState('')
  const [creating, setCreating] = useState(false)
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const [viewMode, setViewMode] = useState<'dir' | 'sprint'>('dir')

  const date = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })

  // Если утро уже заполнено — подтягиваем «свободные мысли», чтобы возврат на шаг 1
  // и повторное сохранение не затирали их пустым значением.
  useEffect(() => {
    if (checkin?.exists) {
      api.getTodayCheckin().then(d => { if (d?.content) setContent(d.content) }).catch(() => {})
    }
  }, [checkin?.exists])

  const available = useMemo(() => {
    const f = filter.trim().toLowerCase()
    const list = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday && t.slot !== 'now')
    return f ? list.filter(t => t.title.toLowerCase().includes(f)) : list
  }, [tasks, filter])

  const byDir = useMemo(() => {
    const groups: { dir: Direction | null; tasks: Task[] }[] = []
    directions.forEach(dir => {
      const dt = available.filter(t => t.direction_id === dir.id)
      if (dt.length > 0) groups.push({ dir, tasks: dt })
    })
    const noDir = available.filter(t => t.direction_id == null)
    if (noDir.length > 0) groups.push({ dir: null, tasks: noDir })
    return groups
  }, [available, directions])

  const bySprint = useMemo(() => groupBySprint(available), [available])
  const thisMonday = thisMondayKey()

  // A3: кандидаты «на сегодня» — задачи с дедлайном, отсортированные по горящести
  // (просрочка → ближайший дедлайн). Топ до 3.
  const candidates = useMemo(() => {
    const todayKey = todayStr()
    return available
      .filter(t => t.deadline)
      .sort((a, b) => (a.deadline as string).localeCompare(b.deadline as string))
      .map(t => {
        const dl = (t.deadline as string).slice(0, 10)
        return { t, overdue: dl < todayKey }
      })
      .sort((a, b) => Number(b.overdue) - Number(a.overdue))
      .map(x => x.t)
      .slice(0, 3)
  }, [available])

  const toggle = (id: number) => setSelected(prev =>
    prev.includes(id) ? prev.filter(x => x !== id) : prev.length >= 3 ? prev : [...prev, id]
  )

  // A3: одним нажатием добавить кандидатов в выбор (не превышая 3, без дублей).
  const takeTop3 = () => setSelected(prev => {
    const next = [...prev]
    for (const c of candidates) {
      if (next.length >= 3) break
      if (!next.includes(c.id)) next.push(c.id)
    }
    return next
  })

  const handleStep1Next = async () => {
    // Сохраняем при первом заполнении ИЛИ если вернулись и изменили настроение/цель.
    const changed = mood !== (checkin?.mood ?? null) || goal.trim() !== (checkin?.goal ?? '')
    if (mood && (!checkin?.exists || changed)) {
      try {
        await api.createJournalEntry({ type: 'checkin', mood, goal: goal.trim(), content: content.trim() })
        playSound('checkin_save')
        onCheckinSaved(mood, goal.trim())
        window.dispatchEvent(new CustomEvent('journal-updated'))
      } catch (e) { console.error(e) }
    }
    setStep(2)
  }

  const handleCreateInline = async () => {
    const t = newTitle.trim()
    if (!t || creating) return
    setCreating(true)
    try {
      const task = await api.createTask({ title: t, slot: 'queue' }) as { id: number }
      window.dispatchEvent(new CustomEvent('gamification-updated'))
      setSelected(prev => prev.length < 3 ? [...prev, task.id] : prev)
      setNewTitle('')
    } catch (e) { console.error(e) }
    setCreating(false)
  }

  const handleFinish = async () => {
    setSaving(true)
    try {
      await api2.setMissions(todayStr(), selected.map(id => ({ task_id: id })))
    } catch (e) { console.error(e) }
    setSaving(false)
    playSound('take_now')
    onDone()
  }

  const renderTask = (t: Task) => {
    const on = selected.includes(t.id)
    const dc = t.direction_id != null ? getDirectionColor(t.direction_id) : null
    return (
      <button key={t.id} onClick={() => toggle(t.id)}
        className={`w-full flex items-center gap-3 rounded-lg px-3.5 py-2.5 text-left transition-colors border
          ${on ? 'bg-accent/10 border-accent/50' : 'bg-card border-transparent hover:bg-raised'}`}>
        <span className={`w-4 h-4 rounded-md border flex items-center justify-center text-[10px] shrink-0 transition-colors
          ${on ? 'bg-accent border-accent text-[#1c1610]' : 'border-border-strong'}`}>{on ? '✓' : ''}</span>
        {t.priority && t.priority !== 'none' && (
          <span className="text-[11px] font-mono shrink-0" style={{ color: priorityColor(t.priority) }}>{priorityLabel(t.priority)}</span>
        )}
        <span className={`flex-1 text-[14px] truncate ${on ? 'text-text' : 'text-[#ddd6cb]'}`}>{t.title}</span>
        {viewMode === 'sprint' && dc && <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: dc }} />}
        {t.deadline && <span className="text-[10px] text-text-muted shrink-0">{new Date(t.deadline).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}</span>}
      </button>
    )
  }

  return (
    <div className="h-full overflow-y-auto" style={{ background: 'radial-gradient(80% 60% at 50% 0%, #1e1a15 0%, #100f0e 100%)' }}>
      <div className="max-w-xl mx-auto px-8 py-10 min-h-full flex flex-col animate-rise-in">

        {/* Шапка */}
        <div className="mb-8">
          <div className="text-[11px] font-semibold tracking-[0.2em] text-accent/80 uppercase mb-2">Утро · шаг {step} из 2</div>
          <h1 className="text-[26px] font-semibold tracking-tight text-text">
            {step === 1 ? 'Доброе утро' : 'Миссии дня'}
          </h1>
          <p className="text-[13px] text-text-muted capitalize mt-1">{step === 1 ? date : 'Выбери 1–3 главные задачи'}</p>
        </div>

        {/* Шаг 1: настроение + цель */}
        {step === 1 && (
          <div className="flex flex-col gap-6">
            <div>
              <label className="block text-[13px] text-text-secondary mb-3">Как ты сегодня?</label>
              <div className="flex gap-5">
                {[1, 2, 3, 4, 5].map(m => (
                  <button key={m} onClick={() => setMood(m)}
                    className={`transition-all duration-150 ${mood === m ? 'text-accent-light scale-125' : 'text-text-muted hover:text-text-secondary'}`}>
                    <MoodIcon mood={m} size={32} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-[13px] text-text-secondary mb-1.5">Главная цель дня</label>
              <textarea value={goal} onChange={e => setGoal(e.target.value)} rows={2} placeholder="Что сделает день не зря?"
                className="input w-full resize-none !text-[15px]" />
            </div>
            <div>
              <label className="block text-[13px] text-text-secondary mb-1.5">Свободные мысли</label>
              <textarea value={content} onChange={e => setContent(e.target.value)} rows={3} placeholder="Что на уме?"
                className="input w-full resize-none" />
            </div>
            <div className="flex items-center gap-2 mt-2">
              <button onClick={onSkip} className="btn-ghost">Пропустить утро</button>
              <span className="flex-1" />
              <button onClick={handleStep1Next} className="btn-primary !px-5">Дальше →</button>
            </div>
          </div>
        )}

        {/* Шаг 2: выбор миссий */}
        {step === 2 && (
          <div className="flex flex-col gap-4 flex-1">
            {/* A3: предложение на сегодня — горящие задачи с дедлайном */}
            {candidates.length > 0 && (
              <div className="rounded-xl border border-accent/25 bg-accent/[0.06] p-3">
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-accent/90">Предлагаю на сегодня</span>
                  <button onClick={takeTop3} className="btn-outline shrink-0 !py-1 !px-2.5 !text-[12px]">Взять топ-3</button>
                </div>
                <div className="space-y-1">{candidates.map(renderTask)}</div>
              </div>
            )}

            <div className="flex gap-2">
              <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Найти задачу…" className="input flex-1" />
              <div className="flex items-center gap-1 text-[13px] text-text-muted tabular-nums px-2 shrink-0">
                {[0, 1, 2].map(i => (
                  <span key={i} className={`w-2 h-2 rounded-full ${i < selected.length ? 'bg-accent' : 'bg-border-strong'}`} />
                ))}
              </div>
            </div>

            <div className="flex gap-1 bg-raised/50 rounded-lg p-0.5 text-[12px]">
              <button onClick={() => setViewMode('dir')}
                className={`flex-1 py-1 rounded-md transition-colors ${viewMode === 'dir' ? 'bg-accent text-white' : 'text-text-muted hover:text-text'}`}>
                По направлениям
              </button>
              <button onClick={() => setViewMode('sprint')}
                className={`flex-1 py-1 rounded-md transition-colors ${viewMode === 'sprint' ? 'bg-accent text-white' : 'text-text-muted hover:text-text'}`}>
                По спринтам
              </button>
            </div>

            <div className="flex-1 overflow-y-auto -mx-2 px-2 space-y-4 max-h-[46vh]">
              {viewMode === 'dir' && byDir.map(({ dir, tasks: dt }) => {
                const c = dir ? getDirectionColor(dir.id) : null
                return (
                  <div key={dir?.id ?? 'none'}>
                    <div className="flex items-center gap-2 mb-1.5">
                      {c && <span className="w-2 h-2 rounded-full" style={{ backgroundColor: c }} />}
                      <span className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: c ?? '#6f695f' }}>{dir?.name ?? 'Без направления'}</span>
                    </div>
                    <div className="space-y-1">{dt.map(renderTask)}</div>
                  </div>
                )
              })}

              {viewMode === 'sprint' && bySprint.groups.map(({ key, monday, tasks: st }) => {
                const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6)
                const isCurrent = key === thisMonday
                const isPast = key < thisMonday
                return (
                  <div key={key}>
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${isCurrent ? 'text-accent' : isPast ? 'text-danger/70' : 'text-text-secondary'}`}>{fmtDM(monday)}–{fmtDM(sunday)}</span>
                      {isCurrent && <span className="text-[9px] text-accent">· сейчас</span>}
                      <span className="text-[10px] text-text-faint tabular-nums">{st.length}</span>
                    </div>
                    <div className="space-y-1">{st.map(renderTask)}</div>
                  </div>
                )
              })}
              {viewMode === 'sprint' && bySprint.noDl.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-muted">Без срока</span>
                    <span className="text-[10px] text-text-faint tabular-nums">{bySprint.noDl.length}</span>
                  </div>
                  <div className="space-y-1">{bySprint.noDl.map(renderTask)}</div>
                </div>
              )}

              {((viewMode === 'dir' && byDir.length === 0) || (viewMode === 'sprint' && bySprint.groups.length === 0 && bySprint.noDl.length === 0)) &&
                <div className="text-[13px] text-text-muted py-6 text-center">Ничего не нашлось</div>}
            </div>

            {/* Новая задача сразу в миссии */}
            <div className="flex gap-2">
              <input
                value={newTitle}
                onChange={e => setNewTitle(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleCreateInline() }}
                placeholder="+ новая задача сразу в миссии…"
                className="input flex-1"
              />
              {newTitle.trim() && <button onClick={handleCreateInline} disabled={creating} className="btn-outline shrink-0">Создать</button>}
            </div>

            {/* A4: мягкая поддержка, когда пока ничего не выбрано */}
            {selected.length === 0 && (
              <p className="text-[12px] text-text-faint text-center px-2">
                Не можешь выбрать? Возьми одну маленькую — этого хватит на сегодня.
              </p>
            )}

            <div className="flex items-center gap-2 pt-1">
              <button onClick={() => setStep(1)} className="btn-ghost">← Назад</button>
              <span className="flex-1" />
              <button onClick={onSkip} className="btn-ghost text-text-muted">Сегодня без миссий</button>
              <button onClick={handleFinish} disabled={selected.length === 0 || saving} className="btn-primary !px-6 !py-2.5">{saving ? 'Сохраняю…' : 'Начать день ▶'}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
