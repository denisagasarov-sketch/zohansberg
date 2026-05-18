import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api'
import { playSound } from '../sound'

export interface TimerState {
  isRunning: boolean
  elapsed: number
  sessionId: number | null
  taskId: number | null
  sessionDuration: number
}

const DEFAULT_DURATION = 25

export function useTimer(onComplete?: () => void) {
  const [state, setState] = useState<TimerState>({
    isRunning: false,
    elapsed: 0,
    sessionId: null,
    taskId: null,
    sessionDuration: DEFAULT_DURATION,
  })

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  // Wall-clock reference for accurate elapsed (avoids setInterval drift)
  const startedAtMsRef = useRef<number | null>(null)
  // Session ID set async after API responds; read in pause/stop
  const sessionIdRef = useRef<number | null>(null)

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  useEffect(() => {
    return () => clearTimer()
  }, [clearTimer])

  const start = useCallback(async (taskId: number, sessionDuration?: number) => {
    clearTimer()
    const duration = sessionDuration ?? stateRef.current.sessionDuration
    const nowMs = Date.now()
    const nowIso = new Date(nowMs).toISOString()

    startedAtMsRef.current = nowMs
    sessionIdRef.current = null

    // Start displaying immediately — do not wait for the API round-trip
    setState(prev => ({
      ...prev,
      isRunning: true,
      elapsed: 0,
      sessionId: null,
      taskId,
      sessionDuration: duration,
    }))
    playSound('start')

    // Poll every 500 ms; compute elapsed from wall clock, not tick count
    intervalRef.current = setInterval(() => {
      const elapsed = startedAtMsRef.current !== null
        ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
        : 0

      setState(prev => {
        if (!prev.isRunning) return prev
        if (elapsed >= prev.sessionDuration * 60) {
          clearTimer()
          const sid = sessionIdRef.current
          if (sid !== null) {
            api.endSession(sid, new Date().toISOString(), elapsed).catch(console.error)
            sessionIdRef.current = null
          }
          startedAtMsRef.current = null
          playSound('timer_end')
          onComplete?.()
          return { ...prev, isRunning: false, elapsed, sessionId: null }
        }
        return { ...prev, elapsed }
      })
    }, 500)

    // Register session in DB async; update state when we have the ID
    try {
      const session = await api.startSession(taskId, nowIso)
      sessionIdRef.current = session.id
      setState(prev => ({ ...prev, sessionId: session.id }))
    } catch (e) {
      console.error('Failed to start session', e)
    }
  }, [clearTimer, onComplete])

  const pause = useCallback(async () => {
    clearTimer()
    const elapsed = startedAtMsRef.current !== null
      ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
      : stateRef.current.elapsed
    const sessionId = sessionIdRef.current
    sessionIdRef.current = null
    startedAtMsRef.current = null

    if (sessionId !== null) {
      try {
        await api.endSession(sessionId, new Date().toISOString(), elapsed)
      } catch (e) {
        console.error('Failed to end session', e)
      }
    }
    playSound('pause')
    setState(prev => ({ ...prev, isRunning: false, elapsed, sessionId: null }))
  }, [clearTimer])

  const stop = useCallback(async () => {
    clearTimer()
    const elapsed = startedAtMsRef.current !== null
      ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
      : stateRef.current.elapsed
    const sessionId = sessionIdRef.current
    sessionIdRef.current = null
    startedAtMsRef.current = null

    if (sessionId !== null) {
      try {
        await api.endSession(sessionId, new Date().toISOString(), elapsed)
      } catch (e) {
        console.error('Failed to end session', e)
      }
    }
    setState({
      isRunning: false,
      elapsed: 0,
      sessionId: null,
      taskId: null,
      sessionDuration: stateRef.current.sessionDuration,
    })
  }, [clearTimer])

  const setDuration = useCallback((minutes: number) => {
    setState(prev => ({ ...prev, sessionDuration: minutes }))
  }, [])

  return { timerState: state, start, pause, stop, setDuration }
}
