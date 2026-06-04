import { useState, useRef, useEffect } from 'react'

interface Props {
  taskTitle: string
  onStart: (intent: string) => void
  onSkip: () => void
}

export default function SessionIntentModal({ taskTitle, onStart, onSkip }: Props) {
  const [intent, setIntent] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleStart = () => onStart(intent.trim())

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60" onClick={onSkip} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-sm shadow-2xl p-5"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>
        <div className="text-[10px] font-semibold tracking-widest text-[#5060a0] uppercase mb-1">Намерение сессии</div>
        <p className="text-xs text-[#555] mb-4 truncate">{taskTitle}</p>

        <input
          ref={inputRef}
          value={intent}
          onChange={e => setIntent(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleStart(); if (e.key === 'Escape') onSkip() }}
          placeholder="Что конкретно сделаешь?"
          className="w-full bg-[#141414] border border-[#252525] rounded-xl px-4 py-3 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0] mb-4"
        />

        <div className="flex gap-2">
          <button onClick={onSkip}
            className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
            Пропустить
          </button>
          <button onClick={handleStart}
            className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white font-medium transition-colors">
            Начать ▶
          </button>
        </div>
      </div>
    </div>
  )
}
