import { useState, useEffect } from 'react'
import { api } from '../api'

interface Props {
  onClose: () => void
}

type Period = 'week' | 'month' | 'all'

const MOOD_EMOJI: Record<number, string> = { 1: '😔', 2: '😐', 3: '🙂', 4: '😄', 5: '🚀' }

interface StatsData {
  tasks_total?: number
  tasks_by_direction?: Array<{ direction_name: string | null; count: number }>
  time_total?: number
  time_by_day?: Array<{ date: string; total: number }>
  time_by_direction?: Array<{ direction_name: string | null; total: number }>
  mood_by_day?: Array<{ date: string; mood: number }>
  mood_average?: number
  journal_count?: number
  checkin_count?: number
  top_words?: string[]
}

interface WorklogData {
  heatmap: Array<{ day: string; seconds: number }>
  top_tasks: Array<{ id: number; title: string; direction_name: string; total_seconds: number; first_day: string }>
  log_text: string
  period_label: string
}

function formatHours(s: number) {
  const h = s / 3600
  return h < 1 ? `${Math.round(h * 60)}м` : `${h.toFixed(1)}ч`
}

// GitHub-style heatmap: fills a grid of days for the period
function buildHeatmapGrid(heatmap: WorklogData['heatmap'], period: Period): Array<{ day: string; seconds: number }> {
  const map = new Map(heatmap.map(d => [d.day, d.seconds]))
  const days: Array<{ day: string; seconds: number }> = []
  const count = period === 'week' ? 7 : period === 'month' ? 30 : 90
  for (let i = count - 1; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    const key = d.toISOString().slice(0, 10)
    days.push({ day: key, seconds: map.get(key) ?? 0 })
  }
  return days
}

function heatColor(seconds: number): string {
  if (seconds === 0) return '#1c1c1c'
  const h = seconds / 3600
  if (h < 1) return '#2a3060'
  if (h < 2) return '#3a4880'
  if (h < 3) return '#4a58a0'
  if (h < 4) return '#5060a0'
  return '#8090c8'
}

function formatDayLabel(iso: string) {
  const d = new Date(iso)
  const days = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб']
  const months = ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
  return `${days[d.getDay()]} ${d.getDate()} ${months[d.getMonth()]}`
}

export default function StatsScreen({ onClose }: Props) {
  const [period, setPeriod] = useState<Period>('week')
  const [stats, setStats] = useState<StatsData | null>(null)
  const [worklog, setWorklog] = useState<WorklogData | null>(null)
  const [loading, setLoading] = useState(true)
  const [gptResult, setGptResult] = useState<string | null>(null)
  const [gptLoading, setGptLoading] = useState(false)
  const [hasApiKey, setHasApiKey] = useState(false)

  useEffect(() => {
    setHasApiKey(!!localStorage.getItem('openai_api_key'))
  }, [])

  useEffect(() => {
    setLoading(true)
    setGptResult(null)
    Promise.all([
      api.getStats(period),
      api.getWorklog(period),
    ]).then(([s, w]) => {
      setStats(s as StatsData)
      setWorklog(w as WorklogData)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [period])

  const handleGptAnalyze = async () => {
    if (!worklog) return
    setGptLoading(true)
    setGptResult(null)
    try {
      const prompt = worklog.log_text +
        '\n\nПроанализируй: когда я наиболее продуктивен, на что трачу больше всего времени, какие паттерны видишь, что посоветуешь изменить? Отвечай по-русски, кратко и по делу.'
      const resp = await fetch('/api/ai/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: prompt }),
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.error ?? 'Ошибка сервера')
      setGptResult(data.result ?? '')
    } catch (e) {
      setGptResult(e instanceof Error ? e.message : 'Ошибка при обращении к AI')
    } finally {
      setGptLoading(false)
    }
  }

  const maxDayTime = stats?.time_by_day ? Math.max(...stats.time_by_day.map(d => d.total), 1) : 1
  const heatGrid = worklog ? buildHeatmapGrid(worklog.heatmap, period) : []

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold flex-1">Статистика</h1>
        <div className="flex gap-1">
          {(['week', 'month', 'all'] as Period[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 rounded text-xs transition-colors border ${period === p ? 'bg-[#5060a0] border-[#5060a0] text-white' : 'border-[#252525] text-[#666] hover:border-[#5060a0]/50'}`}
            >
              {p === 'week' ? 'Неделя' : p === 'month' ? 'Месяц' : 'Всё время'}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {loading && <div className="text-[#666] text-sm">Загрузка…</div>}
        {!loading && stats && (
          <>
            <div className="grid grid-cols-2 gap-4">
              {/* Tasks */}
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Задачи</div>
                <div className="text-3xl font-bold text-[#f0f0f0] mb-3">{stats.tasks_total ?? 0}</div>
                {stats.tasks_by_direction && stats.tasks_by_direction.length > 0 && (
                  <div className="space-y-1.5">
                    {stats.tasks_by_direction.slice(0, 5).map((d, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="text-[#666] flex-1 truncate">{d.direction_name ?? 'Без направления'}</span>
                        <span className="text-[#f0f0f0] font-mono">{d.count}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Time */}
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Время</div>
                <div className="text-3xl font-bold text-[#f0f0f0] mb-3">{formatHours(stats.time_total ?? 0)}</div>
                {stats.time_by_day && stats.time_by_day.length > 0 && (
                  <div className="flex items-end gap-0.5 h-12 mb-2">
                    {stats.time_by_day.slice(-14).map((d, i) => (
                      <div
                        key={i}
                        className="flex-1 bg-[#5060a0] rounded-sm min-w-0 transition-all"
                        style={{ height: `${Math.max(2, (d.total / maxDayTime) * 100)}%` }}
                        title={`${d.date}: ${formatHours(d.total)}`}
                      />
                    ))}
                  </div>
                )}
                {stats.time_by_direction && stats.time_by_direction.length > 0 && (
                  <div className="space-y-1">
                    {stats.time_by_direction.slice(0, 4).map((d, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className="text-[#666] flex-1 truncate">{d.direction_name ?? 'Без направления'}</span>
                        <span className="text-[#5060a0] font-mono">{formatHours(d.total)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Mood */}
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Настроение</div>
                {stats.mood_average != null && (
                  <div className="text-3xl mb-3">{MOOD_EMOJI[Math.round(stats.mood_average)] ?? '—'} <span className="text-lg font-mono text-[#666]">{stats.mood_average.toFixed(1)}</span></div>
                )}
                {stats.mood_by_day && stats.mood_by_day.length > 0 && (
                  <div className="flex gap-1 flex-wrap">
                    {stats.mood_by_day.slice(-14).map((d, i) => (
                      <span key={i} className="text-base" title={d.date}>{MOOD_EMOJI[d.mood] ?? '·'}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Journal */}
              <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
                <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-3">Дневник</div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-[#666]">Записей</span>
                    <span className="text-[#f0f0f0] font-mono">{stats.journal_count ?? 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#666]">Чекинов</span>
                    <span className="text-[#f0f0f0] font-mono">{stats.checkin_count ?? 0}</span>
                  </div>
                </div>
                {stats.top_words && stats.top_words.length > 0 && (
                  <div className="mt-3">
                    <div className="text-[10px] text-[#383838] mb-1">Топ слова</div>
                    <div className="flex flex-wrap gap-1">
                      {stats.top_words.slice(0, 5).map((w, i) => (
                        <span key={i} className="text-xs bg-[#252525] px-1.5 py-0.5 rounded text-[#666]">{w}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── Рабочий журнал ── */}
            <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg p-4">
              <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-4">Рабочий журнал</div>

              <div className="flex gap-6">
                {/* Left: heatmap + top tasks */}
                <div className="flex-1 min-w-0">
                  {/* Heatmap */}
                  <div className="mb-1">
                    <div className="flex flex-wrap gap-[3px]">
                      {heatGrid.map(({ day, seconds }) => (
                        <div
                          key={day}
                          title={`${formatDayLabel(day)}: ${seconds > 0 ? formatHours(seconds) : '0'}`}
                          style={{ backgroundColor: heatColor(seconds), width: 12, height: 12, borderRadius: 2, flexShrink: 0 }}
                        />
                      ))}
                    </div>
                    <div className="flex items-center gap-1.5 mt-2">
                      <span className="text-[10px] text-[#383838]">0ч</span>
                      {[0, 3600, 7200, 10800, 14400].map(s => (
                        <div key={s} style={{ backgroundColor: heatColor(s), width: 10, height: 10, borderRadius: 2 }} />
                      ))}
                      <span className="text-[10px] text-[#383838]">4ч+</span>
                    </div>
                  </div>

                  {/* Top tasks */}
                  {worklog && worklog.top_tasks.length > 0 && (
                    <div className="mt-4">
                      <div className="text-[10px] text-[#383838] mb-2">Топ задачи</div>
                      <div className="space-y-1.5">
                        {worklog.top_tasks.slice(0, 3).map((t) => (
                          <div key={t.id} className="flex items-baseline gap-2 text-xs">
                            <span className="text-[#5060a0] font-mono shrink-0 w-10 text-right">{formatHours(t.total_seconds)}</span>
                            <span className="flex-1 text-[#f0f0f0] truncate">{t.title}</span>
                            <span className="text-[#666] shrink-0 truncate max-w-[100px]">{t.direction_name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Right: GPT analysis */}
                <div className="w-64 shrink-0">
                  <button
                    onClick={handleGptAnalyze}
                    disabled={!hasApiKey || gptLoading || !worklog || worklog.top_tasks.length === 0}
                    className="w-full px-3 py-2 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-40 disabled:cursor-not-allowed rounded text-xs text-white transition-colors mb-2"
                  >
                    {gptLoading ? 'Анализирую…' : 'Проанализировать с GPT'}
                  </button>

                  {!hasApiKey && (
                    <p className="text-[10px] text-[#666] mb-2">Добавьте OpenAI API-ключ в настройках</p>
                  )}

                  {gptLoading && (
                    <div className="flex gap-1 mb-2">
                      {[0, 1, 2].map(i => (
                        <div key={i} className="w-1.5 h-1.5 bg-[#5060a0] rounded-full animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                      ))}
                    </div>
                  )}

                  {gptResult && (
                    <div className="bg-[#141414] border border-[#252525] rounded p-3 text-xs text-[#f0f0f0] leading-relaxed whitespace-pre-wrap max-h-64 overflow-y-auto">
                      {gptResult}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
