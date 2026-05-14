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
    const now = new Date().toISOString()
    let sessionId: number | null = null
    try {
      const session = await api.startSession(taskId, now)
      sessionId = session.id
    } catch (e) {
      console.error('Failed to start session', e)
    }
    setState(prev => ({
      ...prev,
      isRunning: true,
      elapsed: 0,
      sessionId,
      taskId,
      sessionDuration: duration,
    }))
    playSound('start')
    intervalRef.current = setInterval(() => {
      setState(prev => {
        const next = prev.elapsed + 1
        if (next >= prev.sessionDuration * 60) {
          clearTimer()
          if (prev.sessionId !== null) {
            api.endSession(prev.sessionId, new Date().toISOString(), next).catch(console.error)
          }
          playSound('timer_end')
          onComplete?.()
          return { ...prev, isRunning: false, elapsed: next, sessionId: null }
        }
        return { ...prev, elapsed: next }
      })
    }, 1000)
  }, [clearTimer, onComplete])

  const pause = useCallback(async () => {
    clearTimer()
    const { sessionId, elapsed } = stateRef.current
    if (sessionId !== null) {
      try {
        await api.endSession(sessionId, new Date().toISOString(), elapsed)
      } catch (e) {
        console.error('Failed to end session', e)
      }
    }
    playSound('pause')
    setState(prev => ({ ...prev, isRunning: false, sessionId: null }))
  }, [clearTimer])

  const stop = useCallback(async () => {
    clearTimer()
    const { sessionId, elapsed } = stateRef.current
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
