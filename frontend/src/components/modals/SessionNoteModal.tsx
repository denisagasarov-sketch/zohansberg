import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'

interface Props {
  sessionId: number
  intent?: string
  onClose: () => void
}

export default function SessionNoteModal({ sessionId, intent, onClose }: Props) {
  const [achieved, setAchieved] = useState<boolean | null>(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [achieved])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [note])

  const handleSave = async () => {
    setSaving(true)
    try {
      const parts: string[] = []
      if (intent) parts.push(`→ ${intent}`)
      if (achieved !== null) parts.push(achieved ? '✓ Выполнено' : '✗ Не до конца')
      if (note.trim()) parts.push(note.trim())
      if (parts.length > 0) await api.updateSessionNote(sessionId, parts.join('\n'))
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl p-5 w-[360px] shadow-2xl"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>

        {intent && (
          <div className="bg-[#141414] rounded-xl px-3 py-2 mb-4">
            <span className="text-[10px] text-[#555] uppercase tracking-widest font-semibold">Намерение</span>
            <p className="text-sm text-[#c0c0c0] mt-0.5">{intent}</p>
          </div>
        )}

        {intent && achieved === null && (
          <>
            <p className="text-sm font-semibold text-[#f0f0f0] mb-3">Удалось выполнить?</p>
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setAchieved(true)}
                className="flex-1 py-2.5 bg-[#1a3a1a] hover:bg-[#2a4a2a] border border-[#4a7a4a]/40 rounded-xl text-sm text-[#7ab87a] transition-colors"
              >✓ Да, сделал</button>
              <button
                onClick={() => setAchieved(false)}
                className="flex-1 py-2.5 bg-[#141414] hover:bg-[#1a1a1a] border border-[#383838] rounded-xl text-sm text-[#666] transition-colors"
              >Не до конца</button>
            </div>
          </>
        )}

        {(!intent || achieved !== null) && (
          <>
            <p className="text-sm font-semibold text-[#f0f0f0] mb-1">Заметка о сессии</p>
            <p className="text-[11px] text-[#555] mb-3">Необязательно</p>
            <textarea
              ref={textareaRef}
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Что сделал, что осталось…"
              rows={3}
              className="w-full bg-[#141414] border border-[#252525] rounded-xl px-3 py-2 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838] mb-4"
            />
            <div className="flex justify-between items-center">
              <button onClick={onClose} className="text-xs text-[#666] hover:text-[#f0f0f0] transition-colors">Пропустить</button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-50 rounded-lg text-xs text-white transition-colors"
              >{saving ? 'Сохраняю…' : 'Сохранить'}</button>
            </div>
            <p className="text-[10px] text-[#383838] mt-2 text-right">⌘↩ · Esc пропустить</p>
          </>
        )}
      </div>
    </div>
  )
}
