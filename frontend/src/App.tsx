import { useState, useEffect, useCallback, useRef } from 'react'
import type { Task, Screen } from './types'
import { api } from './api'
import { useTasks } from './hooks/useTasks'
import { useTimer } from './hooks/useTimer'
import { useRecommendation } from './hooks/useRecommendation'
import Header from './components/Header'
import NowBlock from './components/NowBlock'
import NextBlock from './components/NextBlock'
import RecBar from './components/RecBar'
import DirectionsPanel from './components/DirectionsPanel'
import MatrixScreen from './components/MatrixScreen'
import TaskEditor from './components/TaskEditor'
import AfterDoneModal from './components/modals/AfterDoneModal'
import TimerSwitchModal from './components/modals/TimerSwitchModal'
import CheckinModal from './components/modals/CheckinModal'
import FocusSwitchModal from './components/modals/FocusSwitchModal'
import EveningSummaryModal from './components/modals/EveningSummaryModal'
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
  const [todayTime, setTodayTime] = useState(0)
  const quickInputRef = useRef<HTMLInputElement | null>(null)

  const { tasks, directions, refresh, updateTask, deleteTask, takeNow, reorderTasks } = useTasks()
  const { recommendation, getNext, setAsNext } = useRecommendation()

  const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at) ?? null
  const nextTasks = tasks.filter(t => t.slot === 'next' && !t.done_at && !t.deleted_at)

  const { timerState, start, stop } = useTimer()

  // Load today time for now task
  useEffect(() => {
    if (!nowTask) { setTodayTime(0); return }
    api.getTodayTime(nowTask.id).then(r => setTodayTime(r.total)).catch(() => setTodayTime(0))
  }, [nowTask?.id])

  // Recalculate urgency from deadlines on mount, then refresh
  useEffect(() => {
    api.recalculateUrgency().then(() => refresh()).catch(() => {})
  }, [])

  // Load recommendation on mount
  useEffect(() => {
    getNext()
  }, [getNext])

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

  // Space shortcut for timer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' && e.target === document.body) {
        e.preventDefault()
        if (!nowTask) return
        if (timerState.isRunning) stop()
        else start(nowTask.id)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [timerState.isRunning, nowTask, stop, start])

  const handleTaskClick = useCallback((task: Task) => {
    if (timerState.isRunning && nowTask && task.id !== nowTask.id) {
      setPendingFocusTask(task)
      setShowFocusSwitch(true)
      return
    }
    setSelectedTask(task)
  }, [timerState.isRunning, nowTask])

  const handleStartTimer = useCallback(() => {
    if (!nowTask) return
    start(nowTask.id)
  }, [nowTask, start])

  const handleStopTimer = useCallback(() => {
    stop()
  }, [stop])

  const handleDoneNow = useCallback(async () => {
    if (!nowTask) return
    if (timerState.isRunning) await stop()
    await updateTask(nowTask.id, { status: 'done', slot: 'later', done_at: new Date().toISOString() })
    setShowAfterDone(true)
  }, [nowTask, timerState.isRunning, stop, updateTask])

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

  const handleSetNext = useCallback(async (taskId: number) => {
    await setAsNext(taskId)
    await refresh()
    await getNext()
  }, [setAsNext, refresh, getNext])

  // DnD handlers — cross-section slot moves
  const handleDropToNow = useCallback(async (taskId: number) => {
    await handleTakeNow(taskId)
  }, [handleTakeNow])

  const handleDropToNext = useCallback(async (taskId: number) => {
    await updateTask(taskId, { slot: 'next' })
  }, [updateTask])

  const handleMoveToLater = useCallback(async (taskId: number) => {
    await updateTask(taskId, { slot: 'later' })
  }, [updateTask])

  const handleGetNext = useCallback((skipId?: number) => {
    getNext(skipId)
  }, [getNext])

  const handleFocusSwitchConfirm = useCallback(() => {
    setShowFocusSwitch(false)
    if (pendingFocusTask) setSelectedTask(pendingFocusTask)
    setPendingFocusTask(null)
  }, [pendingFocusTask])

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
        isTimerActive={timerState.isRunning}
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
                onStop={handleStopTimer}
                onDone={handleDoneNow}
                onTaskClick={handleTaskClick}
                onAddTask={handleOpenNewTask}
                onDropTask={handleDropToNow}
              />
              <NextBlock
                tasks={tasks}
                onTaskClick={handleTaskClick}
                recommendation={recommendation}
                onReorder={reorderTasks}
                onDropFromOutside={handleDropToNext}
                focusMode={timerState.isRunning}
                nowTaskId={nowTask?.id}
              />
              <div className="flex-1" />
              <RecBar
                recommendation={recommendation}
                onGetNext={handleGetNext}
                onSetNext={handleSetNext}
                onTaskClick={handleTaskClick}
              />
            </div>

            {/* Right column */}
            <div className={`w-[42%] p-4 overflow-hidden transition-all ${timerState.isRunning ? 'opacity-30 blur-[3px] pointer-events-none' : ''}`}>
              <DirectionsPanel
                tasks={tasks}
                directions={directions}
                onTaskClick={handleTaskClick}
                onReorder={reorderTasks}
                onMoveToLater={handleMoveToLater}
                focusMode={timerState.isRunning}
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

        {screen === 'matrix' && (
          <MatrixScreen tasks={tasks} onClose={() => setScreen('main')} onTaskClick={handleTaskClick} />
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
          nextTasks={nextTasks}
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
          incompleteTasks={tasks.filter(t => !t.done_at && !t.deleted_at && t.slot !== 'someday')}
          onClose={() => setShowEveningSummary(false)}
          onLater={() => setShowEveningSummary(false)}
          onMoveToTomorrow={handleMoveToTomorrow}
        />
      )}
    </div>
  )
}
