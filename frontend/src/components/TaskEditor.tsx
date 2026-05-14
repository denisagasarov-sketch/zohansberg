import { useState, useEffect, useRef, useCallback } from 'react'
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
}

type Priority = 'high' | 'medium' | 'low'
type Status = 'todo' | 'in_progress' | 'done' | 'frozen'
type Slot = 'next' | 'later' | 'someday'

function Btn({ active, onClick, children, cls = '' }: { active: boolean; onClick: () => void; children: React.ReactNode; cls?: string }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 rounded text-xs transition-colors border ${
        active
          ? 'bg-[#5060a0] border-[#5060a0] text-white'
          : `bg-transparent border-[#252525] text-[#666] hover:border-[#5060a0]/50 ${cls}`
      }`}
    >
      {children}
    </button>
  )
}

export default function TaskEditor({ task, directions, onClose, onSaved, onDeleted, onTakenNow }: Props) {
  const [title, setTitle] = useState(task?.title ?? '')
  const [directionId, setDirectionId] = useState<number | null>(task?.direction_id ?? null)
  const [priority, setPriority] = useState<Priority>(task?.priority ?? 'medium')
  const [status, setStatus] = useState<Status>(task?.status ?? 'todo')
  const [slot, setSlot] = useState<Slot>((task?.slot === 'now' ? 'next' : task?.slot) as Slot ?? 'later')
  const [deadline, setDeadline] = useState(task?.deadline?.slice(0, 10) ?? '')
  const [durationPlan, setDurationPlan] = useState<string>(task?.duration_plan?.toString() ?? '')
  const [notes, setNotes] = useState(task?.notes ?? '')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const titleRef = useRef<HTMLTextAreaElement>(null)

  const isDirty = useCallback(() => {
    return (
      title !== (task?.title ?? '') ||
      directionId !== (task?.direction_id ?? null) ||
      priority !== (task?.priority ?? 'medium') ||
      status !== (task?.status ?? 'todo') ||
      slot !== ((task?.slot === 'now' ? 'next' : task?.slot) ?? 'later') ||
      deadline !== (task?.deadline?.slice(0, 10) ?? '') ||
      durationPlan !== (task?.duration_plan?.toString() ?? '') ||
      notes !== (task?.notes ?? '')
    )
  }, [title, directionId, priority, status, slot, deadline, durationPlan, notes, task])

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
      const data: Partial<Task> = {
        title: title.trim(),
        direction_id: directionId,
        priority,
        status,
        slot: task?.slot === 'now' ? 'now' : slot,
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
          {/* Title */}
          <textarea
            ref={titleRef}
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Название задачи"
            rows={2}
            className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838]"
          />

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

          {/* Priority */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Приоритет</label>
            <div className="flex gap-1.5">
              <Btn active={priority === 'high'} onClick={() => setPriority('high')} cls="text-[#b07070]">Высокий</Btn>
              <Btn active={priority === 'medium'} onClick={() => setPriority('medium')} cls="text-[#a08850]">Средний</Btn>
              <Btn active={priority === 'low'} onClick={() => setPriority('low')} cls="text-[#555]">Низкий</Btn>
            </div>
          </div>

          {/* Status */}
          <div>
            <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Статус</label>
            <div className="flex flex-wrap gap-1.5">
              <Btn active={status === 'todo'} onClick={() => setStatus('todo')}>Не начата</Btn>
              <Btn active={status === 'in_progress'} onClick={() => setStatus('in_progress')}>В работе</Btn>
              <Btn active={status === 'done'} onClick={() => setStatus('done')}>Готово</Btn>
              <Btn active={status === 'frozen'} onClick={() => setStatus('frozen')}>Заморожена</Btn>
            </div>
          </div>

          {/* Slot */}
          {task?.slot !== 'now' && (
            <div>
              <label className="block text-[10px] text-[#666] uppercase tracking-wider mb-1.5">Слот</label>
              <div className="flex gap-1.5">
                <Btn active={slot === 'next'} onClick={() => setSlot('next')}>Следом</Btn>
                <Btn active={slot === 'later'} onClick={() => setSlot('later')}>Позже</Btn>
                <Btn active={slot === 'someday'} onClick={() => setSlot('someday')}>Когда-нибудь</Btn>
              </div>
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
