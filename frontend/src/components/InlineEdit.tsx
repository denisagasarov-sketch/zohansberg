import { useState, useRef, useEffect } from 'react'

interface Props {
  value: string
  onSave: (v: string) => void
  className?: string
  placeholder?: string
  multiline?: boolean
}

export function InlineEdit({ value, onSave, className = '', placeholder, multiline }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const ref = useRef<HTMLInputElement & HTMLTextAreaElement>(null)

  useEffect(() => {
    if (editing) {
      ref.current?.focus()
      ref.current?.select()
    }
  }, [editing])

  const commit = () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== value) onSave(trimmed)
    else setDraft(value)
    setEditing(false)
  }

  const cancel = () => {
    setDraft(value)
    setEditing(false)
  }

  if (editing) {
    const sharedProps = {
      ref: ref as React.Ref<HTMLInputElement & HTMLTextAreaElement>,
      value: draft,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setDraft(e.target.value),
      onBlur: commit,
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !multiline) { e.preventDefault(); commit() }
        if (e.key === 'Escape') cancel()
      },
      className: `bg-[#18181b] border border-[#3b82f6]/60 rounded px-2 py-0.5 outline-none text-[#e8e8f0] w-full ${className}`,
      placeholder,
    }
    if (multiline) {
      return <textarea {...sharedProps} rows={3} style={{ resize: 'vertical' }} />
    }
    return <input {...sharedProps} type="text" />
  }

  return (
    <span
      onClick={() => { setDraft(value); setEditing(true) }}
      className={`cursor-text hover:bg-[#18181b] rounded px-1 -mx-1 transition-colors ${className}`}
      title="Click to edit"
    >
      {value || <span className="text-[#4a4a55]">{placeholder}</span>}
    </span>
  )
}
