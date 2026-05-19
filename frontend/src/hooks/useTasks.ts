import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api'
import type { Task, Direction } from '../types'

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [directions, setDirections] = useState<Direction[]>([])
  const [loading, setLoading] = useState(true)
  const undoStack = useRef<Array<() => Promise<void>>>([])

  const refresh = useCallback(async () => {
    try {
      const [t, d] = await Promise.all([api.getTasks(), api.getDirections()])
      setTasks(t as Task[])
      setDirections(d as Direction[])
    } catch (e) {
      console.error('Failed to load tasks/directions', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  function pushUndo(fn: () => Promise<void>) {
    undoStack.current = [fn, ...undoStack.current].slice(0, 20)
  }

  const undo = useCallback(async () => {
    const fn = undoStack.current.shift()
    if (fn) { await fn(); await refresh() }
  }, [refresh])

  const createTask = useCallback(async (data: Partial<Task>): Promise<Task> => {
    const task = await api.createTask(data) as Task
    pushUndo(async () => { await api.deleteTask(task.id) })
    await refresh()
    return task
  }, [refresh])

  const updateTask = useCallback(async (id: number, data: Partial<Task>): Promise<void> => {
    const prev = tasks.find(t => t.id === id)
    if (prev) {
      const snapshot: Partial<Task> = {
        title: prev.title, direction_id: prev.direction_id, deadline: prev.deadline,
        duration_plan: prev.duration_plan, notes: prev.notes, slot: prev.slot,
        done_at: prev.done_at,
      }
      pushUndo(async () => { await api.updateTask(id, snapshot) })
    }
    await api.updateTask(id, data)
    await refresh()
  }, [refresh, tasks])

  const deleteTask = useCallback(async (id: number): Promise<void> => {
    pushUndo(async () => { await api.restoreTask(id) })
    await api.deleteTask(id)
    await refresh()
  }, [refresh])

  const takeNow = useCallback(async (taskId: number): Promise<void> => {
    const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at)
    const prevNowId = nowTask?.id ?? null
    pushUndo(async () => {
      await api.updateTask(taskId, { slot: 'queue' })
      if (prevNowId) await api.updateTask(prevNowId, { slot: 'now' })
    })
    await api.takeNow(taskId)
    await refresh()
  }, [refresh, tasks])

  const reorderTasks = useCallback(async (slot: string, orderedIds: number[]): Promise<void> => {
    await api.reorderTasks(slot, orderedIds)
    await refresh()
  }, [refresh])

  return { tasks, directions, loading, refresh, createTask, updateTask, deleteTask, takeNow, reorderTasks, undo }
}
