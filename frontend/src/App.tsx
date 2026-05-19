import { useState, useEffect, useCallback, useRef } from 'react'
import type { Task, Screen } from './types'
import { api } from './api'
import { useTasks } from './hooks/useTasks'
import { useTimer } from './hooks/useTimer'
import Header from './components/Header'
import NowBlock from './components/NowBlock'
import QueueBlock from './components/QueueBlock'
import DirectionsPanel from './components/DirectionsPanel'
import TaskEditor from './components/TaskEditor'
import AfterDoneModal from './components/modals/AfterDoneModal'
import TimerSwitchModal from './components/modals/TimerSwitchModal'
import CheckinModal from './components/modals/CheckinModal'
import FocusSwitchModal from './components/modals/FocusSwitchModal'
import EveningSummaryModal from './components/modals/EveningSummaryModal'
import SessionNoteModal from './components/modals/SessionNoteModal'
import SettingsScreen from './components/SettingsScreen'
import ArchiveScreen from './components/ArchiveScreen'
import TrashScreen from './components/TrashScreen'
import StatsScreen from './components/StatsScreen'
import JournalScreen from './components/JournalScreen'

export default function App() {
  const [screen, setScreen] = useState<Screen>('main')
  const [selectedTask, setSelectedTask] = useState<Task | null | undefined>(undefined) // undefined = closed, null = new, Task = edit
  const [showCheckin, setShowCheckin] = useState(false)
  const [showAfterDone, setShowAfterDone] = useState(false)
  const [showTimerSwitch, setShowTimerSwitch] = useState(false)
  const [pendingSwitchTaskId, setPendingSwitchTaskId] = useState<number | null>(null)
  const [pendingFocusTask, setPendingFocusTask] = useState<Task | null>(null)
  const [showFocusSwitch, setShowFocusSwitch] = useState(false)
  const [showEveningSummary, setShowEveningSummary] = useState(false)
  const [postStopSessionId, setPostStopSessionId] = useState<number | null>(null)
  const [todayTime, setTodayTime] = useState(0)
  const quickInputRef = useRef<HTMLInputElement | null>(null)

  const { tasks, directions, refresh, updateTask, deleteTask, takeNow, reorderTasks, undo } = useTasks()

  const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at) ?? null
  const queueTasks = tasks.filter(t => t.slot === 'queue' && !t.done_at && !t.deleted_at)

  const { timerState, start, pause, resume, stop } = useTimer()

  // Load today time for now task
  useEffect(() => {
    if (!nowTask) { setTodayTime(0); return }
    api.getTodayTime(nowTask.id).then(r => setTodayTime(r.total)).catch(() => setTodayTime(0))
  }, [nowTask?.id])

  // Show checkin modal if no checkin recorded today
  useEffect(() => {
    api.getTodayCheckin().then(r => {
      if (!r.exists) setShowCheckin(true)
    }).catch(() => {})
  }, [])

  // Show evening summary after 19:00
  useEffect(() => {
    const check = () => {
      const now = new Date()
      if (now.getHours() < 19) return
      const today = now.toISOString().slice(0, 10)
      if (localStorage.getItem('evening_summary_date') === today) return
      setShowEveningSummary(true)
      localStorage.setItem('evening_summary_date', today)
    }
    check()
    const id = setInterval(check, 60_000)
    return () => clearInterval(id)
  }, [])

  // Space shortcut for timer; Cmd+Z/Ctrl+Z for undo
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' && e.target === document.body) {
        e.preventDefault()
        if (!nowTask) return
        if (timerState.isRunning) pause()
        else if (timerState.isPaused) resume()
        else start(nowTask.id)
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
        const tag = (e.target as HTMLElement)?.tagName
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          e.preventDefault()
          undo()
        }
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [timerState.isRunning, timerState.isPaused, nowTask, stop, start, pause, resume, undo])

  const handleTaskClick = useCallback((task: Task) => {
    if ((timerState.isRunning || timerState.isPaused) && nowTask && task.id !== nowTask.id) {
      setPendingFocusTask(task)
      setShowFocusSwitch(true)
      return
    }
    setSelectedTask(task)
  }, [timerState.isRunning, timerState.isPaused, nowTask])

  const handleStartTimer = useCallback(() => {
    if (!nowTask) return
    start(nowTask.id)
  }, [nowTask, start])

  const handlePauseTimer = useCallback(() => { pause() }, [pause])
  const handleResumeTimer = useCallback(() => { resume() }, [resume])

  const handleStopTimer = useCallback(async () => {
    const { sessionId } = await stop()
    if (sessionId !== null) setPostStopSessionId(sessionId)
  }, [stop])

  const handleDoneNow = useCallback(async () => {
    if (!nowTask) return
    let stoppedSessionId: number | null = null
    if (timerState.isRunning || timerState.isPaused) {
      const { sessionId } = await stop()
      stoppedSessionId = sessionId
    }
    await updateTask(nowTask.id, { slot: 'queue', done_at: new Date().toISOString() })
    if (stoppedSessionId !== null) setPostStopSessionId(stoppedSessionId)
    setShowAfterDone(true)
  }, [nowTask, timerState.isRunning, timerState.isPaused, stop, updateTask])

  const handleTakeNow = useCallback(async (taskId: number) => {
    if (timerState.isRunning) {
      setPendingSwitchTaskId(taskId)
      setShowTimerSwitch(true)
      return
    }
    await takeNow(taskId)
    setSelectedTask(undefined)
  }, [timerState.isRunning, takeNow])

  const handleTimerSwitchConfirm = useCallback(async () => {
    setShowTimerSwitch(false)
    await stop()
    if (pendingSwitchTaskId !== null) {
      await takeNow(pendingSwitchTaskId)
      setPendingSwitchTaskId(null)
    }
  }, [stop, takeNow, pendingSwitchTaskId])

  const handleAfterDoneStartNext = useCallback(async (taskId: number) => {
    setShowAfterDone(false)
    await takeNow(taskId)
  }, [takeNow])

  const handleCheckinSave = useCallback(async (mood: number, goal: string, content: string) => {
    try {
      await api.createJournalEntry({ type: 'checkin', mood, goal, content })
    } catch (e) { console.error(e) }
    setShowCheckin(false)
  }, [])

  const handleOpenNewTask = useCallback(() => {
    setSelectedTask(null)
  }, [])

  // DnD handlers
  const handleDropToNow = useCallback(async (taskId: number) => {
    await handleTakeNow(taskId)
  }, [handleTakeNow])

  const handleDropToQueue = useCallback(async (taskId: number) => {
    await updateTask(taskId, { slot: 'queue' })
  }, [updateTask])

  const handleMoveToQueue = useCallback(async (taskId: number) => {
    await updateTask(taskId, { slot: 'queue' })
  }, [updateTask])

  const handleAddToQueue = useCallback(async (taskId: number) => {
    const task = tasks.find(t => t.id === taskId)
    const update: any = { in_queue: true }
    if (task?.slot === 'now') update.slot = 'queue'
    await updateTask(taskId, update)
  }, [updateTask, tasks])

  const handleRemoveFromQueue = useCallback(async (taskId: number) => {
    await updateTask(taskId, { in_queue: false } as any)
  }, [updateTask])

  const handlePriorityChange = useCallback(async (taskId: number, priority: string) => {
    await updateTask(taskId, { priority } as any)
  }, [updateTask])

  const handleFocusSwitchConfirm = useCallback(() => {
    setShowFocusSwitch(false)
    if (pendingFocusTask) setSelectedTask(pendingFocusTask)
    setPendingFocusTask(null)
  }, [pendingFocusTask])

  const handleReorderInDirection = useCallback(async (directionId: number | null, orderedIds: number[]) => {
    await api.reorderInDirection(directionId, orderedIds)
    await refresh()
  }, [refresh])

  const handleMoveToTomorrow = useCallback(async (taskId: number) => {
    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    const tomorrowStr = tomorrow.toISOString().slice(0, 10)
    await updateTask(taskId, { deadline: tomorrowStr })
  }, [updateTask])

  return (
    <div className="h-screen flex flex-col bg-[#181818] text-[#f0f0f0] overflow-hidden">
      <Header
        onNavigate={s => setScreen(s)}
        onTaskCreated={refresh}
        onOpenEditor={(id) => {
          const t = tasks.find(x => x.id === id)
          if (t) setSelectedTask(t)
        }}
        onEndDay={() => setShowEveningSummary(true)}
        isTimerActive={timerState.isRunning || timerState.isPaused}
      />

      <div className="flex-1 overflow-hidden">
        {screen === 'main' && (
          <div className="h-full flex gap-0">
            {/* Left column */}
            <div className="w-[58%] flex flex-col gap-3 p-4 overflow-y-auto border-r border-[#252525]">
              <NowBlock
                task={nowTask}
                directions={directions}
                timer={timerState}
                todayTime={todayTime}
                onStart={handleStartTimer}
                onPause={handlePauseTimer}
                onResume={handleResumeTimer}
                onStop={handleStopTimer}
                onDone={handleDoneNow}
                onTaskClick={handleTaskClick}
                onAddTask={handleOpenNewTask}
                onDropTask={handleDropToNow}
              />
              <QueueBlock
                tasks={tasks}
                directions={directions}
                onTaskClick={handleTaskClick}
                onReorder={reorderTasks}
                onDropFromOutside={handleAddToQueue}
                onRemoveFromQueue={handleRemoveFromQueue}
                focusMode={timerState.isRunning || timerState.isPaused}
                nowTaskId={nowTask?.id}
              />
              <div className="flex-1" />
            </div>

            {/* Right column */}
            <div className={`w-[42%] p-4 overflow-hidden transition-all ${(timerState.isRunning || timerState.isPaused) ? 'opacity-30 blur-[3px] pointer-events-none' : ''}`}>
              <DirectionsPanel
                tasks={tasks}
                directions={directions}
                onTaskClick={handleTaskClick}
                onReorder={reorderTasks}
                onReorderInDirection={handleReorderInDirection}
                onMoveToQueue={handleMoveToQueue}
                onAddToQueue={handleAddToQueue}
                onPriorityChange={handlePriorityChange}
                focusMode={timerState.isRunning || timerState.isPaused}
                nowTaskId={nowTask?.id}
              />
            </div>
          </div>
        )}

        {screen === 'settings' && (
          <SettingsScreen
            directions={directions}
            onClose={() => setScreen('main')}
            onDirectionChange={refresh}
            onNavigate={(s) => setScreen(s)}
          />
        )}

        {screen === 'archive' && (
          <ArchiveScreen
            directions={directions}
            onClose={() => setScreen('main')}
          />
        )}

        {screen === 'trash' && (
          <TrashScreen
            onClose={() => setScreen('main')}
            onRestored={refresh}
          />
        )}

        {screen === 'stats' && (
          <StatsScreen onClose={() => setScreen('main')} />
        )}

        {screen === 'journal' && (
          <JournalScreen onClose={() => setScreen('main')} />
        )}
      </div>

      {/* Task Editor */}
      {selectedTask !== undefined && (
        <TaskEditor
          task={selectedTask}
          directions={directions}
          onClose={() => setSelectedTask(undefined)}
          onSaved={async () => { await refresh(); setSelectedTask(undefined) }}
          onDeleted={async () => { await refresh(); setSelectedTask(undefined) }}
          onTakenNow={() => {
            if (selectedTask) handleTakeNow(selectedTask.id)
          }}
        />
      )}

      {/* Modals */}
      {showAfterDone && (
        <AfterDoneModal
          queueTasks={queueTasks}
          onStartNext={handleAfterDoneStartNext}
          onChoose={() => { setShowAfterDone(false); setSelectedTask(null) }}
          onLeaveEmpty={() => setShowAfterDone(false)}
        />
      )}

      {showTimerSwitch && (
        <TimerSwitchModal
          onCancel={() => { setShowTimerSwitch(false); setPendingSwitchTaskId(null) }}
          onConfirm={handleTimerSwitchConfirm}
        />
      )}

      {showCheckin && (
        <CheckinModal
          onClose={() => setShowCheckin(false)}
          onSave={handleCheckinSave}
        />
      )}

      {showFocusSwitch && pendingFocusTask && (
        <FocusSwitchModal
          taskTitle={pendingFocusTask.title}
          onStay={() => { setShowFocusSwitch(false); setPendingFocusTask(null) }}
          onSwitch={handleFocusSwitchConfirm}
        />
      )}

      {showEveningSummary && (
        <EveningSummaryModal
          incompleteTasks={tasks.filter(t => !t.done_at && !t.deleted_at)}
          onClose={() => setShowEveningSummary(false)}
          onLater={() => setShowEveningSummary(false)}
          onMoveToTomorrow={handleMoveToTomorrow}
        />
      )}

      {postStopSessionId !== null && (
        <SessionNoteModal
          sessionId={postStopSessionId}
          onClose={() => setPostStopSessionId(null)}
        />
      )}
    </div>
  )
}
