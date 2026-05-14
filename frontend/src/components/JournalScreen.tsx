import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { JournalEntry } from '../types'
import { playSound } from '../sound'

interface Props {
  onClose: () => void
}

const MOOD_EMOJI: Record<number, string> = { 1: '😔', 2: '😐', 3: '🙂', 4: '😄', 5: '🚀' }

function groupByDay(entries: JournalEntry[]): Map<string, JournalEntry[]> {
  const map = new Map<string, JournalEntry[]>()
  for (const e of entries) {
    const key = e.created_at.slice(0, 10)
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(e)
  }
  return map
}

function formatDay(dateStr: string) {
  const d = new Date(dateStr)
  return d.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'long' })
}

export default function JournalScreen({ onClose }: Props) {
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showThoughtInput, setShowThoughtInput] = useState(false)
  const [thoughtText, setThoughtText] = useState('')
  const [analysis, setAnalysis] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [apiKey, setApiKey] = useState('')

  useEffect(() => {
    const k = localStorage.getItem('openai_api_key')
    if (k) setApiKey(k)
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getJournal()
      setEntries(Array.isArray(data) ? data as JournalEntry[] : [])
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAddThought = async () => {
    if (!thoughtText.trim()) return
    try {
      await api.createJournalEntry({ type: 'thought', content: thoughtText.trim() })
      playSound('thought_saved')
      setThoughtText('')
      setShowThoughtInput(false)
      await load()
    } catch (e) { console.error(e) }
  }

  const handleAnalyze = async () => {
    if (!apiKey) return
    setAnalyzing(true)
    setAnalysis(null)
    const week = entries.slice(0, 50)
    const text = week.map(e => {
      if (e.type === 'checkin') return `[Чекин] Настроение: ${MOOD_EMOJI[e.mood ?? 0] ?? e.mood}, Цель: ${e.goal ?? ''}, Мысли: ${e.content ?? ''}`
      return `[Мысль] ${e.content ?? ''}`
    }).join('\n')
    try {
      const resp = await fetch('/api/ai/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error ?? 'Ошибка сервера')
      setAnalysis(data.result ?? 'Не удалось получить анализ')
    } catch (e) {
      setAnalysis(e instanceof Error ? e.message : 'Ошибка при обращении к AI')
    } finally {
      setAnalyzing(false)
    }
  }

  const filtered = search.trim()
    ? entries.filter(e => (e.content ?? '').toLowerCase().includes(search.toLowerCase()) || (e.goal ?? '').toLowerCase().includes(search.toLowerCase()))
    : entries

  const grouped = groupByDay(filtered)
  const sortedKeys = [...grouped.keys()].sort((a, b) => b.localeCompare(a))

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold flex-1">Дневник</h1>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск…"
          className="bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0] w-40"
        />
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: entries */}
        <div className="flex-[3] overflow-y-auto px-6 py-4 border-r border-[#252525]">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => setShowThoughtInput(v => !v)}
              className="text-xs px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] rounded transition-colors text-white"
            >
              + Добавить мысль
            </button>
          </div>

          {showThoughtInput && (
            <div className="mb-4 bg-[#1c1c1c] border border-[#252525] rounded-lg p-3">
              <textarea
                autoFocus
                value={thoughtText}
                onChange={e => setThoughtText(e.target.value)}
                placeholder="Что у тебя на уме?"
                rows={3}
                className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838] mb-2"
              />
              <div className="flex gap-2 justify-end">
                <button onClick={() => setShowThoughtInput(false)} className="text-xs text-[#666] hover:text-[#f0f0f0]">Отмена</button>
                <button onClick={handleAddThought} className="text-xs px-3 py-1 bg-[#5060a0] hover:bg-[#8090c8] rounded text-white transition-colors">Сохранить</button>
              </div>
            </div>
          )}

          {loading && <div className="text-[#666] text-sm">Загрузка…</div>}
          {!loading && filtered.length === 0 && (
            <div className="text-[#666] text-sm">Нет записей</div>
          )}
          {!loading && sortedKeys.map(key => (
            <div key={key} className="mb-5">
              <div className="text-[10px] text-[#666] uppercase tracking-wide mb-2 capitalize">{formatDay(key)}</div>
              <div className="space-y-2">
                {grouped.get(key)!.map(entry => {
                  if (entry.type === 'checkin') {
                    return (
                      <div key={entry.id} className="bg-[#1c1c1c] border border-[#252525] rounded-lg px-3 py-2.5">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xl">{MOOD_EMOJI[entry.mood ?? 0] ?? '·'}</span>
                          <span className="text-xs text-[#666]">Чекин</span>
                          <span className="text-[10px] text-[#383838] ml-auto">
                            {new Date(entry.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                        {entry.goal && <p className="text-sm text-[#f0f0f0] mb-1 font-medium">{entry.goal}</p>}
                        {entry.content && <p className="text-sm text-[#666]">{entry.content}</p>}
                      </div>
                    )
                  }
                  return (
                    <div key={entry.id} className="bg-[#1c1c1c] border border-[#252525] rounded-lg px-3 py-2">
                      <div className="flex items-start gap-2">
                        <span className="text-[#383838] text-sm mt-0.5">💭</span>
                        <p className="flex-1 text-sm text-[#f0f0f0]">{entry.content}</p>
                        <span className="text-[10px] text-[#383838] shrink-0 mt-0.5">
                          {new Date(entry.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Right: AI analysis */}
        <div className="flex-[2] overflow-y-auto px-6 py-4">
          <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">AI-анализ</div>
          <button
            onClick={handleAnalyze}
            disabled={!apiKey || analyzing}
            className="w-full px-4 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm text-white transition-colors mb-3"
          >
            {analyzing ? 'Анализирую…' : 'Анализировать за неделю'}
          </button>
          {!apiKey && (
            <p className="text-xs text-[#666] mb-3">Добавьте OpenAI API-ключ в настройках, чтобы использовать анализ</p>
          )}
          {analyzing && (
            <div className="flex gap-1 mb-3">
              {[0, 1, 2].map(i => (
                <div key={i} className="w-1.5 h-1.5 bg-[#5060a0] rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
          )}
          {analysis && (
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg px-4 py-3 text-sm text-[#f0f0f0] leading-relaxed whitespace-pre-wrap">
              {analysis}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
