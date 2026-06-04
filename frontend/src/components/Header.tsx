import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api'
import type { Screen } from '../types'

interface Props {
  onNavigate: (screen: Screen) => void
  onTaskCreated: () => void
  onOpenEditor: (taskId: number) => void
  onEndDay: () => void
  onStandup: () => void
  isTimerActive?: boolean
}

function padZ(n: number) { return String(n).padStart(2, '0') }

function formatDateTime() {
  const now = new Date()
  const days = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  return `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} · ${padZ(now.getHours())}:${padZ(now.getMinutes())}`
}

export default function Header({ onNavigate, onTaskCreated, onOpenEditor, onEndDay, onStandup, isTimerActive }: Props) {
  const [inputValue, setInputValue] = useState('')
  const [pendingText, setPendingText] = useState('')
  const [showTypeDropdown, setShowTypeDropdown] = useState(false)
  const [thoughtSaved, setThoughtSaved] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [datetime, setDatetime] = useState(formatDateTime())
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const id = setInterval(() => setDatetime(formatDateTime()), 60_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && inputValue.trim()) {
      setPendingText(inputValue.trim())
      setShowTypeDropdown(true)
    }
    if (e.key === 'Escape') {
      setInputValue('')
      setShowTypeDropdown(false)
      inputRef.current?.blur()
    }
  }

  const handleTask = useCallback(async () => {
    try {
      const task = await api.createTask({ title: pendingText, slot: 'queue' }) as { id: number }
      onTaskCreated()
      onOpenEditor(task.id)
    } catch (e) {
      console.error(e)
    }
    setInputValue('')
    setShowTypeDropdown(false)
    setPendingText('')
  }, [pendingText, onTaskCreated, onOpenEditor])

  const handleThought = useCallback(async () => {
    try {
      await api.createJournalEntry({ type: 'thought', content: pendingText })
      window.dispatchEvent(new CustomEvent('journal-updated'))
      setThoughtSaved(true)
      setTimeout(() => setThoughtSaved(false), 2000)
    } catch (e) {
      console.error(e)
    }
    setInputValue('')
    setShowTypeDropdown(false)
    setPendingText('')
  }, [pendingText])

  const handleSmartTask = useCallback(async () => {
    if (!pendingText) return
    setParsing(true)
    setShowTypeDropdown(false)
    try {
      const parsed = await api.parseTask(pendingText)
      const task = await api.createTask({
        title: parsed.title ?? pendingText,
        direction_id: parsed.direction_id ?? null,
        deadline: parsed.deadline ?? null,
        duration_plan: parsed.duration_plan ?? null,
        slot: 'queue',
      }) as { id: number }
      onTaskCreated()
      onOpenEditor(task.id)
    } catch (e) {
      console.error(e)
      // Fallback: create plain task
      try {
        const task = await api.createTask({ title: pendingText, slot: 'queue' }) as { id: number }
        onTaskCreated()
        onOpenEditor(task.id)
      } catch {}
    } finally {
      setParsing(false)
    }
    setInputValue('')
    setPendingText('')
  }, [pendingText, onTaskCreated, onOpenEditor])

  const cancelAll = useCallback(() => {
    setInputValue('')
    setShowTypeDropdown(false)
    setPendingText('')
  }, [])

  return (
    <header className="h-10 bg-[#141414] border-b border-[#252525] flex items-center px-4 gap-4 shrink-0">
      <div className="relative flex-1 max-w-xs">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Быстрый ввод… (⌘N)"
          className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0] h-7"
        />
        {thoughtSaved && (
          <div className="absolute top-8 left-0 z-50 bg-[#1c1c1c] border border-[#5060a0]/50 rounded px-3 py-1.5 text-xs text-[#8090c8] shadow-lg whitespace-nowrap">
            ✓ Мысль записана
          </div>
        )}
        {parsing && (
          <div className="absolute top-8 left-0 z-50 bg-[#1c1c1c] border border-[#252525] rounded px-3 py-1.5 text-xs text-[#8090c8] shadow-lg whitespace-nowrap">
            ✨ Разбираю…
          </div>
        )}
        {showTypeDropdown && (
          <div className="absolute top-8 left-0 z-50 bg-[#1c1c1c] border border-[#252525] rounded p-2 w-max text-sm shadow-lg">
            <div className="text-[#666] mb-2 truncate max-w-xs">&ldquo;{pendingText}&rdquo;</div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[#666] text-xs">Это:</span>
              <button onClick={handleSmartTask} className="px-2 py-1 bg-[#252525] rounded hover:bg-[#5060a0] transition-colors text-xs">✨ Умная задача</button>
              <button onClick={handleTask} className="px-2 py-1 bg-[#252525] rounded hover:bg-[#383838] transition-colors text-xs text-[#999]">📋 Просто задача</button>
              <button onClick={handleThought} className="px-2 py-1 bg-[#252525] rounded hover:bg-[#5060a0] transition-colors text-xs">💭 Мысль</button>
              <span className="text-[#383838] text-xs">Esc — отмена</span>
            </div>
          </div>
        )}
      </div>

      {isTimerActive && (
        <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#5060a0]/20 border border-[#5060a0]/40 text-[#8090c8] text-xs shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-[#5060a0] animate-pulse inline-block" />
          Режим фокуса
        </div>
      )}

      <div className="flex-1 text-center text-[#666] text-xs tabular-nums select-none">{datetime}</div>

      <nav className="flex items-center gap-1">
        <button onClick={onEndDay} title="Завершить день" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">🌆</button>
        <button onClick={onStandup} title="Стендап" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">🗣</button>
        <button onClick={() => onNavigate('horizon')} title="Горизонт" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">🗓</button>
        <button onClick={() => onNavigate('journal')} title="Дневник" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">📓</button>
        <button onClick={() => onNavigate('stats')} title="Статистика" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">📊</button>
        <button onClick={() => onNavigate('archive')} title="Архив" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">📦</button>
        <button onClick={() => onNavigate('settings')} title="Настройки" className="w-7 h-7 flex items-center justify-center rounded hover:bg-[#252525] text-base transition-colors">⚙️</button>
      </nav>
    </header>
  )
}
