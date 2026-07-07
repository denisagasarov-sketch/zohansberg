import { useState, useEffect } from 'react'
import { api } from '../../api'

interface Props {
  taskId: number
  taskTitle: string
  onClose: () => void
}

const QUICK_MINUTES = [15, 30, 45, 60, 90] as const

export default function CreditWorkModal({ taskId, taskTitle, onClose }: Props) {
  const [manual, setManual] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const credit = async (minutes: number) => {
    if (saving || minutes <= 0) return
    setSaving(true)
    try {
      const now = new Date()
      const started = new Date(now.getTime() - minutes * 60_000)
      await api.createManualSession(taskId, {
        started_at: started.toISOString(),
        ended_at: now.toISOString(),
        duration_seconds: minutes * 60,
      })
      window.dispatchEvent(new CustomEvent('gamification-updated'))
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
      onClose()
    }
  }

  const submitManual = () => {
    const m = Math.round(Number(manual))
    if (Number.isFinite(m) && m > 0) credit(m)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 bg-overlay border border-border-strong rounded-2xl p-5 w-[360px] shadow-2xl"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>

        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[#6f695f] hover:text-[#ece7df] transition-colors text-lg leading-none"
          aria-label="Закрыть"
        >✕</button>

        <p className="text-sm font-semibold text-[#ece7df] mb-1 pr-6">Сколько примерно заняло?</p>
        <p className="text-sm text-[#b5aea1] truncate">{taskTitle}</p>
        <p className="text-[11px] text-[#6f695f] mb-4 mt-0.5">Ты отметил задачу готовой — зачтём время в фокус</p>

        <div className="flex flex-wrap gap-2 mb-4">
          {QUICK_MINUTES.map(min => (
            <button
              key={min}
              type="button"
              disabled={saving}
              onClick={() => credit(min)}
              className="px-3.5 py-2 bg-[#0f0e0d] hover:bg-[#191817] border border-[#2a2723] hover:border-[#e0a458] disabled:opacity-50 rounded-full text-xs text-[#b5aea1] transition-colors"
            >{min} мин</button>
          ))}
        </div>

        <div className="flex gap-2 items-center mb-1">
          <input
            type="number"
            min={1}
            value={manual}
            onChange={e => setManual(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submitManual() }}
            placeholder="Минут"
            className="flex-1 bg-[#0f0e0d] border border-[#2a2723] rounded-xl px-3 py-2 text-sm text-[#ece7df] focus:outline-none focus:border-[#e0a458] placeholder-[#4a463f]"
          />
          <button
            onClick={submitManual}
            disabled={saving || !manual.trim()}
            className="px-4 py-2 bg-accent hover:bg-accent-light disabled:opacity-50 rounded-lg text-xs text-[#1c1610] font-medium transition-colors"
          >Записать</button>
        </div>

        <div className="flex justify-start mt-3">
          <button onClick={onClose} className="text-xs text-[#9c958a] hover:text-[#ece7df] transition-colors">Не надо</button>
        </div>
      </div>
    </div>
  )
}
