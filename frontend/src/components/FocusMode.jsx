import { useState } from 'react'

export default function FocusMode({ task, queueLength, onDone, onSkip, onSplit, onBack }) {
  const [splitMode, setSplitMode] = useState(false)
  const [splitText, setSplitText] = useState('')
  const [completedSubs, setCompletedSubs] = useState(new Set())
  const [completing, setCompleting] = useState(false)

  if (!task) {
    return (
      <div className="focus-mode focus-empty">
        <p className="focus-empty-text">Все задачи выполнены!</p>
        <button className="btn-back" onClick={onBack}>
          ← назад
        </button>
      </div>
    )
  }

  const activeSubs = (task.subtasks || []).filter((s) => !s.done && !completedSubs.has(s.id))
  const totalSubs = (task.subtasks || []).length
  const doneSubs = totalSubs - activeSubs.length

  const handleDone = () => {
    setCompleting(true)
    setTimeout(() => onDone(task.id), 300)
  }

  const handleSubCheck = (id) => {
    setCompletedSubs((prev) => new Set([...prev, id]))
  }

  const handleSplitSubmit = () => {
    const lines = splitText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (lines.length > 0) onSplit(task.id, lines)
    setSplitMode(false)
    setSplitText('')
  }

  return (
    <div className="focus-mode">
      <button className="btn-back" onClick={onBack}>
        ← список
      </button>

      <div className={`focus-card ${completing ? 'focus-completing' : ''}`}>
        {queueLength > 1 && (
          <span className="focus-queue">задача 1 из {queueLength}</span>
        )}
        <h2 className="focus-task-text">{task.text}</h2>

        {activeSubs.length > 0 && (
          <ul className="focus-subtasks">
            {activeSubs.map((sub) => (
              <li
                key={sub.id}
                className={`focus-sub ${completedSubs.has(sub.id) ? 'focus-sub-done' : ''}`}
              >
                <button
                  className="sub-check"
                  onClick={() => handleSubCheck(sub.id)}
                  aria-label="Шаг выполнен"
                />
                <span>{sub.text}</span>
              </li>
            ))}
          </ul>
        )}

        {totalSubs > 0 && doneSubs > 0 && (
          <div className="sub-progress">
            {doneSubs} / {totalSubs} шагов
          </div>
        )}
      </div>

      {splitMode ? (
        <div className="split-panel">
          <p className="split-hint">Разбей на шаги (каждый с новой строки):</p>
          <textarea
            className="split-textarea"
            value={splitText}
            onChange={(e) => setSplitText(e.target.value)}
            placeholder={'Открыть ноутбук\nНайти нужный файл\nНаписать первый абзац'}
            autoFocus
            rows={4}
          />
          <div className="split-actions">
            <button className="btn-primary" onClick={handleSplitSubmit}>
              Добавить шаги
            </button>
            <button className="btn-secondary" onClick={() => setSplitMode(false)}>
              Отмена
            </button>
          </div>
        </div>
      ) : (
        <div className="focus-actions">
          <button className="btn-done" onClick={handleDone}>
            ✓ Сделал
          </button>
          <button className="btn-split" onClick={() => setSplitMode(true)}>
            ⊕ Разбить
          </button>
          <button className="btn-skip" onClick={() => onSkip(task.id)}>
            → Пропустить
          </button>
        </div>
      )}
    </div>
  )
}
