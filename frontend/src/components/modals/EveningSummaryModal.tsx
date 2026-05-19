import { useState, useEffect, useCallback } from 'react'
import type { Task } from '../../types'
import { api } from '../../api'
import { playSound } from '../../sound'

interface Props {
  incompleteTasks: Task[]
  onClose: () => void
  onLater: () => void
  onMoveToTomorrow: (taskId: number) => void
}

function formatSeconds(s: number) {
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

export default function EveningSummaryModal({ incompleteTasks, onClose, onLater, onMoveToTomorrow }: Props) {
  const [bars, setBars] = useState([0.4, 0.7, 0.5, 0.9, 0.3, 0.8, 0.6, 0.4, 0.7, 0.5])
  const [doneCount, setDoneCount] = useState(0)
  const [timeSeconds, setTimeSeconds] = useState(0)
  const [movedIds, setMovedIds] = useState<Set<number>>(new Set())

  useEffect(() => {
    playSound('fanfare', 1.0)
    api.getTodaySummary().then((d: any) => {
      setDoneCount(d.done_count)
      setTimeSeconds(d.time_seconds)
    }).catch(() => {})
    const id = setInterval(() => {
      setBars(prev => prev.map(() => 0.15 + Math.random() * 0.85))
    }, 130)
    return () => clearInterval(id)
  }, [])

  const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', weekday: 'long' })

  const handleMoveToTomorrow = useCallback((taskId: number) => {
    setMovedIds(prev => new Set([...prev, taskId]))
    onMoveToTomorrow(taskId)
  }, [onMoveToTomorrow])

  const visibleTasks = incompleteTasks.filter(t => !movedIds.has(t.id)).slice(0, 8)

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/80" onClick={onLater} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-md shadow-2xl overflow-hidden">
        {/* Animated sound bars */}
        <div className="flex items-end gap-1 px-6 pt-5 pb-1 h-14" style={{ background: 'linear-gradient(180deg, #1a1a2e 0%, #1c1c1c 100%)' }}>
          {bars.map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-sm"
              style={{
                height: `${h * 100}%`,
                backgroundColor: `hsl(${230 + i * 4}, 60%, ${45 + h * 20}%)`,
                transition: 'height 0.12s ease-in-out',
              }}
            />
          ))}
        </div>

        <div className="px-6 pb-6">
          {/* Title */}
          <h2 className="text-xl font-bold text-[#f0f0f0] mt-4 mb-0.5">Итог дня</h2>
          <p className="text-sm text-[#555] mb-5 capitalize">{today}</p>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-3 mb-5">
            <div className="bg-[#141414] rounded-xl p-3">
              <div className="text-2xl font-bold text-[#f0f0f0]">{doneCount}</div>
              <div className="text-xs text-[#555] mt-0.5">задач выполнено</div>
            </div>
            <div className="bg-[#141414] rounded-xl p-3">
              <div className="text-2xl font-bold text-[#f0f0f0]">{formatSeconds(timeSeconds)}</div>
              <div className="text-xs text-[#555] mt-0.5">время в работе</div>
            </div>
          </div>

          {/* Incomplete tasks */}
          {visibleTasks.length > 0 && (
            <div className="mb-5">
              <div className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase mb-2">Незавершённые</div>
              <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                {visibleTasks.map(task => (
                  <div key={task.id} className="flex items-center gap-2 bg-[#141414] rounded-lg px-3 py-2">
                    <span className="flex-1 text-sm text-[#999] truncate">{task.title}</span>
                    <button
                      onClick={() => handleMoveToTomorrow(task.id)}
                      className="text-[10px] text-[#5060a0] hover:text-[#8090c8] transition-colors shrink-0 whitespace-nowrap"
                    >
                      На завтра →
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2">
            <button onClick={onLater} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
              Позже
            </button>
            <button onClick={onClose} className="flex-1 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-xl text-sm text-white transition-colors font-medium">
              Закрыть день ✓
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
