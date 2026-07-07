import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api'
import type { Screen } from '../types'
import Icon from './Icon'

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
    <header className="h-11 bg-header/80 backdrop-blur border-b border-border flex items-center px-4 gap-4 shrink-0">
      <div className="relative flex-1 max-w-xs">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Быстрый ввод…   ⌘N"
          className="w-full h-7 bg-bg-sunken border border-border rounded-lg px-2.5 text-[13px] text-text placeholder:text-text-faint outline-none focus:border-accent/60 transition-colors"
        />
        {thoughtSaved && (
          <div className="absolute top-9 left-0 z-50 card-raised px-3 py-1.5 text-xs text-accent-light whitespace-nowrap animate-fade-in">
            ✓ Мысль записана
          </div>
        )}
        {parsing && (
          <div className="absolute top-9 left-0 z-50 card-raised px-3 py-1.5 text-xs text-accent-light whitespace-nowrap animate-fade-in">
            Разбираю…
          </div>
        )}
        {showTypeDropdown && (
          <div className="absolute top-9 left-0 z-50 card-raised p-2.5 w-max text-sm animate-scale-in">
            <div className="text-text-secondary mb-2 truncate max-w-xs text-xs">&ldquo;{pendingText}&rdquo;</div>
            <div className="flex items-center gap-1.5 flex-wrap">
              <button onClick={handleSmartTask} className="px-2.5 py-1 bg-accent/15 text-accent-light rounded-lg hover:bg-accent hover:text-[#1c1610] transition-colors text-xs inline-flex items-center gap-1.5"><Icon name="sparkles" size={13} /> Умная задача</button>
              <button onClick={handleTask} className="px-2.5 py-1 bg-raised rounded-lg hover:bg-border-strong transition-colors text-xs text-text-secondary hover:text-text inline-flex items-center gap-1.5"><Icon name="check" size={13} /> Просто задача</button>
              <button onClick={handleThought} className="px-2.5 py-1 bg-raised rounded-lg hover:bg-border-strong transition-colors text-xs text-text-secondary hover:text-text inline-flex items-center gap-1.5"><Icon name="thought" size={13} /> Мысль</button>
              <span className="text-text-faint text-[11px] pl-1">Esc — отмена</span>
            </div>
          </div>
        )}
      </div>

      {isTimerActive && (
        <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-accent/15 border border-accent/30 text-accent-light text-xs shrink-0">
          <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse inline-block" />
          Фокус
        </div>
      )}

      <div className="flex-1 text-center text-text-muted text-xs tabular-nums select-none">{datetime}</div>

      <nav className="flex items-center gap-0.5 text-[#8d8679]">
        <button onClick={onEndDay} title="Завершить день" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="sunset" /></button>
        <button onClick={onStandup} title="Стендап" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="message" /></button>
        <button onClick={() => onNavigate('weekplan')} title="План недели" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="target" /></button>
        <button onClick={() => onNavigate('journal')} title="Дневник" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="book" /></button>
        <button onClick={() => onNavigate('stats')} title="Статистика" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="chart" /></button>
        <button onClick={() => onNavigate('archive')} title="Архив" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="archive" /></button>
        <button onClick={() => onNavigate('settings')} title="Настройки" className="w-8 h-7 flex items-center justify-center rounded-lg hover:bg-raised hover:text-text transition-colors"><Icon name="settings" /></button>
      </nav>
    </header>
  )
}
