// Спринт = неделя дедлайна (пн–вс). Раскладка по спринтам зашита в дедлайны задач,
// поэтому группируем по неделе, в которую попадает deadline. Одна логика на все экраны.

export function localKey(dt: Date): string {
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`
}

// Понедельник недели, в которую попадает дата (ISO-неделя, пн–вс).
export function mondayOf(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  const dt = new Date(y, m - 1, d); dt.setHours(0, 0, 0, 0)
  const day = (dt.getDay() + 6) % 7 // 0 = понедельник
  dt.setDate(dt.getDate() - day)
  return dt
}

export function fmtDM(dt: Date): string {
  return `${String(dt.getDate()).padStart(2, '0')}.${String(dt.getMonth() + 1).padStart(2, '0')}`
}

// Ключ понедельника текущей недели — для подсветки «сейчас».
export function thisMondayKey(): string {
  return localKey(mondayOf(localKey(new Date())))
}

export interface SprintGroup<T> { key: string; monday: Date; tasks: T[] }

// Группировка задач по спринтам. Возвращает отсортированные недели + задачи без срока.
export function groupBySprint<T extends { deadline?: string | null }>(
  tasks: T[],
): { groups: SprintGroup<T>[]; noDl: T[] } {
  const map = new Map<string, { monday: Date; tasks: T[] }>()
  const noDl: T[] = []
  tasks.forEach(t => {
    if (!t.deadline) { noDl.push(t); return }
    const monday = mondayOf(t.deadline)
    const key = localKey(monday)
    if (!map.has(key)) map.set(key, { monday, tasks: [] })
    map.get(key)!.tasks.push(t)
  })
  const groups = [...map.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .map(([key, v]) => ({ key, monday: v.monday, tasks: v.tasks }))
  return { groups, noDl }
}
