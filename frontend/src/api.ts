// HTTP-клиент к Express-backend. Vite dev-сервер проксирует /api → :3001,
// статический сервер Electron делает то же самое (см. electron/main.js).
// Tauri-ветки удалены 2026-07-03 — Tauri-порт заброшен, приложение живёт на Electron.
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
  evictNow: () => req('POST', '/tasks/evict-now', {}),
  reorderTasks: (slot: string, ordered_ids: number[]) =>
    req('POST', '/tasks/reorder', { slot, ordered_ids }),
  resetOrder: (slot: string) => req('POST', '/tasks/reset-order', { slot }),
  getDoneTasks: (params?: { direction_id?: number; search?: string }) => {
    const qs = new URLSearchParams()
    if (params?.direction_id) qs.set('direction_id', String(params.direction_id))
    if (params?.search) qs.set('search', params.search)
    return req<any[]>('GET', `/tasks/done${qs.toString() ? '?' + qs : ''}`)
  },
  cleanupTrash: () => req('POST', '/tasks/cleanup-trash', {}),

  // Sessions
  startSession: (task_id: number, started_at: string) =>
    req<any>('POST', '/sessions', { task_id, started_at }),
  endSession: (id: number, ended_at: string, duration_actual: number) =>
    req('PATCH', `/sessions/${id}`, { ended_at, duration_actual }),
  heartbeatSession: (id: number, elapsed_seconds: number) =>
    req<{ ok: boolean }>('PATCH', `/sessions/${id}/heartbeat`, { elapsed_seconds }),
  getActiveSession: () =>
    req<{ id: number; task_id: number; elapsed_seconds: number } | null>('GET', '/sessions/active'),
  updateSessionNote: (id: number, note: string) => req('PATCH', `/sessions/${id}`, { note }),
  getTaskSessions: (task_id: number) => req<any[]>('GET', `/sessions/task/${task_id}`),
  createManualSession: (
    task_id: number,
    data: { started_at: string; ended_at: string; duration_seconds: number; note?: string },
  ) => req<any>('POST', `/tasks/${task_id}/sessions`, data),
  getTodayTime: (task_id: number) => req<{ total: number }>('GET', `/sessions/today/${task_id}`),
  getSessionStats: (period: string) => req<any>('GET', `/sessions/stats?period=${period}`),

  // Journal
  getJournal: () => req<any[]>('GET', '/journal'),
  createJournalEntry: (data: any) => req('POST', '/journal', data),
  getTodayCheckin: () =>
    req<{ exists: boolean; mood: number | null; goal: string | null; content: string | null }>('GET', '/journal/today-checkin'),

  // Settings
  getSettings: () => req<any>('GET', '/settings'),
  updateSetting: (key: string, value: string) => req('PATCH', '/settings', { key, value }),

  // Stats
  getStats: (period: string) => req<any>('GET', `/stats?period=${period}`),
  getWorklog: (period: string) => req<any>('GET', `/sessions/worklog?period=${period}`),
  getStatsDashboard: (period: string) => req<any>('GET', `/stats/dashboard?period=${period}`),
  getTodaySummary: () => req<any>('GET', '/today-summary'),
  getWeeklyTime: () => req<{ direction_id: number | null; seconds: number }[]>('GET', '/stats/weekly-time'),
  getWeeklySummary: () => req<any>('GET', '/weekly-summary'),
  getStandup: () => req<any>('GET', '/standup'),
  getMonthlySummary: (months: number) => req<any>('GET', `/monthly-summary?months=${months}`),

  // Day plan
  getDayPlan: (date: string) => req<any[]>('GET', `/day-plan?date=${date}`),
  setDayPlan: (date: string, task_ids: number[]) => req('POST', '/day-plan', { date, task_ids }),

  // AI
  reorderInDirection: (direction_id: number | null, ordered_ids: number[]) =>
    req('POST', '/tasks/reorder-direction', { direction_id, ordered_ids }),
  suggestTitle: (data: { title: string; direction?: string; deadline?: string; notes?: string; recentTasks?: string[] }) =>
    req<{ suggestions: string[] }>('POST', '/ai/suggest-title', data),
  parseTask: (text: string) =>
    req<{ title?: string; direction_id?: number | null; deadline?: string | null; duration_plan?: number | null }>('POST', '/ai/parse-task', { text }),
}
