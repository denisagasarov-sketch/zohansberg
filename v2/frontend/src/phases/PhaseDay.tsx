// Фаза «День»: до трёх миссий крупными карточками + живой таймлайн дня.
import { useState, useEffect, useCallback } from 'react'
import type { Task, Direction, DayThread } from '../types'
import { api, api2, type Mission, type TimelineSession } from '../api'
import { getDirectionColor } from '../utils/directionColors'
import { localKey } from '../utils/sprint'
import Icon, { MoodIcon } from '../components/Icon'
import SubtaskList from '../components/SubtaskList'
import DayThreadBlock from '../components/DayThreadBlock'
import GamificationBar from '../components/GamificationBar'

interface Props {
  missions: Mission[]
  missionsLoaded: boolean
  tasks: Task[]
  directions: Direction[]
  checkin: { exists: boolean; mood?: number | null; goal?: string | null } | null
  nowTaskId: number | null
  onFocus: (taskId: number) => void
  onMarkDone: (taskId: number) => void
  onEdit: (task: Task) => void
  onOpenLibrary: () => void
  onOpenMorning: () => void
  onOpenEvening: () => void
  onRemoveMission: (missionId: number) => void
  onReorder: (orderedTaskIds: number[]) => void
}

const todayStr = () => localKey(new Date())

function fmt(s: number): string {
  if (s < 60) return `${s}с`
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}

// ── Карточка миссии ────────────────────────────────────────────────────────────

function MissionCard({ mission, task, dir, active, recommended, onFocus, onMarkDone, onEdit, onRemove }: {
  mission: Mission
  task: Task | undefined
  dir: Direction | undefined
  active: boolean
  recommended?: boolean
  onFocus: () => void
  onMarkDone: () => void
  onEdit: () => void
  onRemove: () => void
}) {
  const done = !!mission.done_at
  const c = dir ? getDirectionColor(dir.id) : null
  const worked = mission.seconds_today > 0
  const suggest = !!recommended && !active && !done

  // Прогресс по шагам (подзадачам) — чтобы видеть их прямо на карточке миссии
  const [subs, setSubs] = useState<{ done: number; total: number }>({ done: 0, total: 0 })
  const [showSteps, setShowSteps] = useState(true)   // шаги развёрнуты по умолчанию
  const loadSubs = useCallback(() => {
    api.getSubtasks(mission.task_id)
      .then(list => setSubs({ done: (list as any[]).filter(s => s.done_at).length, total: (list as any[]).length }))
      .catch(() => {})
  }, [mission.task_id])
  useEffect(() => { loadSubs() }, [loadSubs])
  useEffect(() => {
    const h = () => loadSubs()
    window.addEventListener('gamification-updated', h)
    return () => window.removeEventListener('gamification-updated', h)
  }, [loadSubs])

  return (
    <div className={`group relative card-raised p-5 flex flex-col gap-3 transition-all duration-200 min-h-[180px]
      ${done ? 'opacity-55' : ''} ${active ? '!border-accent/50' : ''} ${suggest ? '!border-accent/30' : ''}`}
      style={active ? { boxShadow: '0 0 32px rgba(224,164,88,0.10), 0 8px 28px rgba(0,0,0,0.45)' } : undefined}
    >
      {suggest && (
        <span className="absolute -top-2 left-4 px-2 py-0.5 rounded-full text-[10px] font-medium bg-raised border border-accent/30 text-accent-light/80">
          начни с этой
        </span>
      )}
      <div className="flex items-center gap-2">
        <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-semibold tabular-nums shrink-0
          ${done ? 'bg-ok/20 text-ok' : 'bg-raised text-text-muted border border-border-strong'}`}>
          {done ? '✓' : mission.slot}
        </span>
        {dir && c && <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ color: c, backgroundColor: c + '22' }}>{dir.name}</span>}
        <span className="flex-1" />
        <button onClick={onRemove} title="Убрать из миссий дня" className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-text text-sm transition-opacity leading-none">×</button>
      </div>

      <button onClick={onEdit} className={`text-left text-[17px] font-semibold leading-snug tracking-tight hover:text-white transition-colors ${done ? 'line-through decoration-border-strong text-text-secondary' : 'text-text'}`}>
        {mission.title}
      </button>

      {/* Шаги (подзадачи) прямо на карточке миссии — можно добавлять и отмечать здесь же */}
      {!done && (
        <div>
          <button
            onClick={() => setShowSteps(v => !v)}
            className="flex items-center gap-1.5 text-[11px] text-text-secondary hover:text-text transition-colors"
          >
            <span className="text-text-faint">{showSteps ? '▾' : '▸'}</span>
            <span className="tabular-nums">{subs.total > 0 ? `Шаги ${subs.done}/${subs.total}` : 'разбить на шаги'}</span>
            {!showSteps && subs.total > 0 && (
              <span className="w-16 h-[3px] bg-border rounded-full overflow-hidden ml-1">
                <span className="block h-full bg-ok" style={{ width: `${Math.round((subs.done / subs.total) * 100)}%` }} />
              </span>
            )}
          </button>
          {showSteps && (
            <div className="mt-2">
              <SubtaskList
                key={mission.task_id}
                taskId={mission.task_id}
                compact
                onChanged={() => { loadSubs(); window.dispatchEvent(new CustomEvent('gamification-updated')) }}
              />
            </div>
          )}
        </div>
      )}

      <div className="flex-1" />

      {/* Время в фокусе сегодня */}
      <div>
        <div className="flex items-center justify-between text-[11px] mb-1.5">
          <span className="text-text-secondary tabular-nums">{worked ? `${fmt(mission.seconds_today)} в фокусе сегодня` : 'ещё не начата'}</span>
        </div>
        <div className="h-[4px] bg-border rounded-full overflow-hidden">
          <div className="h-full rounded-full transition-all duration-500"
            style={{ width: worked ? '100%' : '0%', backgroundColor: c ?? '#e0a458' }} />
        </div>
      </div>

      <div className="flex items-center gap-2">
        {!done && <button onClick={onFocus} className="btn-primary flex-1">{active ? '▶ Продолжить' : '▶ В фокус'}</button>}
        {done && <div className="text-[12px] text-ok flex-1 text-center py-1.5">Выполнено</div>}
      </div>
      {task?.notes && <div className="text-[11px] text-text-muted truncate" title={task.notes}>{task.notes}</div>}
    </div>
  )
}

// ── Таймлайн дня ───────────────────────────────────────────────────────────────

const TL_START = 6 * 60   // 06:00, минуты
const TL_END = 24 * 60    // 24:00

function TimelineBar({ sessions, thread, directions }: { sessions: TimelineSession[]; thread: DayThread | null; directions: Direction[] }) {
  const [nowMin, setNowMin] = useState(() => { const d = new Date(); return d.getHours() * 60 + d.getMinutes() })
  useEffect(() => {
    const id = setInterval(() => { const d = new Date(); setNowMin(d.getHours() * 60 + d.getMinutes()) }, 60_000)
    return () => clearInterval(id)
  }, [])

  const toPct = (min: number) => Math.max(0, Math.min(100, ((min - TL_START) / (TL_END - TL_START)) * 100))
  const parseMin = (iso: string) => { const d = new Date(iso.includes('T') ? iso : iso.replace(' ', 'T')); return d.getHours() * 60 + d.getMinutes() }

  const totalSec = sessions.reduce((s, x) => s + (x.duration_actual ?? 0), 0)
  const events = (thread?.events ?? []).filter(e => e.kind === 'subtask_done' || e.kind === 'task_done')

  return (
    <div className="card px-5 pt-3 pb-4 select-none">
      <div className="flex items-center gap-2 mb-3">
        <span className="section-label">Нить дня</span>
        <span className="text-[11px] text-text-secondary tabular-nums">{fmt(totalSec)} в фокусе · {sessions.length} сесс.</span>
      </div>

      <div className="relative h-9">
        {/* Часовые метки */}
        {[6, 9, 12, 15, 18, 21, 24].map(h => (
          <div key={h} className="absolute top-0 bottom-0 flex flex-col justify-between items-center" style={{ left: `${toPct(h * 60)}%` }}>
            <div className="w-px flex-1 bg-border" />
            <span className="text-[9px] text-text-faint tabular-nums -translate-x-1/2 absolute -bottom-0.5">{h === 24 ? '00' : h}</span>
          </div>
        ))}

        {/* Сессии */}
        {sessions.map(s => {
          const a = parseMin(s.started_at)
          // Длина полосы = фактическое время в фокусе (duration_actual), а не wall-clock
          // начало→конец: иначе сессия с долгой паузой/незакрытая растягивается на часы.
          const durMin = s.ended_at ? (s.duration_actual ?? 0) / 60 : Math.max(0, nowMin - a)
          const b = a + durMin
          const c = s.direction_id != null ? getDirectionColor(s.direction_id) : '#e0a458'
          return (
            <div
              key={s.id}
              title={`${s.title} · ${fmt(s.duration_actual ?? 0)}${s.note ? `\n${s.note}` : ''}`}
              className="absolute top-[7px] h-[12px] rounded-[3px] opacity-90 hover:opacity-100 hover:scale-y-110 transition-all"
              style={{ left: `${toPct(a)}%`, width: `${Math.max(0.6, toPct(b) - toPct(a))}%`, backgroundColor: c }}
            />
          )
        })}

        {/* События (закрытые шаги/задачи) */}
        {events.map((e, i) => (
          <div key={i} title={e.text} className="absolute top-[2px] w-[5px] h-[5px] rounded-full bg-ok" style={{ left: `${toPct(parseMin(e.at))}%` }} />
        ))}

        {/* Сейчас */}
        {nowMin >= TL_START && nowMin <= TL_END && (
          <div className="absolute top-0 bottom-2 w-px bg-accent-light" style={{ left: `${toPct(nowMin)}%` }}>
            <div className="w-[5px] h-[5px] rounded-full bg-accent-light -translate-x-1/2" />
          </div>
        )}
      </div>
    </div>
  )
}

// ── Фаза «День» ────────────────────────────────────────────────────────────────

export default function PhaseDay({ missions, missionsLoaded, tasks, directions, checkin, nowTaskId, onFocus, onMarkDone, onEdit, onOpenLibrary, onOpenMorning, onOpenEvening, onRemoveMission, onReorder }: Props) {
  const [sessions, setSessions] = useState<TimelineSession[]>([])
  const [thread, setThread] = useState<DayThread | null>(null)
  const [streak, setStreak] = useState<number | null>(null)
  const [dragMissionId, setDragMissionId] = useState<number | null>(null)

  const handleMissionDrop = (targetTaskId: number) => {
    const from = dragMissionId
    setDragMissionId(null)
    if (from == null || from === targetTaskId) return
    const ids = missions.map(m => m.task_id)
    const fi = ids.indexOf(from), ti = ids.indexOf(targetTaskId)
    if (fi === -1 || ti === -1) return
    ids.splice(fi, 1)
    ids.splice(ti, 0, from)
    onReorder(ids)
  }

  const load = useCallback(() => {
    const t = todayStr()
    api2.getTodaySessions(t).then(setSessions).catch(() => {})
    api.getDayThread(t).then(setThread).catch(() => {})
    api.getGamification().then(g => setStreak(g.streak)).catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const h = () => load()
    window.addEventListener('gamification-updated', h)
    window.addEventListener('journal-updated', h)
    return () => { window.removeEventListener('gamification-updated', h); window.removeEventListener('journal-updated', h) }
  }, [load])

  const date = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })
  const evening = new Date().getHours() >= 19
  const goal = checkin?.goal?.trim()

  const totalSec = sessions.reduce((s, x) => s + (x.duration_actual ?? 0), 0)

  // Локальная дата YYYY-MM-DD (без сдвига на UTC)
  const localDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  const today = localDay(new Date())

  // Активные задачи (не выполнены, не удалены, не «когда-нибудь», не в фокусе)
  const activeTasks = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday && t.slot !== 'now')

  // A1 — «горящая» задача для минимум-режима: просрочка → ближайший дедлайн → первая активная
  const deadlineMs = (t: Task) => (t.deadline ? new Date(t.deadline).getTime() : Number.POSITIVE_INFINITY)
  const withDeadline = activeTasks.filter(t => t.deadline).sort((a, b) => deadlineMs(a) - deadlineMs(b))
  const suggestedTask: Task | undefined = withDeadline[0] ?? activeTasks[0]

  // F3 — активные задачи с дедлайном сегодня (по локальной дате)
  const dueToday = activeTasks.filter(t => t.deadline && localDay(new Date(t.deadline)) === today)

  // B3 — прогресс дня в окне 06:00–22:00
  const DAY_END = 22 * 60
  const nowMinutes = (() => { const d = new Date(); return d.getHours() * 60 + d.getMinutes() })()
  const dayElapsed = Math.max(0, nowMinutes - TL_START)
  const untilEvening = Math.max(0, DAY_END - nowMinutes)
  const dayProgress = `день: прошло ${Math.floor(dayElapsed / 60)}ч ${dayElapsed % 60}м · до вечера ${Math.ceil(untilEvening / 60)}ч`

  // A2 — «одна следующая вещь»: если ничего не запущено, подсветить первую невыполненную миссию
  const recommendedMissionId = nowTaskId == null ? (missions.find(m => !m.done_at)?.id ?? null) : null

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-[1060px] mx-auto px-6 py-6 flex flex-col gap-5 min-h-full">

        {/* Шапка дня */}
        <div className="flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <div className="text-[13px] text-text-muted"><span className="capitalize">{date}</span>{streak ? <span className="text-accent/80"> · серия {streak} дн.</span> : null}</div>
            <button onClick={onOpenMorning} className="text-left mt-1 group flex items-center gap-2.5" title="Утренний ритуал">
              {checkin?.mood ? <span className="text-accent-light shrink-0"><MoodIcon mood={checkin.mood} size={20} /></span> : <span className="text-text-faint shrink-0"><Icon name="sun" size={20} /></span>}
              <span className={`text-[21px] font-semibold tracking-tight leading-snug group-hover:text-white transition-colors ${goal ? 'text-text' : 'text-text-muted'}`}>
                {goal || 'Без цели — просто хороший день'}
              </span>
            </button>
            <div className="mt-1 text-[11px] text-text-faint tabular-nums">{dayProgress}</div>
          </div>
          {totalSec > 0 && (
            <div className="shrink-0 text-right">
              <div className="text-[24px] font-mono font-semibold tabular-nums leading-none text-text">{fmt(totalSec)}</div>
              <div className="text-[10px] text-text-muted mt-1 uppercase tracking-[0.12em]">в фокусе сегодня</div>
            </div>
          )}
        </div>

        {/* Геймификация: серия, кольца дня и idle-нудж «не разорви цепочку» */}
        <GamificationBar />

        {/* F3 — дедлайн сегодня */}
        {dueToday.length > 0 && (
          <div className="flex items-center gap-3 rounded-lg border border-accent/25 bg-raised/40 px-4 py-2.5 text-[13px]">
            <span className="text-text-secondary min-w-0 flex-1 truncate">
              Сегодня дедлайн: <span className="text-text">{dueToday[0].title}</span>
              {dueToday.length > 1 && <span className="text-text-muted"> +{dueToday.length - 1}</span>}
            </span>
            <button onClick={() => onFocus(dueToday[0].id)} className="btn-outline shrink-0 hover:!border-accent/50 hover:!text-accent-light">Взять сейчас</button>
          </div>
        )}

        {/* Миссии */}
        {missionsLoaded && missions.length === 0 ? (
          <div className="card-raised px-8 py-14 text-center">
            <div className="text-text-secondary text-[15px] mb-1.5">Миссии дня не выбраны</div>
            <div className="text-text-muted text-[13px] mb-5">1–3 главные задачи, которые сделают день не зря</div>
            <button onClick={onOpenMorning} className="btn-primary">Выбрать миссии</button>
            {suggestedTask && (
              <div className="mt-6 pt-5 border-t border-border max-w-md mx-auto">
                <div className="text-text-muted text-[12px] mb-2">Или начни с малого:</div>
                <div className="text-text text-[14px] mb-3 truncate" title={suggestedTask.title}>{suggestedTask.title}</div>
                <button onClick={() => onFocus(suggestedTask.id)} className="btn-outline hover:!border-accent/50 hover:!text-accent-light">▶ 10 минут, и хватит</button>
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className={`grid gap-4 ${missions.length === 1 ? 'grid-cols-1 max-w-xl' : missions.length === 2 ? 'grid-cols-2' : 'grid-cols-3 max-lg:grid-cols-1'}`}>
              {missions.map(m => (
                <div
                  key={m.id}
                  draggable
                  onDragStart={e => { setDragMissionId(m.task_id); e.dataTransfer.effectAllowed = 'move' }}
                  onDragOver={e => e.preventDefault()}
                  onDrop={() => handleMissionDrop(m.task_id)}
                  className={`transition-opacity ${dragMissionId === m.task_id ? 'opacity-40' : ''} ${dragMissionId != null && dragMissionId !== m.task_id ? 'rounded-2xl ring-1 ring-transparent hover:ring-accent/40' : ''}`}
                >
                  <MissionCard
                    mission={m}
                    task={tasks.find(t => t.id === m.task_id)}
                    dir={directions.find(d => d.id === m.direction_id)}
                    active={nowTaskId === m.task_id}
                    recommended={recommendedMissionId === m.id}
                    onFocus={() => onFocus(m.task_id)}
                    onMarkDone={() => onMarkDone(m.task_id)}
                    onEdit={() => { const t = tasks.find(x => x.id === m.task_id); if (t) onEdit(t) }}
                    onRemove={() => onRemoveMission(m.id)}
                  />
                </div>
              ))}
            </div>
            {missions.length < 3 && (
              <button onClick={onOpenLibrary} title="Добавить миссию дня"
                className="mt-2.5 inline-flex items-center gap-1.5 text-[12px] text-text-muted hover:text-accent-light transition-colors">
                <span className="text-[14px] leading-none">+</span> добавить миссию
              </button>
            )}
          </div>
        )}

        <div className="flex-1" />

        {/* Таймлайн */}
        <TimelineBar sessions={sessions} thread={thread} directions={directions} />

        {/* Нить дня: шаги, заметки сессий, что сделал — прямо на дне, не только вечером */}
        <div className="mt-3"><DayThreadBlock onOpenTask={id => { const t = tasks.find(x => x.id === id); if (t) onEdit(t) }} /></div>

        {/* Нижняя строка */}
        <div className="flex items-center gap-3 text-[13px] -mt-1">
          <button onClick={onOpenLibrary} className="btn-ghost !px-2">
            <Icon name="archive" size={14} /> Библиотека
          </button>
          <span className="flex-1" />
          <button onClick={onOpenEvening} className={`btn-outline hover:!border-accent/50 hover:!text-accent-light${evening ? ' !border-accent/50 !text-accent-light' : ''}`}>
            <Icon name="sunset" size={14} /> Завершить день →
          </button>
        </div>
      </div>
    </div>
  )
}
