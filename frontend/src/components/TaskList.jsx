import { useState } from 'react'

export default function TaskList({ tasks, onDone, onDelete, onFocus, onRandom, dailyCount }) {
  const [removing, setRemoving] = useState(null)

  const active = tasks.filter((t) => !t.done)
  const done = tasks.filter((t) => t.done)

  const animatedDone = (id) => {
    setRemoving(id)
    setTimeout(() => {
      onDone(id)
      setRemoving(null)
    }, 280)
  }

  const animatedDelete = (id) => {
    setRemoving(id)
    setTimeout(() => {
      onDelete(id)
      setRemoving(null)
    }, 280)
  }

  // Progress: 5 completed = 100%
  const progressPct = Math.min(dailyCount * 20, 100)

  return (
    <div className="task-list">
      {dailyCount > 0 && (
        <div className="progress-wrap">
          <div className="progress-bar" style={{ width: `${progressPct}%` }} />
          <span className="progress-label">
            {dailyCount} {plural(dailyCount, 'задача', 'задачи', 'задач')} сегодня
          </span>
        </div>
      )}

      {active.length === 0 ? (
        <div className="empty-state">
          <p>Задач нет — добавь первую ↑</p>
        </div>
      ) : (
        <>
          <ul className="tasks">
            {active.map((task) => (
              <li
                key={task.id}
                className={`task-item ${removing === task.id ? 'task-removing' : ''}`}
              >
                <button
                  className="task-check"
                  onClick={() => animatedDone(task.id)}
                  aria-label="Выполнено"
                />
                <span
                  className="task-text"
                  onClick={() => onFocus(task.id)}
                  title="Перейти в режим фокуса"
                >
                  {task.text}
                  {task.subtasks?.some((s) => !s.done) && (
                    <span className="subtask-badge">
                      {task.subtasks.filter((s) => !s.done).length}
                    </span>
                  )}
                </span>
                <div className="task-actions">
                  <button className="btn-focus-sm" onClick={() => onFocus(task.id)}>
                    ▶
                  </button>
                  <button
                    className="btn-delete"
                    onClick={() => animatedDelete(task.id)}
                    aria-label="Удалить"
                  >
                    ×
                  </button>
                </div>
              </li>
            ))}
          </ul>

          {active.length > 1 && (
            <button className="btn-random" onClick={onRandom}>
              ⚡ сделать хоть что-нибудь
            </button>
          )}

          {active.length === 1 && (
            <button className="btn-start-one" onClick={() => onFocus(active[0].id)}>
              ▶ начать
            </button>
          )}
        </>
      )}

      {done.length > 0 && (
        <details className="done-section">
          <summary className="done-summary">Выполнено ({done.length})</summary>
          <ul className="tasks tasks-done">
            {done.map((task) => (
              <li key={task.id} className="task-item task-item-done">
                <span className="task-check-done">✓</span>
                <span className="task-text task-text-done">{task.text}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

function plural(n, one, few, many) {
  if (n % 10 === 1 && n % 100 !== 11) return one
  if (n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20)) return few
  return many
}
