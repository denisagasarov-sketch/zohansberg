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
  const enabled = !!parseInt(localStorage.getItem('pomo_enabled') ?? '1', 10)

  const [state, setState] = useState<PomodoroState>({ phase: 'idle', remaining: 0, cycle: 0 })
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const stateRef = useRef(state)
  stateRef.current = state

  const clearPomo = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null }
  }, [])

  // One interval drives both phases. Side effects (sound, onWorkEnd, phase
  // transitions) live HERE, in the tick — never inside a setState updater.
  // Under React.StrictMode (active on the dev server) updaters are double-invoked,
  // so a side effect inside one would fire twice and leak a second interval.
  const tick = useCallback(() => {
    const cur = stateRef.current
    if (cur.phase === 'work') {
      if (cur.remaining <= 1) {
        playSound('done')
        onWorkEnd()
        const { brk } = getPomodoroSettings()
        setState(p => ({ ...p, phase: 'break', remaining: brk }))
      } else {
        setState(p => ({ ...p, remaining: p.remaining - 1 }))
      }
    } else if (cur.phase === 'break') {
      if (cur.remaining <= 1) {
        playSound('start')
        clearPomo()
        setState(p => ({ phase: 'idle', remaining: 0, cycle: p.cycle + 1 }))
      } else {
        setState(p => ({ ...p, remaining: p.remaining - 1 }))
      }
    }
  }, [clearPomo, onWorkEnd])

  const startWork = useCallback(() => {
    clearPomo()
    const { work } = getPomodoroSettings()
    setState(p => ({ phase: 'work', remaining: work, cycle: p.cycle }))
    intervalRef.current = setInterval(tick, 1000)
  }, [clearPomo, tick])

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
