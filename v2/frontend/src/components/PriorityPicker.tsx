import { useEffect, useState } from 'react'
import { PRIORITY_OPTIONS, priorityLabel, priorityColor } from '../utils/priority'

// Приоритеты можно выключить в настройках — тогда бейджи не показываются
export const prioritiesOn = () => localStorage.getItem('show_priorities') !== 'false'

let pickerSeq = 0

export function PriorityPicker({ current, onChange, onClose }: {
  current: string
  onChange: (v: string) => void
  onClose: () => void
}) {
  const [id] = useState(() => `priority-picker-${++pickerSeq}`)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const el = document.getElementById(id)
      if (el && !el.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [onClose, id])

  return (
    <div
      id={id}
      className="absolute z-40 left-0 top-full mt-1 card-raised py-1 min-w-[56px] animate-scale-in"
      onMouseDown={e => e.stopPropagation()}
    >
      {PRIORITY_OPTIONS.map(o => (
        <button
          key={o.value}
          onClick={e => { e.stopPropagation(); onChange(o.value); onClose() }}
          className={`flex items-center justify-center w-full px-3 py-1 text-xs hover:bg-border-strong transition-colors ${current === o.value ? 'bg-border-strong' : ''}`}
          style={{ color: o.color }}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

// Clickable priority symbol + dropdown picker — reusable across blocks
export function PriorityBadge({ priority, onChange }: {
  priority: string
  onChange: (v: string) => void
}) {
  const [open, setOpen] = useState(false)
  const isNone = !priority || priority === 'none'

  if (!prioritiesOn()) return null

  return (
    <div className="relative shrink-0">
      <button
        onClick={e => { e.stopPropagation(); setOpen(v => !v) }}
        className={`text-[11px] font-mono w-4 text-center leading-none transition-opacity ${isNone ? 'opacity-0 group-hover:opacity-100' : ''}`}
        style={{ color: priorityColor(priority) }}
        title="Приоритет"
      >
        {priorityLabel(priority)}
      </button>
      {open && (
        <PriorityPicker
          current={priority}
          onChange={onChange}
          onClose={() => setOpen(false)}
        />
      )}
    </div>
  )
}
