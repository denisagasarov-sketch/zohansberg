export const PRIORITY_OPTIONS = [
  { value: 'I',    label: 'Ⅰ', color: '#F97316' },
  { value: 'II',   label: 'Ⅱ', color: '#94A3B8' },
  { value: 'III',  label: 'Ⅲ', color: '#475569' },
  { value: 'none', label: '–', color: '#555'     },
] as const

export function priorityLabel(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.label ?? '–' }
export function priorityColor(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.color ?? '#555' }
