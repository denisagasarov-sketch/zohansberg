export const PRIORITY_OPTIONS = [
  { value: 'I',    label: 'Ⅰ', color: '#e0813f' },
  { value: 'II',   label: 'Ⅱ', color: '#a8a296' },
  { value: 'III',  label: 'Ⅲ', color: '#6b6459' },
  { value: 'none', label: '–', color: '#57534b' },
] as const

export function priorityLabel(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.label ?? '–' }
export function priorityColor(p: string) { return PRIORITY_OPTIONS.find(o => o.value === p)?.color ?? '#57534b' }
