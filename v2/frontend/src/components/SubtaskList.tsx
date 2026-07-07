// Список шагов задачи (микро-подходы). Используется в редакторе задачи и в блоке «Сейчас».
// Прогресс-бар вверху даёт видимое ощущение продвижения по частям.
import { useState, useEffect, useCallback } from 'react'
import type { Subtask } from '../types'
import { api } from '../api'

interface Props {
  taskId: number
  compact?: boolean
  // Скрыть поле «Разбить на шаг…» (например, на карточке миссии — там только просмотр/отметка)
  hideAdd?: boolean
  // Если задан — рядом с невыполненным шагом появляется «▶» для запуска таймера на этот шаг
  onFocusStep?: (subtask: Subtask) => void
  onChanged?: () => void
}

export default function SubtaskList({ taskId, compact, hideAdd, onFocusStep, onChanged }: Props) {
  const [subs, setSubs] = useState<Subtask[]>([])
  const [newTitle, setNewTitle] = useState('')

  const load = useCallback(() => {
    api.getSubtasks(taskId).then(s => setSubs(s as Subtask[])).catch(() => {})
  }, [taskId])
  useEffect(() => { load() }, [load])

  const add = async () => {
    const t = newTitle.trim()
    if (!t) return
    try {
      await api.createSubtask(taskId, t)   // очищаем поле только при успехе
      setNewTitle('')
      load(); onChanged?.()
    } catch (e) { console.error('createSubtask failed', e) }
  }
  const toggle = async (s: Subtask) => {
    await api.updateSubtask(s.id, { done: !s.done_at }).catch(() => {})
    load(); onChanged?.()
  }
  const remove = async (s: Subtask) => {
    await api.deleteSubtask(s.id).catch(() => {})
    load(); onChanged?.()
  }

  const done = subs.filter(s => s.done_at).length
  const pct = subs.length ? Math.round((done / subs.length) * 100) : 0

  return (
    <div className={compact ? '' : 'mt-1'}>
      {subs.length > 0 && (
        <div className="flex items-center gap-2 mb-2">
          <div className="flex-1 h-1.5 bg-[#2a2723] rounded-full overflow-hidden">
            <div className="h-full bg-[#82a877] transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <span className="text-[10px] text-[#9c958a] tabular-nums shrink-0">{done}/{subs.length}</span>
        </div>
      )}

      <ul className="space-y-1">
        {subs.map(s => (
          <li key={s.id} className="group flex items-center gap-2 text-sm">
            <button
              onClick={() => toggle(s)}
              className={`w-4 h-4 rounded border shrink-0 flex items-center justify-center text-[10px] transition-colors ${
                s.done_at ? 'bg-[#82a877] border-[#82a877] text-white' : 'border-[#453f37] hover:border-[#82a877]'
              }`}
            >{s.done_at ? '✓' : ''}</button>
            <span className={`flex-1 ${s.done_at ? 'text-[#9c958a] line-through decoration-[#453f37]' : 'text-[#ddd6cb]'}`}>{s.title}</span>
            {!s.done_at && onFocusStep && (
              <button
                onClick={() => onFocusStep(s)}
                className="opacity-0 group-hover:opacity-100 text-[10px] text-[#d89a4e] hover:text-[#eab26c] shrink-0 transition-opacity"
                title="Запустить таймер на этот шаг"
              >▶ подход</button>
            )}
            <button
              onClick={() => remove(s)}
              className="opacity-0 group-hover:opacity-100 text-[#6f695f] hover:text-[#c05555] text-sm shrink-0 transition-opacity"
              title="Удалить шаг"
            >×</button>
          </li>
        ))}
      </ul>

      {!hideAdd && (
        <div className="flex items-center gap-2 mt-2">
          <span className="text-[#453f37] text-sm shrink-0">+</span>
          <input
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') add() }}
            placeholder="Разбить на шаг…"
            className="flex-1 bg-transparent border-b border-[#2a2a2a] focus:border-[#e0a458] text-sm text-[#ddd6cb] placeholder-[#453f37] focus:outline-none py-0.5"
          />
        </div>
      )}
    </div>
  )
}
