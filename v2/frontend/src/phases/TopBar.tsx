// Верхняя полоса: фазы дня слева, часы в центре, слои и быстрый ввод справа.
import { useState, useEffect, useRef, useCallback } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import type { Phase, Layer } from '../App'

interface Props {
  phase: Phase
  onPhase: (p: Phase) => void
  layer: Layer
  onLayer: (l: Layer) => void
  onStandup: () => void
  onTaskCreated: () => void
  onOpenEditor: (taskId: number) => void
}

function padZ(n: number) { return String(n).padStart(2, '0') }
function formatClock() {
  const now = new Date()
  const days = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  return `${days[now.getDay()]}, ${now.getDate()} ${months[now.getMonth()]} · ${padZ(now.getHours())}:${padZ(now.getMinutes())}`
}

const PHASES: { key: Phase; label: string }[] = [
  { key: 'morning', label: 'Утро' },
  { key: 'day', label: 'День' },
  { key: 'evening', label: 'Вечер' },
]

export default function TopBar({ phase, onPhase, layer, onLayer, onStandup, onTaskCreated, onOpenEditor }: Props) {
  const [clock, setClock] = useState(formatClock())
  const [inputValue, setInputValue] = useState('')
  const [pendingText, setPendingText] = useState('')
  const [showTypeDropdown, setShowTypeDropdown] = useState(false)
  const [thoughtSaved, setThoughtSaved] = useState(false)
  const [parsing, setParsing] = useState(false)
  const [showMore, setShowMore] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const moreRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const id = setInterval(() => setClock(formatClock()), 30_000)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') { e.preventDefault(); inputRef.current?.focus() }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    if (!showMore) return
    const h = (e: MouseEvent) => { if (moreRef.current && !moreRef.current.contains(e.target as Node)) setShowMore(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [showMore])

  const reset = useCallback(() => { setInputValue(''); setShowTypeDropdown(false); setPendingText('') }, [])

  const createSimpleTask = useCallback(async (title: string) => {
    try {
      const task = await api.createTask({ title, slot: 'queue' }) as { id: number }
      onTaskCreated(); onOpenEditor(task.id)
    } catch (e) { console.error(e) }
    reset()
  }, [onTaskCreated, onOpenEditor, reset])

  const handleTask = useCallback(() => createSimpleTask(pendingText), [createSimpleTask, pendingText])

  const handleThought = useCallback(async () => {
    try {
      await api.createJournalEntry({ type: 'thought', content: pendingText })
      window.dispatchEvent(new CustomEvent('journal-updated'))
      setThoughtSaved(true)
      setTimeout(() => setThoughtSaved(false), 2000)
    } catch (e) { console.error(e) }
    reset()
  }, [pendingText, reset])

  const handleSmartTask = useCallback(async () => {
    if (!pendingText) return
    setParsing(true); setShowTypeDropdown(false)
    try {
      const parsed = await api.parseTask(pendingText)
      const task = await api.createTask({
        title: parsed.title ?? pendingText,
        direction_id: parsed.direction_id ?? null,
        deadline: parsed.deadline ?? null,
        duration_plan: parsed.duration_plan ?? null,
        slot: 'queue',
      }) as { id: number }
      onTaskCreated(); onOpenEditor(task.id)
    } catch {
      try {
        const task = await api.createTask({ title: pendingText, slot: 'queue' }) as { id: number }
        onTaskCreated(); onOpenEditor(task.id)
      } catch {}
    } finally { setParsing(false) }
    setInputValue(''); setPendingText('')
  }, [pendingText, onTaskCreated, onOpenEditor])

  const layerBtn = (l: Layer, icon: React.ReactNode, title: string) => (
    <button
      onClick={() => onLayer(layer === l ? null : l)}
      title={title}
      className={`w-8 h-7 flex items-center justify-center rounded-lg transition-colors ${layer === l ? 'bg-accent/15 text-accent-light' : 'hover:bg-raised hover:text-text text-[#8d8679]'}`}
    >{icon}</button>
  )

  return (
    <header className="h-11 bg-header/80 backdrop-blur border-b border-border flex items-center px-4 gap-4 shrink-0 relative z-30">
      {/* Фазы дня */}
      <nav className="flex items-center gap-1 shrink-0">
        {PHASES.map(p => (
          <button
            key={p.key}
            onClick={() => onPhase(p.key)}
            className={`px-2.5 py-1 rounded-lg text-[12px] font-medium transition-colors ${
              phase === p.key ? 'bg-raised text-text' : 'text-text-muted hover:text-text-secondary'
            }`}
          >{p.label}</button>
        ))}
      </nav>

      {/* Быстрый ввод */}
      <div className="relative flex-1 max-w-[260px]">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={e => setInputValue(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && inputValue.trim()) {
              const text = inputValue.trim(); setPendingText(text)
              if (e.shiftKey) setShowTypeDropdown(true)   // Shift+Enter — выбор типа
              else createSimpleTask(text)                 // Enter — сразу «просто задача»
            }
            if (e.key === 'Escape') { reset(); inputRef.current?.blur() }
          }}
          placeholder="Быстрый ввод…   ⌘N · ⇧⏎ тип"
          className="w-full h-7 bg-bg-sunken border border-border rounded-lg px-2.5 text-[13px] text-text placeholder:text-text-faint outline-none focus:border-accent/60 transition-colors"
        />
        {thoughtSaved && (
          <div className="absolute top-9 left-0 z-50 card-raised px-3 py-1.5 text-xs text-accent-light whitespace-nowrap animate-fade-in">✓ Мысль записана</div>
        )}
        {parsing && (
          <div className="absolute top-9 left-0 z-50 card-raised px-3 py-1.5 text-xs text-accent-light whitespace-nowrap animate-fade-in">Разбираю…</div>
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

      <div className="flex-1 text-center text-text-muted text-xs tabular-nums select-none">{clock}</div>

      {/* Слои */}
      <nav className="flex items-center gap-0.5 shrink-0">
        {layerBtn('library', <Icon name="archive" />, 'Библиотека задач (⌘L)')}
        {layerBtn('stats', <Icon name="chart" />, 'Пульс — живая статистика')}
        {layerBtn('journal', <Icon name="book" />, 'Дневник')}
        <div className="relative" ref={moreRef}>
          <button
            onClick={() => setShowMore(v => !v)}
            title="Ещё"
            className={`w-8 h-7 flex items-center justify-center rounded-lg transition-colors ${showMore ? 'bg-raised text-text' : 'hover:bg-raised hover:text-text text-[#8d8679]'}`}
          >⋯</button>
          {showMore && (
            <div className="absolute top-9 right-0 z-50 card-raised py-1 min-w-[180px] animate-scale-in text-[13px]">
              {([
                ['weekplan', 'План недели'],
                ['settings', 'Настройки'],
                ['archive', 'Архив'],
                ['trash', 'Корзина'],
              ] as [Layer, string][]).map(([l, label]) => (
                <button key={l as string} onClick={() => { onLayer(l); setShowMore(false) }} className="w-full text-left px-3 py-1.5 text-text-secondary hover:text-text hover:bg-border-strong transition-colors">{label}</button>
              ))}
              <div className="border-t border-border my-1" />
              <button onClick={() => { onStandup(); setShowMore(false) }} className="w-full text-left px-3 py-1.5 text-text-secondary hover:text-text hover:bg-border-strong transition-colors">Стендап</button>
            </div>
          )}
        </div>
      </nav>
    </header>
  )
}
