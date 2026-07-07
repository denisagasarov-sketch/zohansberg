import { useState, useEffect, useCallback } from 'react'
import type { Task } from '../types'
import { api } from '../api'

interface Props {
  onClose: () => void
  onRestored: () => void
}

export default function TrashScreen({ onClose, onRestored }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.getTrash() as Task[]
      setTasks(data)
    } catch (e) { console.error(e) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRestore = async (id: number) => {
    try {
      await api.restoreTask(id)
      await load()
      onRestored()
    } catch (e) { console.error(e) }
  }

  const handleCleanup = async () => {
    if (!window.confirm('Очистить задачи старше 30 дней?')) return
    try {
      await api.cleanupTrash()
      await load()
    } catch (e) { console.error(e) }
  }

  return (
    <div className="h-full flex flex-col bg-[#141312] text-[#ece7df]">
      <div className="flex items-center gap-3 px-6 py-3.5 border-b border-border bg-header/40 shrink-0">
        <button onClick={onClose} className="btn-ghost -ml-2 !px-2 !py-1 text-[13px]">← Назад</button>
        <h1 className="text-[17px] font-semibold tracking-tight flex-1">Корзина</h1>
        {tasks.length > 0 && (
          <button onClick={handleCleanup} className="text-xs text-[#9c958a] hover:text-red-400 transition-colors">Очистить корзину</button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && <div className="text-[#9c958a] text-sm">Загрузка…</div>}
        {!loading && tasks.length === 0 && (
          <div className="text-[#9c958a] text-sm">Корзина пуста</div>
        )}
        {!loading && tasks.length > 0 && (
          <div className="space-y-1">
            {tasks.map(task => (
              <div key={task.id} className="bg-[#1b1a18] border border-[#2a2723] rounded px-3 py-2 flex items-center gap-3">
                <span className="flex-1 text-sm text-[#9c958a] line-through">{task.title}</span>
                {task.deleted_at && (
                  <span className="text-xs text-[#4a463f]">
                    {new Date(task.deleted_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                  </span>
                )}
                <button
                  onClick={() => handleRestore(task.id)}
                  className="text-xs text-[#e0a458] hover:text-[#eab26c] transition-colors"
                >
                  Восстановить
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
