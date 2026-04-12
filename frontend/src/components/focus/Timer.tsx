import { useEffect, useState } from 'react'
import { useStore } from '../../store/useStore'
import { formatTimerDisplay, formatDuration } from '../../utils/time'

interface Props {
  taskId: string
}

export function Timer({ taskId }: Props) {
  const { timer, timerStart, timerPause, timerStop, totalTimeForTask } = useStore()
  const [, setTick] = useState(0)

  const isActive = timer.taskId === taskId
  const isRunning = isActive && timer.running

  useEffect(() => {
    if (!isRunning) return
    const interval = setInterval(() => setTick(t => t + 1), 500)
    return () => clearInterval(interval)
  }, [isRunning])

  const currentMs = isActive
    ? timer.accumulatedMs + (isRunning && timer.startedAt ? Date.now() - timer.startedAt : 0)
    : 0

  const savedTotal = totalTimeForTask(taskId)

  return (
    <div className="flex items-center gap-3 bg-[#111113] border border-[#2a2a31] rounded-lg px-4 py-3">
      <div className="font-mono text-2xl text-[#e8e8f0] tabular-nums w-24 select-none">
        {isActive ? formatTimerDisplay(currentMs) : '00:00'}
      </div>

      <div className="flex items-center gap-1.5">
        {!isRunning ? (
          <button
            onClick={() => timerStart(taskId)}
            className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-[#22c55e]/15 text-[#22c55e] border border-[#22c55e]/30 rounded hover:bg-[#22c55e]/25 transition-colors"
          >
            {isActive && currentMs > 0 ? 'Resume' : 'Start'}
          </button>
        ) : (
          <button
            onClick={timerPause}
            className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/30 rounded hover:bg-[#f59e0b]/25 transition-colors"
          >
            Pause
          </button>
        )}
        {isActive && currentMs > 0 && (
          <button
            onClick={timerStop}
            className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-[#ef4444]/10 text-[#ef4444] border border-[#ef4444]/20 rounded hover:bg-[#ef4444]/20 transition-colors"
          >
            Stop
          </button>
        )}
      </div>

      <div className="ml-auto text-right">
        <div className="text-xs text-[#4a4a55] uppercase tracking-wider mb-0.5">Total</div>
        <div className="font-mono text-sm text-[#8b8b9a]">{formatDuration(savedTotal)}</div>
      </div>
    </div>
  )
}
