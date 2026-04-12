import { useState, useEffect, useRef } from 'react'

export function useTimer(defaultMinutes = 25) {
  const [workMinutes, setWorkMinutes] = useState(defaultMinutes)
  const [timeLeft, setTimeLeft] = useState(defaultMinutes * 60)
  const [isRunning, setIsRunning] = useState(false)
  const [phase, setPhase] = useState('work') // 'work' | 'break'
  const [sessions, setSessions] = useState(0)

  // Refs to read latest values inside effects without re-subscribing
  const phaseRef = useRef(phase)
  const workMinutesRef = useRef(workMinutes)
  phaseRef.current = phase
  workMinutesRef.current = workMinutes

  // Countdown tick
  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(() => {
      setTimeLeft((t) => (t > 0 ? t - 1 : 0))
    }, 1000)
    return () => clearInterval(id)
  }, [isRunning])

  // Handle timer reaching zero
  useEffect(() => {
    if (timeLeft !== 0 || !isRunning) return

    setIsRunning(false)
    const nextPhase = phaseRef.current === 'work' ? 'break' : 'work'
    setPhase(nextPhase)
    if (nextPhase === 'break') setSessions((s) => s + 1)
    setTimeLeft(nextPhase === 'work' ? workMinutesRef.current * 60 : 5 * 60)

    // Browser notification (if permitted)
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(nextPhase === 'break' ? '☕ Отдых — 5 минут' : '💪 Время работать!')
    }
  }, [timeLeft, isRunning])

  const toggle = () => setIsRunning((r) => !r)

  const reset = () => {
    setIsRunning(false)
    setPhase('work')
    setTimeLeft(workMinutesRef.current * 60)
  }

  const changeWorkMinutes = (mins) => {
    setWorkMinutes(mins)
    setIsRunning(false)
    setPhase('work')
    setTimeLeft(mins * 60)
  }

  return {
    minutes: Math.floor(timeLeft / 60),
    seconds: timeLeft % 60,
    isRunning,
    toggle,
    reset,
    phase,
    sessions,
    changeWorkMinutes,
    workMinutes,
  }
}
