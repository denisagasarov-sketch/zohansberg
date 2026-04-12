import { useState } from 'react'

export default function TaskInput({ onAdd, disabled, count, max }) {
  const [value, setValue] = useState('')

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && value.trim()) {
      onAdd(value.trim())
      setValue('')
    }
  }

  return (
    <div className="task-input-wrapper">
      <input
        className="task-input"
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={
          disabled
            ? `Сначала доделай что-нибудь (лимит ${max})`
            : 'Что нужно сделать?  Enter ↵'
        }
        disabled={disabled}
        autoFocus
        maxLength={140}
        autoComplete="off"
      />
      {count > 0 && (
        <span className={`task-count ${count >= max ? 'task-count-max' : ''}`}>
          {count}/{max}
        </span>
      )}
    </div>
  )
}
