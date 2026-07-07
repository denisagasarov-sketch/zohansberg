// Список шагов задачи (микро-подходы). Используется в редакторе задачи и в блоке «Сейчас».
// Прогресс-бар вверху даёт видимое ощущение продвижения по частям.
import { useState, useEffect, useCallback } from 'react'
import type { Subtask } from '../types'
import { api } from '../api'

interface Props {
  taskId: number
  compact?: boolean
  // Если задан — рядом с невыполненным шагом появляется «▶» для запуска таймера на этот шаг
  onFocusStep?: (subtask: Subtask) => void
  onChanged?: () => void
}

export default function SubtaskList({ taskId, compact, onFocusStep, onChanged }: Props) {
  const [subs, setSubs] = useState<Subtask[]>([])
  const [newTitle, setNewTitle] = useState('')

  const load = useCallback(() => {
    api.getSubtasks(taskId).then(s => setSubs(s as Subtask[])).catch(() => {})
  }, [taskId])
  useEffect(() => { load() }, [load])

  const add = async () => {
    const t = newTitle.trim()
    if (!t) return
    setNewTitle('')
    await api.createSubtask(taskId, t).catch(() => {})
    load(); onChanged?.()
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
          <div className="flex-1 h-1.5 bg-[#252525] rounded-full overflow-hidden">
            <div className="h-full bg-[#4a9d5f] transition-all duration-300" style={{ width: `${pct}%` }} />
          </div>
          <span className="text-[10px] text-[#666] tabular-nums shrink-0">{done}/{subs.length}</span>
        </div>
      )}

      <ul className="space-y-1">
        {subs.map(s => (
          <li key={s.id} className="group flex items-center gap-2 text-sm">
            <button
              onClick={() => toggle(s)}
              className={`w-4 h-4 rounded border shrink-0 flex items-center justify-center text-[10px] transition-colors ${
                s.done_at ? 'bg-[#4a9d5f] border-[#4a9d5f] text-white' : 'border-[#444] hover:border-[#4a9d5f]'
              }`}
            >{s.done_at ? '✓' : ''}</button>
            <span className={`flex-1 ${s.done_at ? 'text-[#666] line-through decoration-[#444]' : 'text-[#e0e0e0]'}`}>{s.title}</span>
            {!s.done_at && onFocusStep && (
              <button
                onClick={() => onFocusStep(s)}
                className="opacity-0 group-hover:opacity-100 text-[10px] text-[#5a6db0] hover:text-[#8090c8] shrink-0 transition-opacity"
                title="Запустить таймер на этот шаг"
              >▶ подход</button>
            )}
            <button
              onClick={() => remove(s)}
              className="opacity-0 group-hover:opacity-100 text-[#555] hover:text-[#c05555] text-sm shrink-0 transition-opacity"
              title="Удалить шаг"
            >×</button>
          </li>
        ))}
      </ul>

      <div className="flex items-center gap-2 mt-2">
        <span className="text-[#444] text-sm shrink-0">+</span>
        <input
          value={newTitle}
          onChange={e => setNewTitle(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') add() }}
          placeholder="Разбить на шаг…"
          className="flex-1 bg-transparent border-b border-[#2a2a2a] focus:border-[#5060a0] text-sm text-[#e0e0e0] placeholder-[#444] focus:outline-none py-0.5"
        />
      </div>
    </div>
  )
}
