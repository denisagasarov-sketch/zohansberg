import { useState } from 'react'
import { useTimer } from '../hooks/useTimer'

const pad = (n) => String(n).padStart(2, '0')

export default function PomodoroTimer() {
  const {
    minutes,
    seconds,
    isRunning,
    toggle,
    reset,
    phase,
    sessions,
    changeWorkMinutes,
    workMinutes,
  } = useTimer(25)

  const [editing, setEditing] = useState(false)
  const [inputVal, setInputVal] = useState('')

  const startEdit = () => {
    if (isRunning) return
    setInputVal(String(workMinutes))
    setEditing(true)
  }

  const commitEdit = (e) => {
    e?.preventDefault()
    const val = parseInt(inputVal, 10)
    if (val > 0 && val <= 99) changeWorkMinutes(val)
    setEditing(false)
  }

  // Request notification permission on first start
  const handleToggle = () => {
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission()
    }
    toggle()
  }

  return (
    <div
      className={`pomodoro ${isRunning ? 'pomo-running' : ''} ${
        phase === 'break' ? 'pomo-break' : ''
      }`}
    >
      {sessions > 0 && (
        <span className="pomo-sessions" title={`${sessions} помодоро`}>
          {'🍅'.repeat(Math.min(sessions, 4))}
        </span>
      )}

      {editing ? (
        <form onSubmit={commitEdit} className="pomo-edit-form">
          <input
            type="number"
            className="pomo-edit-input"
            value={inputVal}
            min={1}
            max={99}
            onChange={(e) => setInputVal(e.target.value)}
            autoFocus
            onBlur={commitEdit}
          />
          <span className="pomo-edit-label">мин</span>
        </form>
      ) : (
        <span
          className="pomo-time"
          onClick={startEdit}
          title={!isRunning ? 'Нажми для изменения' : undefined}
        >
          {pad(minutes)}:{pad(seconds)}
        </span>
      )}

      <button className="pomo-btn" onClick={handleToggle} aria-label={isRunning ? 'Пауза' : 'Старт'}>
        {isRunning ? '⏸' : '▶'}
      </button>

      {!isRunning && (
        <button className="pomo-btn" onClick={reset} aria-label="Сбросить" title="Сбросить">
          ↺
        </button>
      )}

      {phase === 'break' && <span className="pomo-break-label">☕ отдых</span>}
    </div>
  )
}
