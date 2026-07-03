import { useState, useEffect, useRef, useCallback } from 'react'
import SubtaskList from './SubtaskList'
import type { Task, Direction } from '../types'
import { api } from '../api'
import { playSound } from '../sound'

interface Props {
  task: Task | null
  directions: Direction[]
  onClose: () => void
  onSaved: () => void
  onDeleted: () => void
  onTakenNow: () => void
  onMarkDone?: () => void
}

interface WorkSession {
  id: number
  started_at: string
  ended_at: string | null
  duration_actual: number | null
  note: string | null
}

function Btn({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded text-xs transition-colors border ${
        active
          ? 'bg-[#5060a0] border-[#5060a0] text-white'
          : 'bg-transparent border-[#252525] text-[#666] hover:border-[#5060a0]/50'
      }`}
    >
      {children}
    </button>
  )
}

function formatDur(s: number | null): string {
  if (!s) return '—'
  const m = Math.floor(s / 60)
  const h = Math.floor(m / 60)
  if (h > 0) return `${h}ч ${m % 60}мин`
  return `${m} мин`
}

function formatSessionLine(started_at: string, ended_at: string | null, duration_actual: number | null): string {
  const d = new Date(started_at)
  const date = d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  const start = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  const end = ended_at ? new Date(ended_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : null
  const dur = formatDur(duration_actual)
  return end ? `${date}, ${start} → ${end} · ${dur}` : `${date}, ${start} · ${dur}`
}

export default function TaskEditor({ task, directions, onClose, onSaved, onDeleted, onTakenNow, onMarkDone }: Props) {
  const [title, setTitle] = useState(task?.title ?? '')
  const [directionId, setDirectionId] = useState<number | null>(task?.direction_id ?? null)
  const [deadline, setDeadline] = useState(task?.deadline?.slice(0, 10) ?? '')
  const [durationPlan, setDurationPlan] = useState<string>(task?.duration_plan?.toString() ?? '')
  const [notes, setNotes] = useState(task?.notes ?? '')
  const [someday, setSomeday] = useState(!!task?.someday)
  const [recurrence, setRecurrence] = useState<string>(task?.recurrence ?? '')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([])
  const [aiError, setAiError] = useState('')
  const [sessions, setSessions] = useState<WorkSession[]>([])
  const [sessionsLoaded, setSessionsLoaded] = useState(false)
  const [showAddForm, setShowAddForm] = useState(false)
  const [addDate, setAddDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [addTime, setAddTime] = useState('00:00')
  const [addMinutes, setAddMinutes] = useState('')
  const [addNote, setAddNote] = useState('')
  const [addSaving, setAddSaving] = useState(false)
  const [addError, setAddError] = useState('')
  const titleRef = useRef<HTMLTextAreaElement>(null)
  const notesRef = useRef<HTMLTextAreaElement>(null)

  const isDirty = useCallback(() => {
    return (
      title !== (task?.title ?? '') ||
      directionId !== (task?.direction_id ?? null) ||
      deadline !== (task?.deadline?.slice(0, 10) ?? '') ||
      durationPlan !== (task?.duration_plan?.toString() ?? '') ||
      notes !== (task?.notes ?? '') ||
      someday !== !!task?.someday
    )
  }, [title, directionId, deadline, durationPlan, notes, task])

  useEffect(() => {
    setTimeout(() => titleRef.current?.focus(), 50)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isDirty()) {
          if (window.confirm('Есть несохранённые изменения. Закрыть?')) onClose()
        } else {
          onClose()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isDirty, onClose])

  useEffect(() => {
    if (task && !sessionsLoaded) {
      api.getTaskSessions(task.id).then(s => {
        setSessions(s)
        setSessionsLoaded(true)
      }).catch(() => setSessionsLoaded(true))
    }
  }, [task, sessionsLoaded])

  // Auto-grow notes textarea
  useEffect(() => {
    const el = notesRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.max(80, el.scrollHeight)}px`
  }, [notes])

  const handleSave = async () => {
    if (!title.trim()) return
    setSaving(true)
    try {
      const data: Partial<Task> = {
        title: title.trim(),
        direction_id: directionId,
        deadline: deadline || null,
        duration_plan: durationPlan ? parseFloat(durationPlan) : null,
        notes: notes || null,
        recurrence: (recurrence || null) as Task['recurrence'],
        someday: someday as any,
        ...(someday ? { in_queue: false as any } : {}),
      }
      if (task) {
        await api.updateTask(task.id, data)
      } else {
        await api.createTask(data)
        playSound('new_task')
      }
      onSaved()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!task) return
    if (!confirmDelete) { setConfirmDelete(true); return }
    try {
      await api.deleteTask(task.id)
      playSound('task_delete')
      onDeleted()
    } catch (e) {
      console.error(e)
    }
  }

  const handleTakeNow = async () => {
    if (!task) return
    try {
      await api.takeNow(task.id)
      playSound('take_now')
      onTakenNow()
    } catch (e) {
      console.error(e)
    }
  }

  const handleAddSession = async () => {
    if (!task || !addMinutes || !addDate) return
    setAddSaving(true)
    setAddError('')
    try {
      const duration_seconds = Math.round(parseFloat(addMinutes) * 60)
      const started_at = new Date(`${addDate}T${addTime}:00`).toISOString()
      const ended_at = new Date(new Date(started_at).getTime() + duration_seconds * 1000).toISOString()
      const session = await api.createManualSession(task.id, {
        started_at,
        ended_at,
        duration_seconds,
        note: addNote || undefined,
      })
      setSessions(prev => [session, ...prev])
      setShowAddForm(false)
      setAddMinutes('')
      setAddNote('')
      setAddDate(new Date().toISOString().slice(0, 10))
      setAddTime('00:00')
    } catch (e: any) {
      setAddError(e?.message ?? 'Ошибка')
    } finally {
      setAddSaving(false)
    }
  }

  const handleOverlayClick = () => {
    if (isDirty()) {
      if (window.confirm('Есть несохранённые изменения. Закрыть?')) onClose()
    } else {
      onClose()
    }
  }

  const handleImproveTitle = async () => {
    if (!title.trim()) return
    setAiLoading(true)
    setAiError('')
    setAiSuggestions([])
    try {
      const direction = directions.find(d => d.id === directionId)?.name
      const result = await api.suggestTitle({
        title: title.trim(),
        direction,
        deadline: deadline || undefined,
        notes: notes || undefined,
      })
      setAiSuggestions(result.suggestions)
    } catch (e: any) {
      const msg = e?.message ?? ''
      if (msg.includes('400')) {
        setAiError('Добавьте OpenAI API Key в настройках')
      } else {
        setAiError('Ошибка при обращении к AI')
      }
    } finally {
      setAiLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end" onClick={handleOverlayClick}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative z-10 w-[360px] h-full bg-[#1c1c1c] border-l border-[#252525] flex flex-col overflow-hidden shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#252525] shrink-0">
          <span className="text-xs text-[#666]">{task ? 'Редактировать задачу' : 'Новая задача'}</span>
          <button onClick={handleOverlayClick} className="text-[#666] hover:text-[#f0f0f0] transition-colors text-lg leading-none">×</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Title + AI */}
          <div className="relative">
            <textarea
              ref={titleRef}
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Название задачи"
              rows={2}
              className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 pr-9 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838]"
            />
            <button
              onClick={handleImproveTitle}
              disabled={!title.trim() || aiLoading}
              title="Улучшить формулировку (AI)"
              className="absolute top-2 right-2 text-base text-[#383838] hover:text-[#8090c8] disabled:opacity-30 transition-colors"
            >
              {aiLoading ? '…' : '✨'}
            </button>
            {aiSuggestions.length > 0 && (
              <div className="mt-2 space-y-1">
                {aiSuggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => { setTitle(s); setAiSuggestions([]) }}
                    className="w-full text-left text-xs px-2.5 py-1.5 bg-[#141414] border border-[#252525] rounded hover:border-[#5060a0]/60 hover:text-[#f0f0f0] text-[#999] transition-colors"
                  >
                    {s}
                  </button>
                ))}
                <button onClick={() => setAiSuggestions([])} className="text-[10px] text-[#383838] hover:text-[#666] transition-colors">скрыть</button>
              </div>
            )}
            {aiError && (
              <p className="text-[10px] text-[#a07030] mt-1">{aiError}</p>
            )}
          </div>

          {/* Direction */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Направление</label>
            <div className="flex flex-wrap gap-1.5">
              <Btn active={directionId === null} onClick={() => setDirectionId(null)}>Без направления</Btn>
              {directions.map(d => (
                <Btn key={d.id} active={directionId === d.id} onClick={() => setDirectionId(d.id)}>{d.name}</Btn>
              ))}
            </div>
          </div>

          {/* Deadline */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Дедлайн</label>
            <div className="flex gap-2 items-center">
              <input
                type="date"
                value={deadline}
                onChange={e => setDeadline(e.target.value)}
                className="flex-1 bg-[#141414] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] [color-scheme:dark]"
              />
              {deadline && (
                <button onClick={() => setDeadline('')} className="text-[#666] hover:text-[#f0f0f0] text-sm">×</button>
              )}
            </div>
          </div>

          {/* Duration */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Время (ч)</label>
            <input
              type="number"
              min={0}
              step={0.5}
              value={durationPlan}
              onChange={e => setDurationPlan(e.target.value)}
              placeholder="0.5"
              className="w-28 bg-[#141414] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
            />
          </div>

          {/* Recurrence */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Повтор</label>
            <select
              value={recurrence}
              onChange={e => setRecurrence(e.target.value)}
              className="bg-[#141414] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
            >
              <option value="">Нет</option>
              <option value="daily">Каждый день</option>
              <option value="weekdays">Будни</option>
              <option value="weekly">Каждую неделю</option>
              <option value="monthly">Каждый месяц</option>
            </select>
          </div>

          {/* Someday */}
          <label className="flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={someday}
              onChange={e => setSomeday(e.target.checked)}
              className="w-3.5 h-3.5 accent-[#5060a0]"
            />
            <span className="text-xs text-[#666]">Когда-нибудь</span>
          </label>

          {/* Sessions block — only for existing tasks */}
          {task && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="block text-[10px] text-[#666] uppercase tracking-wider">Лог сессий</label>
                {sessionsLoaded && sessions.length > 0 && (
                  <span className="text-[10px] text-[#5060a0]">
                    {formatDur(sessions.reduce((s, r) => s + (r.duration_actual ?? 0), 0))} итого
                  </span>
                )}
              </div>
              {!sessionsLoaded ? (
                <p className="text-xs text-[#555]">Загружаю…</p>
              ) : sessions.length === 0 ? (
                <p className="text-xs text-[#383838]">Сессий пока нет</p>
              ) : (
                sessions.map(s => (
                  <div key={s.id} className="bg-[#141414] border border-[#252525] rounded px-3 py-2">
                    <span className="text-[10px] text-[#666]">{formatSessionLine(s.started_at, s.ended_at, s.duration_actual)}</span>
                    {s.note && <p className="text-xs text-[#999] mt-1">{s.note}</p>}
                  </div>
                ))
              )}

              {showAddForm ? (
                <div className="bg-[#141414] border border-[#252525] rounded px-3 py-3 space-y-2">
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="block text-[10px] text-[#666] mb-1">Дата</label>
                      <input
                        type="date"
                        value={addDate}
                        onChange={e => setAddDate(e.target.value)}
                        className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-xs text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] [color-scheme:dark]"
                      />
                    </div>
                    <div className="w-20">
                      <label className="block text-[10px] text-[#666] mb-1">Начало</label>
                      <input
                        type="time"
                        value={addTime}
                        onChange={e => setAddTime(e.target.value)}
                        className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-xs text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] [color-scheme:dark]"
                      />
                    </div>
                    <div className="w-16">
                      <label className="block text-[10px] text-[#666] mb-1">Минуты</label>
                      <input
                        type="number"
                        min={1}
                        value={addMinutes}
                        onChange={e => setAddMinutes(e.target.value)}
                        placeholder="30"
                        className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-xs text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] text-[#666] mb-1">Заметка</label>
                    <input
                      type="text"
                      value={addNote}
                      onChange={e => setAddNote(e.target.value)}
                      placeholder="необязательно"
                      className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-xs text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] placeholder-[#383838]"
                    />
                  </div>
                  {addError && <p className="text-[10px] text-red-400">{addError}</p>}
                  <div className="flex gap-2 justify-end pt-1">
                    <button
                      onClick={() => { setShowAddForm(false); setAddMinutes(''); setAddNote(''); setAddTime('00:00'); setAddError('') }}
                      className="px-2.5 py-1 text-xs text-[#666] hover:text-[#f0f0f0] transition-colors"
                    >
                      Отмена
                    </button>
                    <button
                      onClick={handleAddSession}
                      disabled={addSaving || !addMinutes || !addDate}
                      className="px-2.5 py-1 text-xs bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-50 rounded text-white transition-colors"
                    >
                      {addSaving ? 'Сохраняю…' : 'Сохранить'}
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="w-full text-left text-xs text-[#383838] hover:text-[#666] transition-colors py-1"
                >
                  + Добавить вручную
                </button>
              )}
            </div>
          )}

          {/* Шаги (подзадачи) — доступны только для сохранённой задачи */}
          {task && (
            <div>
              <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Шаги</label>
              <SubtaskList taskId={task.id} onChanged={() => window.dispatchEvent(new CustomEvent('gamification-updated'))} />
            </div>
          )}

          {/* Notes */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Заметки</label>
            <textarea
              ref={notesRef}
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Детали, ссылки, мысли…"
              style={{ minHeight: '80px', height: 'auto' }}
              className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838] overflow-hidden"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#252525] shrink-0 gap-2">
          {task ? (
            <button
              onClick={handleDelete}
              className={`text-xs transition-colors ${confirmDelete ? 'text-red-400 font-medium' : 'text-[#666] hover:text-red-400'}`}
            >
              {confirmDelete ? 'Подтвердить удаление' : 'Удалить'}
            </button>
          ) : (
            <div />
          )}

          <div className="flex items-center gap-2">
            {task && task.slot !== 'now' && (
              <button
                onClick={handleTakeNow}
                className="px-3 py-1.5 bg-[#252525] hover:bg-[#383838] rounded text-xs text-[#f0f0f0] transition-colors"
              >
                Взять сейчас
              </button>
            )}
            {onMarkDone && (
              <button
                onClick={onMarkDone}
                className="px-3 py-1.5 bg-[#1c1c1c] border border-[#252525] hover:border-[#5060a0] hover:text-[#8090c8] rounded text-xs text-[#666] transition-colors"
              >
                ✓ Готово
              </button>
            )}
            <button
              onClick={handleSave}
              disabled={saving || !title.trim()}
              className="px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-50 rounded text-xs text-white transition-colors"
            >
              {saving ? 'Сохраняю…' : 'Сохранить'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
