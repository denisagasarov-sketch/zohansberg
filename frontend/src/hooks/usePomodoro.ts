import { useState, useRef, useEffect, useCallback } from 'react'
import { playSound } from '../sound'

export type PomodoroPhase = 'work' | 'break' | 'idle'

export interface PomodoroState {
  phase: PomodoroPhase
  remaining: number  // seconds
  cycle: number      // how many work sessions completed
}

function getPomodoroSettings() {
  const work = parseInt(localStorage.getItem('pomo_work_min') ?? '25', 10) * 60
  const brk = parseInt(localStorage.getItem('pomo_break_min') ?? '5', 10) * 60
  return { work, brk }
}

export function usePomodoro(timerRunning: boolean, onWorkEnd: () => void) {
  const enabled = !!parseInt(localStorage.getItem('pomo_enabled') ?? '0', 10)

  const [state, setState] = useState<PomodoroState>({ phase: 'idle', remaining: 0, cycle: 0 })
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  const clearPomo = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }, [])

  const startWork = useCallback(() => {
    clearPomo()
    const { work } = getPomodoroSettings()
    setState(p => ({ phase: 'work', remaining: work, cycle: p.cycle }))
    intervalRef.current = setInterval(() => {
      setState(prev => {
        if (prev.phase !== 'work') return prev
        if (prev.remaining <= 1) {
          clearInterval(intervalRef.current!); intervalRef.current = null
          playSound('done')
          onWorkEnd()
          const { brk } = getPomodoroSettings()
          // auto-start break
          setTimeout(() => {
            setState(p => ({ ...p, phase: 'break', remaining: brk }))
            intervalRef.current = setInterval(() => {
              setState(pp => {
                if (pp.phase !== 'break') return pp
                if (pp.remaining <= 1) {
                  clearInterval(intervalRef.current!); intervalRef.current = null
                  playSound('start')
                  return { phase: 'idle', remaining: 0, cycle: pp.cycle + 1 }
                }
                return { ...pp, remaining: pp.remaining - 1 }
              })
            }, 1000)
          }, 0)
          return { ...prev, phase: 'idle', remaining: 0, cycle: prev.cycle + 1 }
        }
        return { ...prev, remaining: prev.remaining - 1 }
      })
    }, 1000)
  }, [clearPomo, onWorkEnd])

  const skip = useCallback(() => {
    clearPomo()
    setState(p => ({ ...p, phase: 'idle', remaining: 0 }))
  }, [clearPomo])

  // Start pomodoro when timer starts, stop when timer stops
  useEffect(() => {
    if (!enabled) return
    if (timerRunning) {
      startWork()
    } else {
      clearPomo()
      setState({ phase: 'idle', remaining: 0, cycle: 0 })
    }
  }, [timerRunning, enabled]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => clearPomo(), [clearPomo])

  return { pomodoroState: state, pomodoroEnabled: enabled, skipPomodoro: skip }
}
