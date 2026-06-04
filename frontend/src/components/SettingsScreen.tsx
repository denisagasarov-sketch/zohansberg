import { useState, useEffect, useRef } from 'react'
import type { Direction } from '../types'
import { api } from '../api'
import { TIMER_SOUNDS, getTimer5mSoundId, getTimer45mSoundId, previewTimerSound } from '../sound'
import ArtilleryGame from './ArtilleryGame'
import ErrorBoundary from './ErrorBoundary'

interface Props {
  directions: Direction[]
  onClose: () => void
  onDirectionChange: () => void
  onNavigate: (screen: 'trash') => void
}

export default function SettingsScreen({ directions, onClose, onDirectionChange, onNavigate }: Props) {
  const [timer5mSoundId, setTimer5mSoundId] = useState(getTimer5mSoundId())
  const [timer45mSoundId, setTimer45mSoundId] = useState(getTimer45mSoundId())
  const [soundsEnabled, setSoundsEnabled] = useState(true)
  const [volume, setVolume] = useState(0.5)
  const [apiKey, setApiKey] = useState('')
  const [apiStatus, setApiStatus] = useState<'idle' | 'checking' | 'ok' | 'fail'>('idle')
  const [anthropicKey, setAnthropicKey] = useState('')
  const [dbPath, setDbPath] = useState('')
  const [newDirName, setNewDirName] = useState('')
  const [editingDir, setEditingDir] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const dragDirRef = useRef<number | null>(null)
  const [localDirs, setLocalDirs] = useState<Direction[]>([])
  // hidden easter egg: tap the «Настройки» title 7 times to unlock the worms game
  const [titleTaps, setTitleTaps] = useState(0)
  const [showGame, setShowGame] = useState(false)
  const tapResetRef = useRef<number | null>(null)

  const handleTitleTap = () => {
    if (tapResetRef.current) window.clearTimeout(tapResetRef.current)
    setTitleTaps(prev => {
      const n = prev + 1
      if (n >= 7) { setShowGame(true); return 0 }
      tapResetRef.current = window.setTimeout(() => setTitleTaps(0), 1200)
      return n
    })
  }

  useEffect(() => {
    setLocalDirs([...directions].sort((a, b) => a.order_index - b.order_index))
  }, [directions])

  useEffect(() => {
    api.getSettings().then((s: Record<string, string>) => {
      if (s.sounds_enabled) setSoundsEnabled(s.sounds_enabled !== 'false')
      if (s.sounds_volume) setVolume(parseFloat(s.sounds_volume))
      if (s.openai_api_key) setApiKey(s.openai_api_key)
      if (s.anthropic_api_key) setAnthropicKey(s.anthropic_api_key)
      if (s.db_path) setDbPath(s.db_path)
    }).catch(() => {})
  }, [])

  const saveSetting = (key: string, value: string) => {
    api.updateSetting(key, value).catch(console.error)
    localStorage.setItem(key, value)
  }

  const handleSelect5mSound = (id: number) => {
    setTimer5mSoundId(id)
    localStorage.setItem('timer_sound_5m', String(id))
  }

  const handleSelect45mSound = (id: number) => {
    setTimer45mSoundId(id)
    localStorage.setItem('timer_sound_45m', String(id))
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
      const resp = await fetch('/api/settings/test-key', { method: 'POST' })
      const data = await resp.json()
      setApiStatus(data.valid ? 'ok' : 'fail')
    } catch { setApiStatus('fail') }
  }

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525]">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold cursor-default select-none" onClick={handleTitleTap}>
          Настройки{titleTaps >= 3 && titleTaps < 7 && <span className="text-[#2c2c2c] text-xs ml-1">{'🐛'.repeat(titleTaps - 2)}</span>}
        </h1>
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
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all shrink-0">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    defaultValue={dir.weekly_goal_seconds ? Math.round(dir.weekly_goal_seconds / 3600) : ''}
                    placeholder="ч/нед"
                    title="Цель в часах в неделю"
                    onBlur={e => {
                      const h = parseFloat(e.target.value) || 0
                      api.updateDirection(dir.id, { weekly_goal_seconds: Math.round(h * 3600) } as any).catch(() => {})
                    }}
                    className="w-14 bg-[#141414] border border-[#252525] rounded px-1.5 py-0.5 text-xs text-[#999] focus:outline-none text-center"
                  />
                  <button
                    onClick={() => handleArchiveDir(dir.id)}
                    className="text-[#666] hover:text-[#f0f0f0] text-xs"
                    title="Архивировать"
                  >→</button>
                </div>
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

        {/* 5-minute sound */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-1">Звук каждые 5 минут</h2>
          <p className="text-xs text-[#555] mb-3">Короткий сигнал, пока таймер активен</p>
          <div className="space-y-0.5 max-h-64 overflow-y-auto pr-1 rounded border border-[#252525]">
            {TIMER_SOUNDS.map(sound => (
              <div
                key={sound.id}
                onClick={() => handleSelect5mSound(sound.id)}
                className={`flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors ${
                  timer5mSoundId === sound.id
                    ? 'bg-[#5060a0]/20 text-[#f0f0f0]'
                    : 'hover:bg-[#252525]/60 text-[#999]'
                }`}
              >
                <span className={`text-[10px] w-5 shrink-0 font-mono ${timer5mSoundId === sound.id ? 'text-[#5060a0]' : 'text-[#383838]'}`}>
                  {String(sound.id).padStart(2, '0')}
                </span>
                <span className="flex-1 text-sm">{sound.name}</span>
                {timer5mSoundId === sound.id && <span className="text-[#5060a0] text-[10px] shrink-0">✓</span>}
                <button
                  onClick={e => { e.stopPropagation(); previewTimerSound(sound.id) }}
                  className="text-[#383838] hover:text-[#8090c8] text-xs shrink-0 px-1 transition-colors"
                  title="Прослушать"
                >▶</button>
              </div>
            ))}
          </div>
        </section>

        {/* 45-minute sound */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-1">Звук каждые 45 минут</h2>
          <p className="text-xs text-[#555] mb-3">Длинный сигнал ≥ 2.5с — напоминание о большом перерыве</p>
          <div className="space-y-0.5 max-h-64 overflow-y-auto pr-1 rounded border border-[#252525]">
            {TIMER_SOUNDS.map(sound => (
              <div
                key={sound.id}
                onClick={() => handleSelect45mSound(sound.id)}
                className={`flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors ${
                  timer45mSoundId === sound.id
                    ? 'bg-[#5060a0]/20 text-[#f0f0f0]'
                    : 'hover:bg-[#252525]/60 text-[#999]'
                }`}
              >
                <span className={`text-[10px] w-5 shrink-0 font-mono ${timer45mSoundId === sound.id ? 'text-[#5060a0]' : 'text-[#383838]'}`}>
                  {String(sound.id).padStart(2, '0')}
                </span>
                <span className="flex-1 text-sm">{sound.name}</span>
                {timer45mSoundId === sound.id && <span className="text-[#5060a0] text-[10px] shrink-0">✓</span>}
                <button
                  onClick={e => { e.stopPropagation(); previewTimerSound(sound.id, true) }}
                  className="text-[#383838] hover:text-[#8090c8] text-xs shrink-0 px-1 transition-colors"
                  title="Прослушать (длинная версия)"
                >▶</button>
              </div>
            ))}
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

        {/* Anthropic API */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-1">Anthropic API</h2>
          <p className="text-xs text-[#555] mb-3">Используется для улучшения формулировок задач (кнопка ✨)</p>
          <input
            type="password"
            value={anthropicKey}
            onChange={e => setAnthropicKey(e.target.value)}
            onBlur={() => saveSetting('anthropic_api_key', anthropicKey)}
            placeholder="sk-ant-…"
            className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-3 py-1.5 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0]"
          />
        </section>

        {/* OpenAI API */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-1">OpenAI API</h2>
          <p className="text-xs text-[#555] mb-3">Используется для анализа дневника</p>
          <div className="flex gap-2 mb-2">
            <input
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              onBlur={() => saveSetting('openai_api_key', apiKey)}
              placeholder="sk-…"
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

        {/* Pomodoro */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Помодоро</h2>
          <PomodoroSettings />
        </section>

        {/* Focus settings */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Фокус</h2>
          <div className="space-y-3">
            <ToggleSetting storageKey="intent_enabled" defaultOn label="Намерение перед сессией" desc="Спрашивать «что сделаешь?» перед запуском таймера" />
            <ToggleSetting storageKey="break_screen_enabled" defaultOn label="Экран перерыва" desc="Показывать экран с подсказками когда таймер на паузе" />
          </div>
        </section>

        {/* Ritual settings */}
        <section>
          <h2 className="text-sm font-semibold text-[#f0f0f0] mb-3">Ритуалы</h2>
          <div className="space-y-3">
            <ToggleSetting storageKey="checkin_enabled" defaultOn label="Утренний чек-ин" desc="Вопрос о настроении и цели на день при открытии" />
            <ToggleSetting storageKey="evening_enabled" defaultOn label="Вечерний итог" desc="Итог дня после 19:00 + план на завтра" />
            <ToggleSetting storageKey="weekly_review_enabled" defaultOn label="Еженедельный обзор" desc="Обзор недели в пятницу/субботу/воскресенье после 17:00" />
            <ToggleSetting storageKey="monthly_review_enabled" defaultOn label="Месячный и квартальный обзор" desc="Обзор месяца 1–3 числа каждого месяца" />
          </div>
        </section>
      </div>

      {showGame && (
        <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-6" onClick={() => setShowGame(false)}>
          <div className="bg-[#181818] border border-[#252525] rounded-lg p-4 w-full max-w-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-[#f0f0f0]">🐛 Черви</h2>
              <button onClick={() => setShowGame(false)} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">✕ Закрыть</button>
            </div>
            <ErrorBoundary><ArtilleryGame /></ErrorBoundary>
          </div>
        </div>
      )}
    </div>
  )
}

function PomodoroSettings() {
  const [enabled, setEnabled] = useState(() => !!parseInt(localStorage.getItem('pomo_enabled') ?? '0', 10))
  const [workMin, setWorkMin] = useState(() => parseInt(localStorage.getItem('pomo_work_min') ?? '25', 10))
  const [breakMin, setBreakMin] = useState(() => parseInt(localStorage.getItem('pomo_break_min') ?? '5', 10))

  const toggle = () => {
    const next = !enabled
    setEnabled(next)
    localStorage.setItem('pomo_enabled', next ? '1' : '0')
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-[#999]">Включить помодоро</span>
        <button onClick={toggle} className={`relative inline-flex h-5 w-9 rounded-full transition-colors ${enabled ? 'bg-[#5060a0]' : 'bg-[#252525]'}`}>
          <span className={`inline-block h-4 w-4 rounded-full bg-white mt-0.5 transition-transform ${enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
        </button>
      </div>
      {enabled && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-[#555] mb-1">Работа (мин)</label>
            <input type="number" min="1" max="120" value={workMin}
              onChange={e => { const v = parseInt(e.target.value) || 25; setWorkMin(v); localStorage.setItem('pomo_work_min', String(v)) }}
              className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
            />
          </div>
          <div>
            <label className="block text-xs text-[#555] mb-1">Перерыв (мин)</label>
            <input type="number" min="1" max="60" value={breakMin}
              onChange={e => { const v = parseInt(e.target.value) || 5; setBreakMin(v); localStorage.setItem('pomo_break_min', String(v)) }}
              className="w-full bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] focus:outline-none focus:border-[#5060a0]"
            />
          </div>
        </div>
      )}
    </div>
  )
}

function ToggleSetting({ storageKey, defaultOn, label, desc }: { storageKey: string; defaultOn: boolean; label: string; desc: string }) {
  const init = () => {
    const v = localStorage.getItem(storageKey)
    if (v === null) return defaultOn
    return v !== 'false'
  }
  const [on, setOn] = useState(init)
  const toggle = () => {
    const next = !on; setOn(next)
    localStorage.setItem(storageKey, next ? 'true' : 'false')
  }
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm text-[#999]">{label}</p>
        <p className="text-[11px] text-[#555] mt-0.5">{desc}</p>
      </div>
      <button onClick={toggle} className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition-colors ${on ? 'bg-[#5060a0]' : 'bg-[#252525]'}`}>
        <span className={`inline-block h-4 w-4 rounded-full bg-white mt-0.5 transition-transform ${on ? 'translate-x-4' : 'translate-x-0.5'}`} />
      </button>
    </div>
  )
}
