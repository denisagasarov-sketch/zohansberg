export interface Quadrant {
  label: string
  short: string
  color: string
  border: string
}

export function getQuadrant(isImportant: number, isUrgent: number): Quadrant {
  if (isImportant && isUrgent)   return { label: 'Сделать сейчас', short: 'DO',   color: '#b05050', border: '#7a2020' }
  if (isImportant && !isUrgent)  return { label: 'Запланировать',  short: 'PLAN', color: '#5060a0', border: '#3040a0' }
  if (!isImportant && isUrgent)  return { label: 'Делегировать',   short: 'DEL',  color: '#a07030', border: '#8a5010' }
  return                                { label: 'Удалить',         short: 'DROP', color: '#505050', border: '#303030' }
}

/** Compute urgency from deadline: today/overdue/tomorrow/day-after-tomorrow → 1, else → 0 */
export function computeUrgency(deadline: string | null | undefined): number {
  if (!deadline) return 0
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const d = new Date(deadline)
  d.setHours(0, 0, 0, 0)
  const diffDays = Math.floor((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24))
  return diffDays <= 2 ? 1 : 0
}

/** Auto-determine slot from matrix (for non-someday tasks) */
export function computeMatrixSlot(isImportant: number, isUrgent: number): 'now' | 'next' | 'later' {
  if (isImportant && isUrgent) return 'now'
  if (isImportant && !isUrgent) return 'next'
  return 'later'
}
