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

function formatHours(s: number) {
  const h = s / 3600
  return h < 1 ? `${Math.round(h * 60)}м` : `${h.toFixed(1)}ч`
}

export default function StatsScreen({ onClose }: Props) {
  const [period, setPeriod] = useState<Period>('week')
  const [stats, setStats] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api.getStats(period).then(s => { setStats(s as StatsData); setLoading(false) }).catch(() => setLoading(false))
  }, [period])

  const maxDayTime = stats?.time_by_day ? Math.max(...stats.time_by_day.map(d => d.total), 1) : 1

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

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && <div className="text-[#666] text-sm">Загрузка…</div>}
        {!loading && stats && (
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
        )}
      </div>
    </div>
  )
}
