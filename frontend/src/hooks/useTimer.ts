import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api'
import { playSound, playTimer5mSound, playTimer45mSound } from '../sound'

export interface TimerState {
  isRunning: boolean
  isPaused: boolean
  elapsed: number
  sessionId: number | null
  taskId: number | null
}

export function useTimer() {
  const [state, setState] = useState<TimerState>({
    isRunning: false,
    isPaused: false,
    elapsed: 0,
    sessionId: null,
    taskId: null,
  })

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  const startedAtMsRef = useRef<number | null>(null)
  const sessionIdRef = useRef<number | null>(null)
  const lastTickMarkRef = useRef<number>(0)

  const clearTimer = useCallback(() => {
    if (intervalRef.current !== null) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }, [])

  const clearHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current !== null) {
      clearInterval(heartbeatIntervalRef.current)
      heartbeatIntervalRef.current = null
    }
  }, [])

  const startHeartbeat = useCallback(() => {
    clearHeartbeat()
    heartbeatIntervalRef.current = setInterval(() => {
      const sid = sessionIdRef.current
      if (sid === null) return
      const elapsed = startedAtMsRef.current !== null
        ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
        : stateRef.current.elapsed
      api.heartbeatSession(sid, elapsed).catch(() => {})
    }, 30_000)
  }, [clearHeartbeat])

  useEffect(() => () => { clearTimer(); clearHeartbeat() }, [clearTimer, clearHeartbeat])

  // Close any session left open from a previous page load — always start idle
  useEffect(() => {
    api.getActiveSession().then(session => {
      if (!session) return
      api.endSession(session.id, new Date().toISOString(), session.elapsed_seconds ?? 0).catch(() => {})
    }).catch(() => {})
  }, [])

  const startInterval = useCallback(() => {
    intervalRef.current = setInterval(() => {
      const elapsed = startedAtMsRef.current !== null
        ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
        : 0

      const tickMark = Math.floor(elapsed / 300)
      if (tickMark > 0 && tickMark > lastTickMarkRef.current) {
        lastTickMarkRef.current = tickMark
        if (tickMark % 9 === 0) {
          playTimer45mSound()
        } else {
          playTimer5mSound()
        }
      }

      setState(prev => prev.isRunning ? { ...prev, elapsed } : prev)
    }, 500)
  }, [])

  const start = useCallback(async (taskId: number) => {
    clearTimer()
    const nowMs = Date.now()
    const nowIso = new Date(nowMs).toISOString()

    startedAtMsRef.current = nowMs
    sessionIdRef.current = null
    lastTickMarkRef.current = 0

    setState({ isRunning: true, isPaused: false, elapsed: 0, sessionId: null, taskId })
    playSound('start')
    startInterval()
    startHeartbeat()

    try {
      const session = await api.startSession(taskId, nowIso)
      sessionIdRef.current = session.id
      setState(prev => ({ ...prev, sessionId: session.id }))
    } catch (e) {
      console.error('Failed to start session', e)
    }
  }, [clearTimer, startInterval, startHeartbeat])

  const pause = useCallback(() => {
    clearTimer()
    clearHeartbeat()
    const elapsed = startedAtMsRef.current !== null
      ? Math.floor((Date.now() - startedAtMsRef.current) / 1000)
      : stateRef.current.elapsed
    startedAtMsRef.current = null
    setState(prev => ({ ...prev, isRunning: false, isPaused: true, elapsed }))
    playSound('pause')
  }, [clearTimer, clearHeartbeat])

  const resume = useCallback(() => {
    if (!stateRef.current.isPaused) return
    const currentElapsed = stateRef.current.elapsed
    startedAtMsRef.current = Date.now() - currentElapsed * 1000
    setState(prev => ({ ...prev, isRunning: true, isPaused: false }))
    playSound('start')
    startInterval()
    startHeartbeat()
  }, [startInterval, startHeartbeat])

  const stop = useCallback(async (): Promise<{ sessionId: number | null }> => {
    clearTimer()
    clearHeartbeat()
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
    setState({ isRunning: false, isPaused: false, elapsed: 0, sessionId: null, taskId: null })
    return { sessionId }
  }, [clearTimer, clearHeartbeat])

  return { timerState: state, start, pause, resume, stop }
}
