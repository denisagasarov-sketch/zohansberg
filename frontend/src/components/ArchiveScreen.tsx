import { useState, useEffect, useCallback } from 'react'
import type { Direction, Task } from '../types'
import { api } from '../api'

interface Props {
  directions: Direction[]
  onClose: () => void
  onChanged?: () => void
}

function groupByDay(tasks: Task[]): Map<string, Task[]> {
  const map = new Map<string, Task[]>()
  for (const t of tasks) {
    const key = t.done_at ? t.done_at.slice(0, 10) : 'unknown'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(t)
  }
  return map
}

function formatDay(dateStr: string) {
  if (dateStr === 'unknown') return 'Дата неизвестна'
  const d = new Date(dateStr)
  return d.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

function formatDuration(s: number) {
  if (!s) return null
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

export default function ArchiveScreen({ directions, onClose, onChanged }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)
  const [filterDir, setFilterDir] = useState<number | null>(null)
  const [search, setSearch] = useState('')

  const restore = async (id: number) => {
    // Вернуть задачу в работу: снять «выполнена», положить в очередь «Следом»
    try {
      await api.updateTask(id, { done_at: null, in_queue: true })
      onChanged?.()
      await load()
    } catch (e) { console.error(e) }
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params: { direction_id?: number; search?: string } = {}
      if (filterDir) params.direction_id = filterDir
      if (search.trim()) params.search = search.trim()
      const data = await api.getDoneTasks(params) as Task[]
      setTasks(data)
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }, [filterDir, search])

  useEffect(() => { load() }, [load])

  const grouped = groupByDay(tasks)
  const sortedKeys = [...grouped.keys()].sort((a, b) => b.localeCompare(a))

  return (
    <div className="h-full flex flex-col bg-[#181818] text-[#f0f0f0]">
      <div className="flex items-center gap-3 px-6 py-4 border-b border-[#252525] shrink-0">
        <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">← Назад</button>
        <h1 className="text-base font-semibold flex-1">Архив</h1>
        <select
          value={filterDir ?? ''}
          onChange={e => setFilterDir(e.target.value ? Number(e.target.value) : null)}
          className="bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#666] focus:outline-none [color-scheme:dark]"
        >
          <option value="">Все направления</option>
          {directions.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Поиск…"
          className="bg-[#1c1c1c] border border-[#252525] rounded px-2 py-1 text-sm text-[#f0f0f0] placeholder-[#383838] focus:outline-none focus:border-[#5060a0] w-40"
        />
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && <div className="text-[#666] text-sm">Загрузка…</div>}
        {!loading && tasks.length === 0 && (
          <div className="text-[#666] text-sm">Нет выполненных задач</div>
        )}
        {!loading && sortedKeys.map(key => (
          <div key={key} className="mb-6">
            <div className="text-xs text-[#666] uppercase tracking-wide mb-2 capitalize">{formatDay(key)}</div>
            <div className="space-y-1">
              {grouped.get(key)!.map(task => {
                const dir = directions.find(d => d.id === task.direction_id)
                return (
                  <div key={task.id} className="group bg-[#1c1c1c] border border-[#252525] rounded px-3 py-2">
                    <div className="flex items-center gap-3">
                      <span className="text-[#666] text-sm">✓</span>
                      <span className="flex-1 text-sm text-[#f0f0f0]">{task.title}</span>
                      {dir && <span className="text-xs text-[#666]">{dir.name}</span>}
                      {task.duration_fact > 0 && (
                        <span className="text-xs text-[#5060a0]">{formatDuration(task.duration_fact)}</span>
                      )}
                      {task.done_at && (
                        <span className="text-xs text-[#383838]">
                          {new Date(task.done_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                      <button
                        onClick={() => restore(task.id)}
                        className="text-xs text-[#777] hover:text-[#8090c8] border border-[#333] hover:border-[#5060a0] rounded px-2 py-0.5 shrink-0 transition-colors"
                        title="Вернуть в работу — задача снова появится в «Следом»"
                      >↩ Вернуть</button>
                    </div>
                    {task.notes && (
                      <p className="text-xs text-[#666] mt-1.5 ml-7 whitespace-pre-wrap">{task.notes}</p>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
