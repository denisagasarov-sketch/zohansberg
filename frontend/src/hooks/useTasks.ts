import { useState, useEffect, useCallback } from 'react'
import { api } from '../api'
import type { Task, Direction } from '../types'

export function useTasks() {
  const [tasks, setTasks] = useState<Task[]>([])
  const [directions, setDirections] = useState<Direction[]>([])
  const [loading, setLoading] = useState(true)

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

  useEffect(() => {
    refresh()
  }, [refresh])

  const createTask = useCallback(async (data: Partial<Task>): Promise<Task> => {
    const task = await api.createTask(data) as Task
    await refresh()
    return task
  }, [refresh])

  const updateTask = useCallback(async (id: number, data: Partial<Task>): Promise<void> => {
    await api.updateTask(id, data)
    await refresh()
  }, [refresh])

  const deleteTask = useCallback(async (id: number): Promise<void> => {
    await api.deleteTask(id)
    await refresh()
  }, [refresh])

  const takeNow = useCallback(async (taskId: number): Promise<void> => {
    await api.takeNow(taskId)
    await refresh()
  }, [refresh])

  const reorderTasks = useCallback(async (slot: string, orderedIds: number[]): Promise<void> => {
    await api.reorderTasks(slot, orderedIds)
    await refresh()
  }, [refresh])

  return { tasks, directions, loading, refresh, createTask, updateTask, deleteTask, takeNow, reorderTasks }
}
