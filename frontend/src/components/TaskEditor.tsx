import { useState, useEffect, useRef, useCallback } from 'react'
import type { Task, Direction } from '../types'
import { api } from '../api'
import { playSound } from '../sound'
import { getQuadrant, computeUrgency, computeMatrixSlot } from '../utils/quadrant'

interface Props {
  task: Task | null
  directions: Direction[]
  onClose: () => void
  onSaved: () => void
  onDeleted: () => void
  onTakenNow: () => void
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

export default function TaskEditor({ task, directions, onClose, onSaved, onDeleted, onTakenNow }: Props) {
  const [title, setTitle] = useState(task?.title ?? '')
  const [directionId, setDirectionId] = useState<number | null>(task?.direction_id ?? null)
  const [isImportant, setIsImportant] = useState(task?.is_important ?? 0)
  const [isSomeday, setIsSomeday] = useState(task?.slot === 'someday')
  const [deadline, setDeadline] = useState(task?.deadline?.slice(0, 10) ?? '')
  const [durationPlan, setDurationPlan] = useState<string>(task?.duration_plan?.toString() ?? '')
  const [notes, setNotes] = useState(task?.notes ?? '')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [aiSuggestions, setAiSuggestions] = useState<string[]>([])
  const [aiError, setAiError] = useState('')
  const titleRef = useRef<HTMLTextAreaElement>(null)

  const computedUrgency = computeUrgency(deadline)

  const isDirty = useCallback(() => {
    return (
      title !== (task?.title ?? '') ||
      directionId !== (task?.direction_id ?? null) ||
      isImportant !== (task?.is_important ?? 0) ||
      isSomeday !== (task?.slot === 'someday') ||
      deadline !== (task?.deadline?.slice(0, 10) ?? '') ||
      durationPlan !== (task?.duration_plan?.toString() ?? '') ||
      notes !== (task?.notes ?? '')
    )
  }, [title, directionId, isImportant, isSomeday, deadline, durationPlan, notes, task])

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

  const handleSave = async () => {
    if (!title.trim()) return
    setSaving(true)
    try {
      const urgent = computeUrgency(deadline)
      const slot = task?.slot === 'now' ? 'now' : (isSomeday ? 'someday' : computeMatrixSlot(isImportant, urgent))
      const data: Partial<Task> = {
        title: title.trim(),
        direction_id: directionId,
        is_important: isImportant,
        is_urgent: urgent,
        slot,
        deadline: deadline || null,
        duration_plan: durationPlan ? parseFloat(durationPlan) : null,
        notes: notes || null,
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

  const q = getQuadrant(isImportant, computedUrgency)

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
            {/* AI suggestions */}
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

          {/* Eisenhower — only Важно; Срочно is auto-computed */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-2">Приоритет</label>
            <div className="flex items-center gap-4 mb-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" checked={!!isImportant} onChange={e => setIsImportant(e.target.checked ? 1 : 0)}
                  className="accent-[#5060a0] w-4 h-4" />
                <span className="text-sm text-[#f0f0f0]">Важно</span>
              </label>
              <span className="text-xs text-[#666]">
                Срочно: <span className={computedUrgency ? 'text-[#b05050]' : 'text-[#505050]'}>
                  {computedUrgency ? 'да (из дедлайна)' : 'нет'}
                </span>
              </span>
            </div>
            <span className="text-xs px-2 py-0.5 rounded" style={{ color: q.color, backgroundColor: q.border + '40' }}>{q.label}</span>
          </div>

          {/* Someday toggle (replaces slot selector) */}
          {task?.slot !== 'now' && (
            <div>
              <label className="flex items-center gap-2 cursor-pointer w-fit">
                <input type="checkbox" checked={isSomeday} onChange={e => setIsSomeday(e.target.checked)}
                  className="accent-[#5060a0] w-4 h-4" />
                <span className="text-sm text-[#999]">Когда-нибудь</span>
              </label>
              {!isSomeday && (
                <p className="text-[10px] text-[#505050] mt-1">
                  Слот определяется автоматически из важности и дедлайна
                </p>
              )}
            </div>
          )}

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

          {/* Notes */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Заметки</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Детали, ссылки, мысли…"
              rows={4}
              className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838]"
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
