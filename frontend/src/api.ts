// Detect Tauri environment
const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window

async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (isTauri) {
    const { invoke: tauriInvoke } = await import('@tauri-apps/api/core')
    return tauriInvoke<T>(cmd, args)
  }
  throw new Error('Not in Tauri environment')
}

// HTTP fallback for browser dev mode (Express backend)
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
  getDirections: () =>
    isTauri ? invoke<any[]>('get_directions') : req<any[]>('GET', '/directions'),
  getAllDirections: () =>
    isTauri ? invoke<any[]>('get_all_directions') : req<any[]>('GET', '/directions/all'),
  createDirection: (name: string) =>
    isTauri ? invoke('create_direction', { name }) : req('POST', '/directions', { name }),
  updateDirection: (id: number, data: any) =>
    isTauri ? invoke('update_direction', { id, ...data }) : req('PATCH', `/directions/${id}`, data),
  archiveDirection: (id: number) =>
    isTauri ? invoke('archive_direction', { id }) : req('DELETE', `/directions/${id}`),

  // Tasks
  getTasks: () =>
    isTauri ? invoke<any[]>('get_tasks') : req<any[]>('GET', '/tasks'),
  createTask: (data: any) =>
    isTauri ? invoke('create_task', data) : req('POST', '/tasks', data),
  updateTask: (id: number, data: any) =>
    isTauri ? invoke('update_task', { id, input: data }) : req('PATCH', `/tasks/${id}`, data),
  deleteTask: (id: number) =>
    isTauri ? invoke('delete_task', { id }) : req('DELETE', `/tasks/${id}`),
  getTrash: () =>
    isTauri ? invoke<any[]>('get_trash') : req<any[]>('GET', '/tasks/trash'),
  restoreTask: (id: number) =>
    isTauri ? invoke('restore_task', { id }) : req('POST', `/tasks/${id}/restore`, {}),
  takeNow: (task_id: number) =>
    isTauri ? invoke('take_now', { taskId: task_id }) : req('POST', '/tasks/take-now', { task_id }),
  reorderTasks: (slot: string, ordered_ids: number[]) =>
    isTauri ? invoke('reorder_tasks', { slot, orderedIds: ordered_ids }) : req('POST', '/tasks/reorder', { slot, ordered_ids }),
  resetOrder: (slot: string) =>
    isTauri ? invoke('reset_order', { slot }) : req('POST', '/tasks/reset-order', { slot }),
  getDoneTasks: (params?: { direction_id?: number; search?: string }) => {
    if (isTauri) return invoke<any[]>('get_done_tasks', { directionId: params?.direction_id, search: params?.search })
    const qs = new URLSearchParams()
    if (params?.direction_id) qs.set('direction_id', String(params.direction_id))
    if (params?.search) qs.set('search', params.search)
    return req<any[]>('GET', `/tasks/done${qs.toString() ? '?' + qs : ''}`)
  },
  cleanupTrash: () =>
    isTauri ? invoke('cleanup_trash') : req('POST', '/tasks/cleanup-trash', {}),

  // Sessions
  startSession: (task_id: number, started_at: string) =>
    isTauri ? invoke<any>('start_session', { taskId: task_id, startedAt: started_at }) : req<any>('POST', '/sessions', { task_id, started_at }),
  endSession: (id: number, ended_at: string, duration_actual: number) =>
    isTauri ? invoke('end_session', { id, endedAt: ended_at, durationActual: duration_actual }) : req('PATCH', `/sessions/${id}`, { ended_at, duration_actual }),
  getTodayTime: (task_id: number) =>
    isTauri
      ? invoke<number>('get_today_time', { taskId: task_id }).then(total => ({ total }))
      : req<{ total: number }>('GET', `/sessions/today/${task_id}`),
  getSessionStats: (period: string) =>
    isTauri ? invoke<any>('get_session_stats', { period }) : req<any>('GET', `/sessions/stats?period=${period}`),

  // Journal
  getJournal: () =>
    isTauri ? invoke<any[]>('get_journal') : req<any[]>('GET', '/journal'),
  createJournalEntry: (data: any) =>
    isTauri
      ? invoke('create_journal_entry', { entryType: data.type, mood: data.mood, goal: data.goal, content: data.content })
      : req('POST', '/journal', data),
  getTodayCheckin: () =>
    isTauri
      ? invoke<boolean>('get_today_checkin').then(exists => ({ exists }))
      : req<{ exists: boolean }>('GET', '/journal/today-checkin'),

  // Settings
  getSettings: () =>
    isTauri ? invoke<any>('get_settings') : req<any>('GET', '/settings'),
  updateSetting: (key: string, value: string) =>
    isTauri ? invoke('update_setting', { key, value }) : req('PATCH', '/settings', { key, value }),

  // Recommendation
  getRecommendation: (skip_id?: number) =>
    isTauri
      ? invoke<any>('get_recommendation', { skipId: skip_id })
      : req<any>('GET', `/recommendation${skip_id ? '?skip_id=' + skip_id : ''}`),

  // Stats
  getStats: (period: string) =>
    isTauri ? invoke<any>('get_stats', { period }) : req<any>('GET', `/stats?period=${period}`),
  getWorklog: (period: string) =>
    req<any>('GET', `/sessions/worklog?period=${period}`),
  getStatsDashboard: (period: string) =>
    req<any>('GET', `/stats/dashboard?period=${period}`),
  getTodaySummary: () =>
    req<any>('GET', '/today-summary'),
}
