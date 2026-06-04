import { useState, useEffect, useCallback, useRef } from 'react'
import type { Task, Screen } from './types'
import { api } from './api'
import { useTasks } from './hooks/useTasks'
import { useTimer } from './hooks/useTimer'
import { usePomodoro } from './hooks/usePomodoro'
import Header from './components/Header'
import BreakScreen from './components/BreakScreen'
import StandupModal from './components/modals/StandupModal'
import MonthlyReviewModal from './components/modals/MonthlyReviewModal'
import HorizonScreen from './components/HorizonScreen'
import NowBlock from './components/NowBlock'
import QueueBlock from './components/QueueBlock'
import DirectionsPanel from './components/DirectionsPanel'
import TaskEditor from './components/TaskEditor'
import AfterDoneModal from './components/modals/AfterDoneModal'
import TimerSwitchModal from './components/modals/TimerSwitchModal'
import CheckinModal from './components/modals/CheckinModal'
import SessionIntentModal from './components/modals/SessionIntentModal'
import FocusSwitchModal from './components/modals/FocusSwitchModal'
import EveningSummaryModal from './components/modals/EveningSummaryModal'
import WeeklyReviewModal from './components/modals/WeeklyReviewModal'
import MorningPlanModal from './components/modals/MorningPlanModal'
import DayPlanBlock from './components/DayPlanBlock'
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
  const [showWeeklyReview, setShowWeeklyReview] = useState(false)
  const [showMonthlyReview, setShowMonthlyReview] = useState(false)
  const [isQuarterlyReview, setIsQuarterlyReview] = useState(false)
  const [showStandup, setShowStandup] = useState(false)
  const [showMorningPlan, setShowMorningPlan] = useState(false)
  const [planTaskIds, setPlanTaskIds] = useState<number[]>([])
  const [planTasks, setPlanTasks] = useState<any[]>([])
  const [postStopSessionId, setPostStopSessionId] = useState<number | null>(null)
  const [pendingStartTaskId, setPendingStartTaskId] = useState<number | null>(null)
  const [sessionIntent, setSessionIntent] = useState('')
  const [todayTime, setTodayTime] = useState(0)
  const [weeklyTime, setWeeklyTime] = useState<Record<number, number>>({})
  const quickInputRef = useRef<HTMLInputElement | null>(null)

  const { tasks, directions, refresh, updateTask, deleteTask, takeNow, reorderTasks, undo } = useTasks()

  const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at) ?? null
  const queueTasks = tasks.filter(t => t.slot === 'queue' && !t.done_at && !t.deleted_at)

  const { timerState, start, pause, resume, stop } = useTimer()
  const { pomodoroState, pomodoroEnabled, skipPomodoro } = usePomodoro(timerState.isRunning, pause)

  // Load today time for now task
  useEffect(() => {
    if (!nowTask) { setTodayTime(0); return }
    api.getTodayTime(nowTask.id).then(r => setTodayTime(r.total)).catch(() => setTodayTime(0))
  }, [nowTask?.id])

  // Load weekly time for direction progress bars
  useEffect(() => {
    api.getWeeklyTime().then(rows => {
      const map: Record<number, number> = {}
      rows.forEach(r => { if (r.direction_id != null) map[r.direction_id] = r.seconds })
      setWeeklyTime(map)
    }).catch(() => {})
  }, [])

  // --- Day-transition checks (run on mount + whenever date changes) ---

  const checkDayTransitions = useCallback((today: string) => {
    const flag = (key: string) => localStorage.getItem(key) !== 'false'

    // Check-in
    if (flag('checkin_enabled')) {
      api.getTodayCheckin().then(r => {
        if (!r.exists) setShowCheckin(true)
      }).catch(() => {})
    }

    // Morning plan
    api.getDayPlan(today).then(rows => {
      setPlanTaskIds(rows.map((r: any) => r.task_id))
      setPlanTasks(rows)
      if (rows.length > 0) {
        const key = `morning_plan_shown_${today}`
        if (!localStorage.getItem(key)) {
          setShowMorningPlan(true)
          localStorage.setItem(key, '1')
        }
      }
    }).catch(() => {})

    const now = new Date()
    const day = now.getDay()

    // Weekly review (Fri/Sat/Sun after 17:00)
    if (flag('weekly_review_enabled') && [0, 5, 6].includes(day) && now.getHours() >= 17) {
      const weekKey = `weekly_review_${now.getFullYear()}_${Math.ceil(now.getDate() / 7)}_${now.getMonth()}`
      if (!localStorage.getItem(weekKey)) {
        setShowWeeklyReview(true)
        localStorage.setItem(weekKey, '1')
      }
    }

    // Monthly/quarterly review (1st–3rd of month)
    if (flag('monthly_review_enabled')) {
      const dom = now.getDate()
      if (dom <= 3) {
        const month = now.getMonth()
        const isQ1 = [0, 3, 6, 9].includes(month)
        const monthKey = `monthly_review_${now.getFullYear()}_${month}`
        if (!localStorage.getItem(monthKey)) {
          setIsQuarterlyReview(isQ1)
          setShowMonthlyReview(true)
          localStorage.setItem(monthKey, '1')
        }
      }
    }
  }, [])

  // Run on mount
  useEffect(() => {
    checkDayTransitions(new Date().toISOString().slice(0, 10))
  }, [checkDayTransitions])

  // Detect midnight — re-run checks when date changes while app is open
  useEffect(() => {
    let lastDate = new Date().toISOString().slice(0, 10)
    const id = setInterval(() => {
      const today = new Date().toISOString().slice(0, 10)
      if (today !== lastDate) {
        lastDate = today
        refresh()
        checkDayTransitions(today)
      }
    }, 60_000)
    return () => clearInterval(id)
  }, [checkDayTransitions, refresh])

  // Show evening summary after 19:00
  useEffect(() => {
    const check = () => {
      if (localStorage.getItem('evening_enabled') === 'false') return
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
    const intentEnabled = localStorage.getItem('intent_enabled') !== 'false'
    if (intentEnabled) {
      setPendingStartTaskId(nowTask.id)
    } else {
      start(nowTask.id)
    }
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

  const handleSendToQueue = useCallback(async () => {
    if (!nowTask) return
    if (timerState.isRunning || timerState.isPaused) {
      const { sessionId } = await stop()
      if (sessionId !== null) setPostStopSessionId(sessionId)
    }
    await api.evictNow()
    await refresh()
  }, [nowTask, timerState.isRunning, timerState.isPaused, stop, refresh])

  // --- Day-plan helpers (keep Сейчас / На сегодня / Следом mutually exclusive) ---
  const removeFromPlan = useCallback((taskId: number) => {
    if (!planTaskIds.includes(taskId)) return
    const today = new Date().toISOString().slice(0, 10)
    const newIds = planTaskIds.filter(id => id !== taskId)
    setPlanTaskIds(newIds)
    api.setDayPlan(today, newIds).catch(() => {})
  }, [planTaskIds])

  const addToPlan = useCallback(async (taskId: number) => {
    // Move into today's plan: drop out of the queue and the now-slot
    await updateTask(taskId, { in_queue: false, slot: 'queue' } as any)
    if (planTaskIds.includes(taskId)) return
    const today = new Date().toISOString().slice(0, 10)
    const newIds = [...planTaskIds, taskId]
    setPlanTaskIds(newIds)
    api.setDayPlan(today, newIds).catch(() => {})
  }, [planTaskIds, updateTask])

  const handleTakeNow = useCallback(async (taskId: number) => {
    if (timerState.isRunning) {
      setPendingSwitchTaskId(taskId)
      setShowTimerSwitch(true)
      return
    }
    await takeNow(taskId)
    removeFromPlan(taskId)
    setSelectedTask(undefined)
  }, [timerState.isRunning, takeNow, removeFromPlan])

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
    removeFromPlan(taskId)
  }, [updateTask, tasks, removeFromPlan])

  const handleRemoveFromQueue = useCallback(async (taskId: number) => {
    await updateTask(taskId, { in_queue: false } as any)
  }, [updateTask])

  const handleMarkDone = useCallback(async (taskId: number) => {
    if (nowTask && taskId === nowTask.id) {
      await handleDoneNow()
      return
    }
    await updateTask(taskId, { done_at: new Date().toISOString() } as any)
  }, [nowTask, handleDoneNow, updateTask])

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
        onStandup={() => setShowStandup(true)}
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
                onSendToQueue={handleSendToQueue}
                onTaskClick={handleTaskClick}
                onAddTask={handleOpenNewTask}
                onDropTask={handleDropToNow}
                onPriorityChange={handlePriorityChange}
                pomodoroPhase={pomodoroEnabled ? pomodoroState.phase : 'idle'}
                pomodoroRemaining={pomodoroState.remaining}
                onSkipPomodoro={skipPomodoro}
              />
              <DayPlanBlock
                planTaskIds={planTaskIds}
                tasks={tasks}
                directions={directions}
                onTakeNow={handleTakeNow}
                onMarkDone={handleMarkDone}
                onTaskClick={handleTaskClick}
                onReorder={newIds => {
                  const today = new Date().toISOString().slice(0, 10)
                  setPlanTaskIds(newIds)
                  api.setDayPlan(today, newIds).catch(() => {})
                }}
                onAddToPlan={addToPlan}
                onPriorityChange={handlePriorityChange}
              />
              <QueueBlock
                tasks={tasks}
                directions={directions}
                onTaskClick={handleTaskClick}
                onReorder={reorderTasks}
                onDropFromOutside={handleAddToQueue}
                onRemoveFromQueue={handleRemoveFromQueue}
                onMarkDone={handleMarkDone}
                onTakeNow={handleTakeNow}
                onPriorityChange={handlePriorityChange}
                planTaskIds={planTaskIds}
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
                onMarkDone={handleMarkDone}
                onPriorityChange={handlePriorityChange}
                onUpdateDirection={(id, data) => api.updateDirection(id, data).then(refresh).catch(() => {})}
                weeklyTime={weeklyTime}
                planTaskIds={planTaskIds}
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
        {screen === 'horizon' && (
          <HorizonScreen
            tasks={tasks}
            directions={directions}
            onClose={() => setScreen('main')}
            onTaskClick={handleTaskClick}
          />
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
          onMarkDone={selectedTask && !selectedTask.done_at ? async () => {
            await handleMarkDone(selectedTask.id)
            setSelectedTask(undefined)
          } : undefined}
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
          tasks={tasks}
          directions={directions}
          onClose={() => setShowEveningSummary(false)}
          onLater={() => setShowEveningSummary(false)}
        />
      )}

      {showWeeklyReview && (
        <WeeklyReviewModal
          tasks={tasks}
          directions={directions}
          onClose={() => setShowWeeklyReview(false)}
          onLater={() => setShowWeeklyReview(false)}
        />
      )}

      {showMonthlyReview && (
        <MonthlyReviewModal
          isQuarterly={isQuarterlyReview}
          tasks={tasks}
          directions={directions}
          onClose={() => setShowMonthlyReview(false)}
          onLater={() => setShowMonthlyReview(false)}
        />
      )}

      {showMorningPlan && (
        <MorningPlanModal
          planTasks={planTasks}
          directions={directions}
          onTakeNow={handleTakeNow}
          onClose={() => setShowMorningPlan(false)}
        />
      )}

      {showStandup && <StandupModal onClose={() => setShowStandup(false)} />}

      {/* Break screen — shown when timer is paused and break screen is enabled */}
      {timerState.isPaused && localStorage.getItem('break_screen_enabled') !== 'false' && (
        <BreakScreen
          elapsed={timerState.elapsed}
          onResume={handleResumeTimer}
        />
      )}

      {pendingStartTaskId !== null && nowTask && (
        <SessionIntentModal
          taskTitle={nowTask.title}
          onStart={intent => {
            setSessionIntent(intent)
            setPendingStartTaskId(null)
            start(pendingStartTaskId)
          }}
          onSkip={() => {
            setSessionIntent('')
            setPendingStartTaskId(null)
            start(pendingStartTaskId!)
          }}
        />
      )}

      {postStopSessionId !== null && (
        <SessionNoteModal
          sessionId={postStopSessionId}
          intent={sessionIntent || undefined}
          onClose={() => { setPostStopSessionId(null); setSessionIntent('') }}
        />
      )}
    </div>
  )
}
