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
import TaskEditor from './components/TaskEditor'
import AfterDoneModal from './components/modals/AfterDoneModal'
import TimerSwitchModal from './components/modals/TimerSwitchModal'
import CheckinModal from './components/modals/CheckinModal'
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
  const [todayTime, setTodayTime] = useState(0)
  const quickInputRef = useRef<HTMLInputElement | null>(null)

  const { tasks, directions, refresh, updateTask, deleteTask, takeNow, reorderTasks } = useTasks()
  const { recommendation, getNext, setAsNext } = useRecommendation()

  const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at) ?? null
  const nextTasks = tasks.filter(t => t.slot === 'next' && !t.done_at && !t.deleted_at)

  const handleTimerComplete = useCallback(() => {
    setShowAfterDone(true)
  }, [])

  const { timerState, start, pause, stop, setDuration } = useTimer(handleTimerComplete)

  // Load timer duration from settings
  useEffect(() => {
    api.getSettings().then((s: Record<string, string>) => {
      if (s.timer_duration) setDuration(parseInt(s.timer_duration))
    }).catch(() => {})
  }, [setDuration])

  // Load today time for now task
  useEffect(() => {
    if (!nowTask) { setTodayTime(0); return }
    api.getTodayTime(nowTask.id).then(r => setTodayTime(r.total)).catch(() => setTodayTime(0))
  }, [nowTask?.id])

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

  // Space shortcut for timer
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === ' ' && e.target === document.body) {
        e.preventDefault()
        if (!nowTask) return
        if (timerState.isRunning) pause()
        else start(nowTask.id)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [timerState.isRunning, nowTask, pause, start])

  const handleTaskClick = useCallback((task: Task) => {
    setSelectedTask(task)
  }, [])

  const handleStartTimer = useCallback(() => {
    if (!nowTask) return
    start(nowTask.id)
  }, [nowTask, start])

  const handlePauseTimer = useCallback(() => {
    pause()
  }, [pause])

  const handleDoneNow = useCallback(async () => {
    if (!nowTask) return
    if (timerState.isRunning) await pause()
    await updateTask(nowTask.id, { status: 'done', slot: 'later', done_at: new Date().toISOString() })
    setShowAfterDone(true)
  }, [nowTask, timerState.isRunning, pause, updateTask])

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

  return (
    <div className="h-screen flex flex-col bg-[#181818] text-[#f0f0f0] overflow-hidden">
      <Header
        onNavigate={s => setScreen(s)}
        onTaskCreated={refresh}
        onOpenEditor={(id) => {
          const t = tasks.find(x => x.id === id)
          if (t) setSelectedTask(t)
        }}
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
            <div className="w-[42%] p-4 overflow-hidden">
              <DirectionsPanel
                tasks={tasks}
                directions={directions}
                onTaskClick={handleTaskClick}
                onReorder={reorderTasks}
                onMoveToLater={handleMoveToLater}
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
    </div>
  )
}
