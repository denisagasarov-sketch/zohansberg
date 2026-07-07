// Библиотека: все задачи по направлениям. Действия: в фокус, в миссии, готово, редактор.
import { useState, useMemo, useEffect } from 'react'
import type { Task, Direction } from '../types'
import type { Mission } from '../api'
import { getDirectionColor } from '../utils/directionColors'
import { localKey, mondayOf, fmtDM, groupBySprint } from '../utils/sprint'
import { PriorityBadge } from '../components/PriorityPicker'
import Icon from '../components/Icon'

interface Props {
  tasks: Task[]
  directions: Direction[]
  missions: Mission[]
  nowTaskId?: number
  onClose: () => void
  onTaskClick: (t: Task) => void
  onNewTask: () => void
  onFocus: (taskId: number) => void
  onMarkDone: (taskId: number) => void
  onAddMission: (taskId: number) => void
  onPriorityChange: (taskId: number, priority: string) => void
  onChangeDirection: (taskId: number, directionId: number | null) => void
  onReorderInDirection: (directionId: number | null, orderedIds: number[]) => void
  onReorderSprint: (orderedIds: number[]) => void
  onReorder: (slot: string, orderedIds: number[]) => void
  onUpdateDirection: (id: number, data: Partial<Direction>) => void
}

const PRIORITY_RANK: Record<string, number> = { I: 1, II: 2, III: 3, none: 4 }

function Row({ task, dirColor, isMission, isNow, missionsFull, onClick, onFocus, onMarkDone, onAddMission, onPriorityChange }: {
  task: Task
  dirColor: string | null
  isMission: boolean
  isNow: boolean
  missionsFull: boolean
  onClick: () => void
  onFocus: () => void
  onMarkDone: () => void
  onAddMission: () => void
  onPriorityChange: (p: string) => void
}) {
  return (
    <div onClick={onClick}
      className={`group flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer hover:bg-raised/70 transition-colors ${isNow ? 'bg-accent/10' : ''}`}>
      <PriorityBadge priority={task.priority} onChange={onPriorityChange} />
      <span className="flex-1 text-[13px] text-[#ddd6cb] truncate">{task.title}</span>
      {isMission && <span title="Миссия дня" className="text-accent text-[11px] shrink-0">★</span>}
      {task.recurrence && <span className="text-[10px] text-accent/60 shrink-0" title="Повторяющаяся">↺</span>}
      {task.deadline && (() => {
        const d = new Date(task.deadline)
        const today = new Date(); today.setHours(0, 0, 0, 0)
        const s = d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        return <span className={`text-[10px] shrink-0 ${d < today ? 'text-danger/80' : 'text-text-muted'}`}>{s}</span>
      })()}
      {task.duration_plan ? <span className="text-[10px] text-text-muted shrink-0">{task.duration_plan}ч</span> : null}
      <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
        {!isMission && !missionsFull && (
          <button onClick={e => { e.stopPropagation(); onAddMission() }} title="В миссии дня" className="w-6 h-6 flex items-center justify-center rounded text-text-muted hover:text-accent-light transition-colors text-[12px]">★</button>
        )}
        <button onClick={e => { e.stopPropagation(); onFocus() }} title="В фокус" className="w-6 h-6 flex items-center justify-center rounded text-text-muted hover:text-accent-light transition-colors text-[10px]">▶</button>
        <button onClick={e => { e.stopPropagation(); onMarkDone() }} title="Готово" className="w-6 h-6 flex items-center justify-center rounded text-text-muted hover:text-ok transition-colors text-[12px]">✓</button>
      </div>
      {dirColor && <span className="w-1.5 h-1.5 rounded-full shrink-0 group-hover:hidden" style={{ backgroundColor: dirColor }} />}
    </div>
  )
}

export default function LibraryDrawer({ tasks, directions, missions, nowTaskId, onClose, onTaskClick, onNewTask, onFocus, onMarkDone, onAddMission, onPriorityChange, onReorderSprint }: Props) {
  const [filter, setFilter] = useState('')
  const [showSomeday, setShowSomeday] = useState(false)
  const [collapsed, setCollapsed] = useState<Set<number | 'none'>>(new Set())
  const [viewMode, setViewMode] = useState<'dir' | 'sprint'>('dir')
  const [collapsedSprints, setCollapsedSprints] = useState<Set<string>>(new Set())
  const [dragId, setDragId] = useState<number | null>(null)
  const [showReturnHint, setShowReturnHint] = useState(false)

  // Якорь возврата: спустя 10 минут открытой Библиотеки мягко напоминаем вернуться к работе.
  useEffect(() => {
    const timer = setTimeout(() => setShowReturnHint(true), 600000)
    return () => clearTimeout(timer)
  }, [])

  // Перетаскивание внутри недели: собираем новый порядок id и шлём на сервер.
  const handleSprintDrop = (weekTasks: Task[], targetId: number) => {
    if (dragId == null || dragId === targetId) { setDragId(null); return }
    const ids = weekTasks.map(t => t.id)
    const from = ids.indexOf(dragId), to = ids.indexOf(targetId)
    if (from === -1 || to === -1) { setDragId(null); return } // разные недели — не двигаем
    ids.splice(from, 1)
    ids.splice(to, 0, dragId)
    onReorderSprint(ids)
    setDragId(null)
  }

  const missionIds = new Set(missions.map(m => m.task_id))
  const missionsFull = missions.length >= 3

  const active = useMemo(() => {
    const f = filter.trim().toLowerCase()
    const list = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday)
    const filtered = f ? list.filter(t => t.title.toLowerCase().includes(f)) : list
    return [...filtered].sort((a, b) =>
      (PRIORITY_RANK[a.priority] ?? 4) - (PRIORITY_RANK[b.priority] ?? 4) ||
      (a.direction_order ?? 0) - (b.direction_order ?? 0) || a.id - b.id)
  }, [tasks, filter])

  const someday = useMemo(() => tasks.filter(t => t.someday && !t.done_at && !t.deleted_at), [tasks])

  const groups = useMemo(() => {
    const gs: { key: number | 'none'; dir: Direction | null; tasks: Task[] }[] = []
    directions.forEach(d => {
      const dt = active.filter(t => t.direction_id === d.id)
      if (dt.length > 0) gs.push({ key: d.id, dir: d, tasks: dt })
    })
    const noDir = active.filter(t => t.direction_id == null)
    if (noDir.length > 0) gs.push({ key: 'none', dir: null, tasks: noDir })
    return gs
  }, [active, directions])

  const toggleCollapse = (k: number | 'none') => setCollapsed(prev => {
    const next = new Set(prev)
    next.has(k) ? next.delete(k) : next.add(k)
    return next
  })

  // Группировка по спринтам: неделя (пн–вс) дедлайна. Задачи без срока — отдельно.
  const sprintGroups = useMemo(() => groupBySprint(active), [active])

  const thisMondayKey = localKey(mondayOf(localKey(new Date())))

  const toggleSprint = (k: string) => setCollapsedSprints(prev => {
    const next = new Set(prev)
    next.has(k) ? next.delete(k) : next.add(k)
    return next
  })

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/45 backdrop-blur-[3px]" />
      <div onClick={e => e.stopPropagation()}
        className="relative z-10 w-[560px] max-w-[90vw] h-full bg-card border-l border-border-strong flex flex-col shadow-2xl animate-drawer-in">

        {/* Шапка */}
        <div className="flex items-center gap-3 px-5 py-3.5 border-b border-border shrink-0">
          <span className="text-[15px] font-semibold tracking-tight">Библиотека</span>
          <span className="text-[11px] text-text-muted tabular-nums">{active.length} актив.</span>
          <span className="flex-1" />
          <button onClick={onNewTask} className="btn-outline !py-1 !px-2.5 text-[12px]">+ Задача</button>
          <button onClick={onClose} className="text-text-secondary hover:text-text text-lg leading-none transition-colors">×</button>
        </div>

        <div className="px-5 py-3 shrink-0 space-y-2.5">
          <input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Поиск по задачам…" autoFocus className="input w-full" />
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
        </div>

        {/* Список */}
        <div className="flex-1 overflow-y-auto px-3 pb-4 space-y-3">
          {showReturnHint && (
            <div className="flex items-center gap-2 mx-1 px-3 py-2 rounded-lg bg-raised/60 border border-border text-[12px] text-text-secondary">
              <span className="flex-1">Ты здесь уже 10 минут. Вернуться к работе?</span>
              <button
                onClick={() => { if (nowTaskId != null) onFocus(nowTaskId); else onClose() }}
                className="btn-outline !py-0.5 !px-2 text-[11px] shrink-0"
              >К задаче</button>
              <button
                onClick={() => setShowReturnHint(false)}
                title="Скрыть"
                className="text-text-muted hover:text-text text-base leading-none shrink-0"
              >×</button>
            </div>
          )}
          {viewMode === 'dir' && groups.map(({ key, dir, tasks: dt }) => {
            const c = dir ? getDirectionColor(dir.id) : null
            const isCollapsed = collapsed.has(key)
            return (
              <div key={String(key)}>
                <button onClick={() => toggleCollapse(key)} className="w-full flex items-center gap-2 px-3 py-1.5 select-none">
                  {c && <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: c }} />}
                  <span className="text-[11px] font-semibold uppercase tracking-[0.12em]" style={{ color: c ?? '#6f695f' }}>{dir?.name ?? 'Без направления'}</span>
                  <span className="text-[10px] text-text-faint tabular-nums">{dt.length}</span>
                  <span className="flex-1 border-t border-border ml-1" />
                  <span className="text-[10px] text-text-faint">{isCollapsed ? '▸' : '▾'}</span>
                </button>
                {!isCollapsed && (
                  <div className="space-y-0.5">
                    {dt.map(t => (
                      <Row
                        key={t.id}
                        task={t}
                        dirColor={c}
                        isMission={missionIds.has(t.id)}
                        isNow={nowTaskId === t.id}
                        missionsFull={missionsFull}
                        onClick={() => onTaskClick(t)}
                        onFocus={() => { onClose(); onFocus(t.id) }}
                        onMarkDone={() => onMarkDone(t.id)}
                        onAddMission={() => onAddMission(t.id)}
                        onPriorityChange={p => onPriorityChange(t.id, p)}
                      />
                    ))}
                  </div>
                )}
              </div>
            )
          })}
          {viewMode === 'dir' && groups.length === 0 && <div className="text-[13px] text-text-muted text-center py-10">Пусто. Создай первую задачу</div>}

          {/* Вид по спринтам: неделя дедлайна */}
          {viewMode === 'sprint' && sprintGroups.groups.map(({ key, monday, tasks: st }) => {
            const sunday = new Date(monday); sunday.setDate(monday.getDate() + 6)
            const isCurrent = key === thisMondayKey
            const isPast = key < thisMondayKey
            const isCollapsed = collapsedSprints.has(key)
            // Порядок внутри недели — по sprint_order (перетаскивание), стабильно при равенстве.
            const ordered = [...st].sort((a, b) => (a.sprint_order ?? 0) - (b.sprint_order ?? 0))
            return (
              <div key={key}>
                <button onClick={() => toggleSprint(key)} className="w-full flex items-center gap-2 px-3 py-1.5 select-none">
                  <span className={`text-[11px] font-semibold uppercase tracking-[0.12em] ${isCurrent ? 'text-accent' : isPast ? 'text-danger/70' : 'text-text-secondary'}`}>{fmtDM(monday)}–{fmtDM(sunday)}</span>
                  {isCurrent && <span className="text-[9px] text-accent lowercase tracking-normal font-normal">· сейчас</span>}
                  <span className="text-[10px] text-text-faint tabular-nums">{ordered.length}</span>
                  <span className="flex-1 border-t border-border ml-1" />
                  <span className="text-[10px] text-text-faint">{isCollapsed ? '▸' : '▾'}</span>
                </button>
                {!isCollapsed && (
                  <div className="space-y-0.5">
                    {ordered.map(t => {
                      const c = t.direction_id != null ? getDirectionColor(t.direction_id) : null
                      return (
                        <div
                          key={t.id}
                          draggable
                          onDragStart={() => setDragId(t.id)}
                          onDragOver={e => e.preventDefault()}
                          onDrop={() => handleSprintDrop(ordered, t.id)}
                          className={`rounded-lg transition-opacity ${dragId === t.id ? 'opacity-40' : ''} ${dragId != null && dragId !== t.id ? 'hover:ring-1 hover:ring-accent/40' : ''}`}
                        >
                          <Row
                            task={t}
                            dirColor={c}
                            isMission={missionIds.has(t.id)}
                            isNow={nowTaskId === t.id}
                            missionsFull={missionsFull}
                            onClick={() => onTaskClick(t)}
                            onFocus={() => { onClose(); onFocus(t.id) }}
                            onMarkDone={() => onMarkDone(t.id)}
                            onAddMission={() => onAddMission(t.id)}
                            onPriorityChange={p => onPriorityChange(t.id, p)}
                          />
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}
          {viewMode === 'sprint' && sprintGroups.noDl.length > 0 && (
            <div>
              <div className="w-full flex items-center gap-2 px-3 py-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-muted">Без срока</span>
                <span className="text-[10px] text-text-faint tabular-nums">{sprintGroups.noDl.length}</span>
                <span className="flex-1 border-t border-border ml-1" />
              </div>
              <div className="space-y-0.5">
                {sprintGroups.noDl.map(t => {
                  const c = t.direction_id != null ? getDirectionColor(t.direction_id) : null
                  return (
                    <Row
                      key={t.id}
                      task={t}
                      dirColor={c}
                      isMission={missionIds.has(t.id)}
                      isNow={nowTaskId === t.id}
                      missionsFull={missionsFull}
                      onClick={() => onTaskClick(t)}
                      onFocus={() => { onClose(); onFocus(t.id) }}
                      onMarkDone={() => onMarkDone(t.id)}
                      onAddMission={() => onAddMission(t.id)}
                      onPriorityChange={p => onPriorityChange(t.id, p)}
                    />
                  )
                })}
              </div>
            </div>
          )}
          {viewMode === 'sprint' && sprintGroups.groups.length === 0 && sprintGroups.noDl.length === 0 && <div className="text-[13px] text-text-muted text-center py-10">Пусто. Создай первую задачу</div>}

          {/* Когда-нибудь */}
          {someday.length > 0 && (
            <div className="pt-2">
              <button onClick={() => setShowSomeday(v => !v)} className="w-full flex items-center gap-2 px-3 py-1.5 select-none">
                <span className="text-text-muted"><Icon name="moon" size={13} /></span>
                <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-muted">Когда-нибудь</span>
                <span className="text-[10px] text-text-faint tabular-nums">{someday.length}</span>
                <span className="flex-1 border-t border-border ml-1" />
                <span className="text-[10px] text-text-faint">{showSomeday ? '▾' : '▸'}</span>
              </button>
              {showSomeday && someday.map(t => (
                <div key={t.id} onClick={() => onTaskClick(t)} className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg cursor-pointer hover:bg-raised/70 transition-colors">
                  <span className="flex-1 text-[12px] italic text-text-secondary truncate">{t.title}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="px-5 py-2.5 border-t border-border text-[10px] text-text-faint shrink-0">
          ★ — в миссии дня · ▶ — в фокус · клик — редактор · ⌘L — закрыть
        </div>
      </div>
    </div>
  )
}
