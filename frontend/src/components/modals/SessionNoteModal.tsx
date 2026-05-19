import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'

interface Props {
  sessionId: number
  onClose: () => void
}

export default function SessionNoteModal({ sessionId, onClose }: Props) {
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleSave()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [note])

  const handleSave = async () => {
    if (!note.trim()) { onClose(); return }
    setSaving(true)
    try {
      await api.updateSessionNote(sessionId, note.trim())
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
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-xl p-5 w-[340px] shadow-2xl">
        <p className="text-sm font-semibold text-[#f0f0f0] mb-1">Что сделал за эту сессию?</p>
        <p className="text-[11px] text-[#555] mb-3">Необязательно — поможет вспомнить прогресс</p>
        <textarea
          ref={textareaRef}
          value={note}
          onChange={e => setNote(e.target.value)}
          placeholder="Описал архитектуру, написал тесты…"
          rows={3}
          className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838] mb-3"
        />
        <div className="flex justify-between items-center">
          <button onClick={onClose} className="text-xs text-[#666] hover:text-[#f0f0f0] transition-colors">Пропустить</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-50 rounded text-xs text-white transition-colors"
          >
            {saving ? 'Сохраняю…' : 'Сохранить'}
          </button>
        </div>
        <p className="text-[10px] text-[#383838] mt-2 text-right">⌘↩ сохранить · Esc пропустить</p>
      </div>
    </div>
  )
}
