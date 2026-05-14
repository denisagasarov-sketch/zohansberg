const BASE = '/api'

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path}: ${res.status}`)
  return res.json()
}

export const api = {
  // Directions
  getDirections: () => req<any[]>('GET', '/directions'),
  getAllDirections: () => req<any[]>('GET', '/directions/all'),
  createDirection: (name: string) => req('POST', '/directions', { name }),
  updateDirection: (id: number, data: any) => req('PATCH', `/directions/${id}`, data),
  archiveDirection: (id: number) => req('DELETE', `/directions/${id}`),

  // Tasks
  getTasks: () => req<any[]>('GET', '/tasks'),
  createTask: (data: any) => req('POST', '/tasks', data),
  updateTask: (id: number, data: any) => req('PATCH', `/tasks/${id}`, data),
  deleteTask: (id: number) => req('DELETE', `/tasks/${id}`),
  getTrash: () => req<any[]>('GET', '/tasks/trash'),
  restoreTask: (id: number) => req('POST', `/tasks/${id}/restore`, {}),
  takeNow: (task_id: number) => req('POST', '/tasks/take-now', { task_id }),
  reorderTasks: (slot: string, ordered_ids: number[]) => req('POST', '/tasks/reorder', { slot, ordered_ids }),
  resetOrder: (slot: string) => req('POST', '/tasks/reset-order', { slot }),
  getDoneTasks: (params?: { direction_id?: number; search?: string }) => {
    const qs = new URLSearchParams()
    if (params?.direction_id) qs.set('direction_id', String(params.direction_id))
    if (params?.search) qs.set('search', params.search)
    return req<any[]>('GET', `/tasks/done${qs.toString() ? '?' + qs : ''}`)
  },
  cleanupTrash: () => req('POST', '/tasks/cleanup-trash', {}),

  // Sessions
  startSession: (task_id: number, started_at: string) => req<any>('POST', '/sessions', { task_id, started_at }),
  endSession: (id: number, ended_at: string, duration_actual: number) => req('PATCH', `/sessions/${id}`, { ended_at, duration_actual }),
  getTodayTime: (task_id: number) => req<{ total: number }>('GET', `/sessions/today/${task_id}`),
  getSessionStats: (period: string) => req<any>('GET', `/sessions/stats?period=${period}`),

  // Journal
  getJournal: () => req<any[]>('GET', '/journal'),
  createJournalEntry: (data: any) => req('POST', '/journal', data),
  getTodayCheckin: () => req<{ exists: boolean }>('GET', '/journal/today-checkin'),

  // Settings
  getSettings: () => req<any>('GET', '/settings'),
  updateSetting: (key: string, value: string) => req('PATCH', '/settings', { key, value }),

  // Recommendation
  getRecommendation: (skip_id?: number) => req<any>('GET', `/recommendation${skip_id ? '?skip_id=' + skip_id : ''}`),

  // Stats
  getStats: (period: string) => req<any>('GET', `/stats?period=${period}`),
}
