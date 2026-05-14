import { useState, useEffect, useRef } from 'react'
import type { Direction } from '../types'
import { api } from '../api'
import { playSound } from '../sound'

interface Props {
  directions: Direction[]
  onClose: () => void
  onDirectionChange: () => void
  onNavigate: (screen: 'trash') => void
}

const TIMER_PRESETS = [15, 25, 45, 60]
const SOUNDS = ['бип', 'пипипипи', 'гонг', 'нарастающий', '1up', 'победа', 'laser', 'coin']

export default function SettingsScreen({ directions, onClose, onDirectionChange, onNavigate }: Props) {
  const [timerDuration, setTimerDuration] = useState(25)
  const [customDuration, setCustomDuration] = useState('')
  const [timerSound, setTimerSound] = useState('бип')
  const [soundsEnabled, setSoundsEnabled] = useState(true)
  const [volume, setVolume] = useState(0.5)
  const [apiKey, setApiKey] = useState('')
  const [apiStatus, setApiStatus] = useState<'idle' | 'checking' | 'ok' | 'fail'>('idle')
  const [dbPath, setDbPath] = useState('')
  const [newDirName, setNewDirName] = useState('')
  const [editingDir, setEditingDir] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const dragDirRef = useRef<number | null>(null)
  const [localDirs, setLocalDirs] = useState<Direction[]>([])

  useEffect(() => {
    setLocalDirs([...directions].sort((a, b) => a.order_index - b.order_index))
  }, [directions])

  useEffect(() => {
    api.getSettings().then((s: Record<string, string>) => {
      if (s.timer_duration) setTimerDuration(parseInt(s.timer_duration))
      if (s.timer_sound) setTimerSound(s.timer_sound)
      if (s.sounds_enabled) setSoundsEnabled(s.sounds_enabled !== 'false')
      if (s.sounds_volume) setVolume(parseFloat(s.sounds_volume))
      if (s.claude_api_key) setApiKey(s.claude_api_key)
      if (s.db_path) setDbPath(s.db_path)
    }).catch(() => {})
  }, [])

  const saveSetting = (key: string, value: string) => {
    api.updateSetting(key, value).catch(console.error)
    localStorage.setItem(key, value)
  }

  const handleAddDir = async () => {
    if (!newDirName.trim()) return
    await api.createDirection(newDirName.trim())
    setNewDirName('')
    onDirectionChange()
  }

  const handleRenameDir = async (id: number) => {
    if (!editingName.trim()) { setEditingDir(null); return }
    await api.updateDirection(id, { name: editingName.trim() })
    setEditingDir(null)
    onDirectionChange()
  }

  const handleArchiveDir = async (id: number) => {
    if (!window.confirm('Архивировать направление?')) return
    await api.archiveDirection(id)
    onDirectionChange()
  }

  const handleDirDragStart = (_e: React.DragEvent, id: number) => { dragDirRef.current = id }
  const handleDirDragOver = (e: React.DragEvent) => e.preventDefault()
  const handleDirDrop = async (e: React.DragEvent, targetId: number) => {
    e.preventDefault()
    const srcId = dragDirRef.current
    if (!srcId || srcId === targetId) return
    const srcIdx = localDirs.findIndex(d => d.id === srcId)
    const tgtIdx = localDirs.findIndex(d => d.id === targetId)
    const next = [...localDirs]
    const [item] = next.splice(srcIdx, 1)
    next.splice(tgtIdx, 0, item)
    setLocalDirs(next)
    try {
      await Promise.all(next.map((d, i) => api.updateDirection(d.id, { order_index: i })))
      onDirectionChange()
    } catch (e) { console.error(e) }
    dragDirRef.current = null
  }

  const checkApiKey = async () => {
    setApiStatus('checking')
    try {
      const resp = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({ model: 'claude-haiku-20240307', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] }),
      })
      setApiStatus(resp.ok || resp.status === 400 ? 'ok' : 'fail')
    } catch { setApiStatus('fail') }
  }

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525]">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold">Настройки</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-8 max-w-2xl mx-auto w-full">
        {/* Directions */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Направления</h2>
          <div className="space-y-1 mb-3">
            {localDirs.map(dir => (
              <div
                key={dir.id}
                draggable
                onDragStart={e => handleDirDragStart(e, dir.id)}
                onDragOver={handleDirDragOver}
                onDrop={e => handleDirDrop(e, dir.id)}
                className="flex items-center gap-2 bg-[#1c1c1c] border border-[#252525] rounded px-3 py-2 group cursor-grab"
              >
                <span className="text-[#383838] text-xs select-none">⠿</span>
                {editingDir === dir.id ? (
                  <input
                    autoFocus
                    value={editingName}
                    onChange={e => setEditingName(e.target.value)}
                    onBlur={() => handleRenameDir(dir.id)}
                    onKeyDown={e => { if (e.key === 'Enter') handleRenameDir(dir.id); if (e.key === 'Escape') setEditingDir(null) }}
                    className="flex-1 bg-transparent text-sm text-[#f0f0f0] focus:outline-none"
                  />
                ) : (
                  <span
                    className="flex-1 text-sm text-[#f0f0f0] cursor-pointer"
                    onClick={() => { setEditingDir(dir.id); setEditingName(dir.name) }}
                  >{dir.name}</span>
                )}
                <button
                  onClick={() => handleArchiveDir(dir.id)}
                  className="opacity-0 group-hover:opacity-100 text-[#666] hover:text-[#f0f0f0] text-xs transition-all"
                  title="Архивировать"
                >→</button>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <input
              value={newDirName}
              onChange={e => setNewDirName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') handleAddDir() }}
              placeholder="Новое направление…"
              className="flex-1 bg-[#1c1c1c] border border-[#252525] rounded px-3 py-1.5 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0]"
            />
            <button onClick={handleAddDir} className="px-3 py-1.5 bg-[#5060a0] hover:bg-[#8090c8] rounded text-sm text-white transition-colors">+</button>
          </div>
          <button onClick={() => onNavigate('trash')} className="mt-2 text-xs text-[#666] hover:text-[#f0f0f0] transition-colors">Корзина →</button>
        </section>

        {/* Timer */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Таймер</h2>
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            {TIMER_PRESETS.map(p => (
              <button
                key={p}
                onClick={() => { setTimerDuration(p); saveSetting('timer_duration', String(p)) }}
                className={`px-3 py-1.5 rounded text-sm transition-colors border ${timerDuration === p ? 'bg-[#5060a0] border-[#5060a0] text-white' : 'border-[#252525] text-[#666] hover:border-[#5060a0]/50'}`}
              >{p} мин</button>
            ))}
            <div className="flex items-center gap-1">
              <span className="text-xs text-[#666]">Другое:</span>
              <input
                type="number"
                min={1}
                value={customDuration}
                onChange={e => setCustomDuration(e.target.value)}
                onBlur={() => {
                  const v = parseInt(customDuration)
                  if (v > 0) { setTimerDuration(v); saveSetting('timer_duration', String(v)) }
                }}
                placeholder="мин"
                className="w-16 bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1.5 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
              />
            </div>
          </div>
          <div>
            <label className="block text-xs text-[#666] mb-2">Звук по завершении</label>
            <div className="flex flex-wrap gap-2">
              {SOUNDS.map(s => (
                <div key={s} className="flex items-center gap-1">
                  <button
                    onClick={() => { setTimerSound(s); saveSetting('timer_sound', s) }}
                    className={`px-2.5 py-1 rounded text-xs transition-colors border ${timerSound === s ? 'bg-[#5060a0] border-[#5060a0] text-white' : 'border-[#252525] text-[#666] hover:border-[#5060a0]/50'}`}
                  >{s}</button>
                  <button onClick={() => playSound(s)} className="text-[#383838] hover:text-[#666] text-xs" title="Прослушать">▶</button>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Sounds */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Звуки</h2>
          <div className="flex items-center gap-3 mb-3">
            <button
              onClick={() => { const v = !soundsEnabled; setSoundsEnabled(v); saveSetting('sounds_enabled', String(v)) }}
              className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${soundsEnabled ? 'bg-[#5060a0]' : 'bg-[#252525]'}`}
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-white mt-0.5 transition-transform ${soundsEnabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
            </button>
            <span className="text-sm text-[#666]">Звуки на действия</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-[#666] w-16">Громкость</span>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={volume}
              onChange={e => { const v = parseFloat(e.target.value); setVolume(v); saveSetting('sounds_volume', String(v)) }}
              className="flex-1 accent-[#5060a0]"
            />
            <span className="text-xs text-[#666] w-8">{Math.round(volume * 100)}%</span>
          </div>
        </section>

        {/* AI */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">AI и дневник</h2>
          <div className="flex gap-2 mb-2">
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              onBlur={() => saveSetting('claude_api_key', apiKey)}
              placeholder="sk-ant-…"
              className="flex-1 bg-[#1c1c1c] border border-[#252525] rounded px-3 py-1.5 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0]"
            />
            <button
              onClick={checkApiKey}
              disabled={!apiKey || apiStatus === 'checking'}
              className="px-3 py-1.5 bg-[#252525] hover:bg-[#383838] rounded text-sm text-[#666] transition-colors disabled:opacity-50"
            >
              {apiStatus === 'checking' ? 'Проверяю…' : 'Проверить ключ'}
            </button>
          </div>
          {apiStatus === 'ok' && <p className="text-xs text-green-400">✓ Ключ работает</p>}
          {apiStatus === 'fail' && <p className="text-xs text-red-400">✗ Ключ не работает</p>}
        </section>

        {/* Data */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Данные</h2>
          <div className="flex gap-2 items-center">
            <input
              readOnly
              value={dbPath || '~/.zohansberg/data.db'}
              className="flex-1 bg-[#1c1c1c] border border-[#252525] rounded px-3 py-1.5 text-sm text-[#666] cursor-default"
            />
            <button
              className="px-3 py-1.5 bg-[#252525] hover:bg-[#383838] rounded text-sm text-[#666] transition-colors"
              onClick={() => { /* electron shell open */ }}
            >
              Открыть папку
            </button>
          </div>
        </section>
      </div>
    </div>
  )
}
