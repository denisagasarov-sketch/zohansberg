import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api'
import { playSound, playTimerSound } from '../sound'

export interface TimerState {
  isRunning: boolean
  elapsed: number
  sessionId: number | null
  taskId: number | null
}

export function useTimer() {
  const [state, setState] = useState<TimerState>({
    isRunning: false,
    elapsed: 0,
    sessionId: null,
    taskId: null,
  })

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  // Wall-clock ref for drift-free elapsed
  const startedAtMsRef = useRef<number | null>(null)
  // Async session ID — set after API responds
  const sessionIdRef = useRef<number | null>(null)
  // Last 5-min mark at which tick sound was played (1 = 5 min, 2 = 10 min …)
  const lastTickMarkRef = useRef<number>(0)

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => () => clearTimer(), [clearTimer])

  const start = useCallback(async (taskId: number) => {
    clearTimer()
    const nowMs = Date.now()
    const nowIso = new Date(nowMs).toISOString()

    startedAtMsRef.current = nowMs
    sessionIdRef.current = null
    lastTickMarkRef.current = 0

    setState(prev => ({ ...prev, isRunning: true, elapsed: 0, sessionId: null, taskId }))
    playSound('start')

    // Poll every 500 ms; compute elapsed from wall clock to avoid drift
    intervalRef.current = setInterval(() => {
      const elapsed = startedAtMsRef.current !== null
        ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
        : 0

      // Play selected timer sound at each 5-minute boundary
      const tickMark = Math.floor(elapsed / 300)
      if (tickMark > 0 && tickMark > lastTickMarkRef.current) {
        lastTickMarkRef.current = tickMark
        playTimerSound()
      }

      setState(prev => prev.isRunning ? { ...prev, elapsed } : prev)
    }, 500)

    // Register session in DB async; store ID for stop/done
    try {
      const session = await api.startSession(taskId, nowIso)
      sessionIdRef.current = session.id
      setState(prev => ({ ...prev, sessionId: session.id }))
    } catch (e) {
      console.error('Failed to start session', e)
    }
  }, [clearTimer])

  // Stop: saves elapsed to DB, resets counter to 0
  const stop = useCallback(async () => {
    clearTimer()
    const elapsed = startedAtMsRef.current !== null
      ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
      : stateRef.current.elapsed
    const sessionId = sessionIdRef.current
    sessionIdRef.current = null
    startedAtMsRef.current = null
    lastTickMarkRef.current = 0

    if (sessionId !== null) {
      try {
        await api.endSession(sessionId, new Date().toISOString(), elapsed)
      } catch (e) {
        console.error('Failed to end session', e)
      }
    }
    playSound('pause')
    setState({ isRunning: false, elapsed: 0, sessionId: null, taskId: null })
  }, [clearTimer])

  return { timerState: state, start, stop }
}
