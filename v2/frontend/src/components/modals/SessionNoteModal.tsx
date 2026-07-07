import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'

interface Props {
  sessionId: number
  intent?: string
  subtaskId?: number | null
  onClose: () => void
}

export default function SessionNoteModal({ sessionId, intent, subtaskId, onClose }: Props) {
  const [achieved, setAchieved] = useState<boolean | null>(null)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)
  const closedRef = useRef(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    setTimeout(() => textareaRef.current?.focus(), 50)
  }, [achieved])

  // Сохраняем всё, что есть (намерение + результат + заметку), при ЛЮБОМ закрытии —
  // чтобы сессия не пропадала бесследно, даже если нажать «Пропустить» или Esc.
  const finish = async () => {
    if (closedRef.current) return
    closedRef.current = true
    setSaving(true)
    try {
      const parts: string[] = []
      if (intent) parts.push(`→ ${intent}`)
      if (achieved !== null) parts.push(achieved ? '✓ Выполнено' : '✗ Не до конца')
      if (note.trim()) parts.push(note.trim())
      if (parts.length > 0) await api.updateSessionNote(sessionId, parts.join('\n'))
      // Шаг выполнен → отмечаем подзадачу закрытой
      if (achieved === true && subtaskId != null) {
        await api.updateSubtask(subtaskId, { done: true }).catch(() => {})
      }
      // Обновляем «Нить дня» и прогресс — чтобы заметка/шаг сразу были видны
      window.dispatchEvent(new CustomEvent('gamification-updated'))
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
      onClose()
    }
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') finish()
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') finish()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [note, achieved])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={finish} />
      <div className="relative z-10 animate-scale-in bg-overlay border border-border-strong rounded-2xl p-5 w-[360px] shadow-2xl"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>

        {intent && (
          <div className="bg-[#0f0e0d] rounded-xl px-3 py-2 mb-4">
            <span className="text-[10px] text-[#6f695f] uppercase tracking-widest font-semibold">Намерение</span>
            <p className="text-sm text-[#b5aea1] mt-0.5">{intent}</p>
          </div>
        )}

        {intent && achieved === null && (
          <>
            <p className="text-sm font-semibold text-[#ece7df] mb-3">Удалось выполнить?</p>
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setAchieved(true)}
                className="flex-1 py-2.5 bg-[#20281d] hover:bg-[#2a4a2a] border border-[#5f7f58]/40 rounded-xl text-sm text-[#93b989] transition-colors"
              >✓ Да, сделал</button>
              <button
                onClick={() => setAchieved(false)}
                className="flex-1 py-2.5 bg-[#0f0e0d] hover:bg-[#191817] border border-[#4a463f] rounded-xl text-sm text-[#9c958a] transition-colors"
              >Не до конца</button>
            </div>
            {subtaskId != null && <p className="text-[10px] text-[#6f695f] mb-1 text-center">«Да, сделал» отметит шаг выполненным</p>}
          </>
        )}

        {(!intent || achieved !== null) && (
          <>
            <p className="text-sm font-semibold text-[#ece7df] mb-1">Заметка о сессии</p>
            <p className="text-[11px] text-[#6f695f] mb-3">Необязательно</p>
            <div className="flex flex-wrap gap-2 mb-3">
              {['Доделал', 'Застрял здесь', 'Переключился'].map(chip => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => setNote(n => n.trim() ? `${n.trim()} · ${chip}` : chip)}
                  className="px-3 py-1.5 bg-[#0f0e0d] hover:bg-[#191817] border border-[#2a2723] hover:border-[#e0a458] rounded-full text-xs text-[#b5aea1] transition-colors"
                >{chip}</button>
              ))}
            </div>
            <textarea
              ref={textareaRef}
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Что сделал, что осталось…"
              rows={3}
              className="w-full bg-[#0f0e0d] border border-[#2a2723] rounded-xl px-3 py-2 text-sm text-[#ece7df] focus:outline-none focus:border-[#e0a458] resize-none placeholder-[#4a463f] mb-4"
            />
            <div className="flex justify-between items-center">
              <button onClick={finish} className="text-xs text-[#9c958a] hover:text-[#ece7df] transition-colors">Пропустить</button>
              <button
                onClick={finish}
                disabled={saving}
                className="px-4 py-1.5 bg-accent hover:bg-accent-light disabled:opacity-50 rounded-lg text-xs text-[#1c1610] font-medium transition-colors"
              >{saving ? 'Сохраняю…' : 'Сохранить'}</button>
            </div>
            <p className="text-[10px] text-[#4a463f] mt-2 text-right">⌘↩ · Esc — тоже сохранит</p>
          </>
        )}
      </div>
    </div>
  )
}
