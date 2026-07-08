import { useState, useRef, useEffect } from 'react'
import type { Subtask } from '../../types'
import { api } from '../../api'

interface Props {
  taskId: number
  taskTitle: string
  onStart: (intent: string, subtaskId: number | null) => void
  onCancel: () => void
}

export default function SessionIntentModal({ taskId, taskTitle, onStart, onCancel }: Props) {
  const [intent, setIntent] = useState('')
  const [subtaskId, setSubtaskId] = useState<number | null>(null)
  const [steps, setSteps] = useState<Subtask[]>([])
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])
  // Escape закрывает БЕЗ запуска таймера (как «Назад» и клик мимо).
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); onCancel() } }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onCancel])
  useEffect(() => {
    api.getSubtasks(taskId)
      .then(s => {
        const open = (s as Subtask[]).filter(x => !x.done_at)
        setSteps(open)
        // Авто-выбор первого незакрытого шага как намерения: тогда «Да, сделал»
        // в конце сессии сразу закроет именно его. Можно снять тапом или вписать своё.
        if (open.length > 0) { setSubtaskId(open[0].id); setIntent(open[0].title) }
      })
      .catch(() => {})
  }, [taskId])

  const pickStep = (s: Subtask) => {
    if (subtaskId === s.id) { setSubtaskId(null); setIntent('') }   // повторный тап снимает выбор
    else { setSubtaskId(s.id); setIntent(s.title) }
  }

  const handleStart = () => onStart(intent.trim(), subtaskId)

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-[4px]" onClick={onCancel} />
      <div className="relative z-10 animate-scale-in bg-overlay border border-border-strong rounded-2xl w-full max-w-sm shadow-2xl p-5"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>
        <button onClick={onCancel} title="Назад (Esc) — без запуска таймера"
          className="absolute top-3 right-3 text-[#6f695f] hover:text-[#ece7df] transition-colors text-lg leading-none">×</button>
        <div className="text-[10px] font-semibold tracking-widest text-[#e0a458] uppercase mb-1">Намерение сессии</div>
        <p className="text-xs text-[#6f695f] mb-4 truncate pr-6">{taskTitle}</p>

        {/* Выбор шага: тап по подзадаче делает её намерением сессии */}
        {steps.length > 0 && (
          <div className="mb-3">
            <div className="text-[10px] uppercase tracking-widest text-[#6f695f] mb-2">Взять шаг</div>
            <div className="flex flex-col gap-1.5 max-h-40 overflow-y-auto">
              {steps.map(s => {
                const on = subtaskId === s.id
                return (
                  <div key={s.id}
                    className={`flex items-center gap-2 rounded-lg pl-3 pr-1.5 py-2 text-sm transition-colors border
                      ${on ? 'bg-accent/15 border-accent/50 text-[#ece7df]' : 'bg-[#0f0e0d] border-[#2a2723] text-[#b5aea1] hover:border-accent/40'}`}>
                    <button onClick={() => pickStep(s)} className="flex items-center gap-2 text-left flex-1 min-w-0">
                      <span className={`w-3.5 h-3.5 rounded-full border shrink-0 flex items-center justify-center text-[9px] ${on ? 'bg-accent border-accent text-[#1c1610]' : 'border-[#4a463f]'}`}>{on ? '✓' : ''}</span>
                      <span className="flex-1 truncate">{s.title}</span>
                    </button>
                    <button
                      onClick={e => { e.stopPropagation(); onStart(s.title, s.id) }}
                      title="Начать с этого шага"
                      className="shrink-0 w-6 h-6 rounded-md flex items-center justify-center text-xs bg-accent hover:bg-accent-light text-[#1c1610] transition-colors">
                      ▶
                    </button>
                  </div>
                )
              })}
            </div>
            <div className="text-[10px] text-[#4a463f] mt-2">или впиши своё:</div>
          </div>
        )}

        <input
          ref={inputRef}
          value={intent}
          onChange={e => { setIntent(e.target.value); setSubtaskId(null) }}
          onKeyDown={e => { if (e.key === 'Enter') handleStart(); if (e.key === 'Escape') { e.preventDefault(); onCancel() } }}
          placeholder="Что конкретно сделаешь?"
          className="w-full bg-[#0f0e0d] border border-[#2a2723] rounded-xl px-4 py-3 text-sm text-[#ece7df] placeholder-[#4a463f] focus:outline-none focus:border-[#e0a458] mb-4"
        />

        <div className="flex gap-2">
          <button onClick={onCancel}
            className="flex-1 py-2.5 bg-raised hover:bg-border-strong rounded-xl text-sm text-[#9c958a] transition-colors">
            ← Назад
          </button>
          <button onClick={handleStart}
            className="flex-1 py-2.5 bg-accent hover:bg-accent-light rounded-xl text-sm text-[#1c1610] font-medium transition-colors">
            Начать ▶
          </button>
        </div>
        <p className="text-[10px] text-[#4a463f] mt-2.5 text-center">пустое поле = старт без намерения · Esc / клик мимо — назад</p>
      </div>
    </div>
  )
}
