// Произвольные, но стабильные цвета для задач на таймлайне — чтобы разные
// задачи легко различались. Цвет закреплён за id задачи (зелёный/янтарь/розовый
// не используем — они заняты маркерами исхода: шаг/задача/пауза/сейчас).
const TASK_PALETTE = [
  '#cf7d92', '#6f9bd6', '#9a86d0', '#5fb0ad', '#c98fb8', '#6aa0c4',
  '#b58a5f', '#8f97d8', '#5f97b0', '#cf8a6a', '#7d8ecf', '#b07fa0',
]

export function getTaskColor(taskId: number): string {
  const i = Math.abs(Math.floor(taskId)) % TASK_PALETTE.length
  return TASK_PALETTE[i]
}
