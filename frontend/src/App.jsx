import { useState, useEffect, useCallback } from 'react'
import TaskInput from './components/TaskInput'
import TaskList from './components/TaskList'
import FocusMode from './components/FocusMode'
import PomodoroTimer from './components/PomodoroTimer'
import { fetchTasks, createTask, updateTask, deleteTask, syncLS } from './api'

const MAX_ACTIVE = 5

const getToday = () => new Date().toISOString().split('T')[0]

const loadDaily = () => {
  try {
    const saved = JSON.parse(localStorage.getItem('adhd_daily') || '{}')
    return saved.date === getToday() ? saved : { date: getToday(), count: 0 }
  } catch {
    return { date: getToday(), count: 0 }
  }
}

export default function App() {
  const [tasks, setTasks] = useState([])
  const [view, setView] = useState('list') // 'list' | 'focus'
  const [focusId, setFocusId] = useState(null)
  const [daily, setDaily] = useState(loadDaily)

  // Load tasks on mount
  useEffect(() => {
    fetchTasks().then(setTasks)
  }, [])

  // Auto-save to localStorage whenever tasks change
  useEffect(() => {
    syncLS(tasks)
  }, [tasks])

  // Persist daily counter
  useEffect(() => {
    localStorage.setItem('adhd_daily', JSON.stringify(daily))
  }, [daily])

  const activeTasks = tasks.filter((t) => !t.done)

  // Resolve which task is currently focused
  const focusTask = focusId
    ? (tasks.find((t) => t.id === focusId && !t.done) ?? activeTasks[0])
    : activeTasks[0]

  // ── Add ────────────────────────────────────────────────────────────────────
  const handleAdd = useCallback(
    async (text) => {
      if (activeTasks.length >= MAX_ACTIVE) return

      // Optimistic: add with tmp id immediately
      const optimistic = {
        id: 'tmp_' + Date.now(),
        text,
        done: false,
        subtasks: [],
        createdAt: Date.now(),
      }
      setTasks((prev) => [...prev, optimistic])

      // Replace with server response (real id)
      const real = await createTask(text)
      setTasks((prev) =>
        prev.map((t) => (t.id === optimistic.id ? real : t))
      )
    },
    [activeTasks.length]
  )

  // ── Done ───────────────────────────────────────────────────────────────────
  const handleDone = useCallback(
    async (id) => {
      setTasks((prev) => prev.map((t) => (t.id === id ? { ...t, done: true } : t)))
      setDaily((d) => ({ date: d.date, count: d.count + 1 }))

      const remaining = activeTasks.filter((t) => t.id !== id)
      if (remaining.length === 0) {
        setView('list')
        setFocusId(null)
      } else {
        setFocusId(remaining[0].id)
      }

      await updateTask(id, { done: true })
    },
    [activeTasks]
  )

  // ── Skip ───────────────────────────────────────────────────────────────────
  const handleSkip = useCallback(
    (id) => {
      setTasks((prev) => {
        const task = prev.find((t) => t.id === id)
        return [...prev.filter((t) => t.id !== id), task]
      })
      const remaining = activeTasks.filter((t) => t.id !== id)
      if (remaining.length > 0) {
        setFocusId(remaining[0].id)
      } else {
        setView('list')
        setFocusId(null)
      }
    },
    [activeTasks]
  )

  // ── Split ──────────────────────────────────────────────────────────────────
  const handleSplit = useCallback(
    async (id, subtexts) => {
      const newSubs = subtexts
        .filter(Boolean)
        .map((text, i) => ({
          id: `sub_${Date.now()}_${i}`,
          text,
          done: false,
        }))

      setTasks((prev) =>
        prev.map((t) =>
          t.id === id ? { ...t, subtasks: [...(t.subtasks || []), ...newSubs] } : t
        )
      )

      const task = tasks.find((t) => t.id === id)
      await updateTask(id, {
        subtasks: [...(task?.subtasks || []), ...newSubs],
      })
    },
    [tasks]
  )

  // ── Delete ─────────────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (id) => {
    setTasks((prev) => prev.filter((t) => t.id !== id))
    await deleteTask(id)
  }, [])

  // ── Random ─────────────────────────────────────────────────────────────────
  const handleRandom = useCallback(() => {
    if (activeTasks.length === 0) return
    const pick = activeTasks[Math.floor(Math.random() * activeTasks.length)]
    setFocusId(pick.id)
    setView('focus')
  }, [activeTasks])

  // ── Focus ──────────────────────────────────────────────────────────────────
  const handleFocus = useCallback((id) => {
    setFocusId(id)
    setView('focus')
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1 className="app-title">focus.</h1>
          {daily.count > 0 && (
            <span className="daily-count">✓ {daily.count} сегодня</span>
          )}
        </div>
        <PomodoroTimer />
      </header>

      <main className="app-main">
        {view === 'list' ? (
          <>
            <TaskInput
              onAdd={handleAdd}
              disabled={activeTasks.length >= MAX_ACTIVE}
              count={activeTasks.length}
              max={MAX_ACTIVE}
            />
            <TaskList
              tasks={tasks}
              onDone={handleDone}
              onDelete={handleDelete}
              onFocus={handleFocus}
              onRandom={handleRandom}
              dailyCount={daily.count}
            />
          </>
        ) : (
          <FocusMode
            key={focusTask?.id}
            task={focusTask}
            queueLength={activeTasks.length}
            onDone={handleDone}
            onSkip={handleSkip}
            onSplit={handleSplit}
            onBack={() => {
              setView('list')
              setFocusId(null)
            }}
          />
        )}
      </main>
    </div>
  )
}
