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
