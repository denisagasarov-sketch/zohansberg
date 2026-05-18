import { useRef, useCallback } from 'react'

// Lightweight global drag tracking via dataTransfer — no context needed.
// Call onDragStart on the draggable element, onDrop on drop targets.

export const DRAG_TASK_KEY = 'focusboard/taskId'

export function useDragDrop() {
  const draggingIdRef = useRef<number | null>(null)

  const getDragId = useCallback((e: React.DragEvent): number | null => {
    const raw = e.dataTransfer.getData(DRAG_TASK_KEY)
    const id = parseInt(raw, 10)
    return isNaN(id) ? null : id
  }, [])

  const setDragId = useCallback((e: React.DragEvent, taskId: number) => {
    draggingIdRef.current = taskId
    e.dataTransfer.setData(DRAG_TASK_KEY, String(taskId))
    e.dataTransfer.effectAllowed = 'move'
  }, [])

  const clearDragId = useCallback(() => {
    draggingIdRef.current = null
  }, [])

  return { draggingIdRef, getDragId, setDragId, clearDragId }
}
