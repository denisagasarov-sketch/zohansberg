const BASE = '/tasks'

// localStorage fallback
const LS = {
  get: () => {
    try {
      return JSON.parse(localStorage.getItem('adhd_tasks') || '[]')
    } catch {
      return []
    }
  },
  set: (tasks) => {
    try {
      localStorage.setItem('adhd_tasks', JSON.stringify(tasks))
    } catch {}
  },
}

export async function fetchTasks() {
  try {
    const res = await fetch(BASE)
    if (!res.ok) throw new Error()
    const data = await res.json()
    LS.set(data)
    return data
  } catch {
    return LS.get()
  }
}

export async function createTask(text) {
  // Optimistic: return immediately with a tmp id; caller replaces on success
  const optimistic = {
    id: 'tmp_' + Date.now(),
    text,
    done: false,
    subtasks: [],
    createdAt: Date.now(),
  }
  try {
    const res = await fetch(BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
    if (!res.ok) return optimistic
    return await res.json()
  } catch {
    return optimistic
  }
}

export async function updateTask(id, patch) {
  try {
    const res = await fetch(`${BASE}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!res.ok) throw new Error()
    return await res.json()
  } catch {
    return { id, ...patch }
  }
}

export async function deleteTask(id) {
  try {
    await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  } catch {
    // optimistic delete already applied in state
  }
}

export const syncLS = (tasks) => LS.set(tasks)
