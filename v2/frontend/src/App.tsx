// Focus Board v2 — фазовая машина дня.
// Утро (визард) → День (миссии) → Туннель (полноэкранный фокус) → Вечер (рефлексия).
// Списки задач и направления живут в слое «Библиотека», статистика — в слое «Пульс».
import { useState, useEffect, useCallback } from 'react'
import type { Task } from './types'
import { api, api2, type Mission } from './api'
import { useTasks } from './hooks/useTasks'
import { useTimer } from './hooks/useTimer'
import { usePomodoro } from './hooks/usePomodoro'

import MorningWizard from './phases/MorningWizard'
import PhaseDay from './phases/PhaseDay'
import FocusTunnel from './phases/FocusTunnel'
import PhaseEvening from './phases/PhaseEvening'
import TopBar from './phases/TopBar'
import LibraryDrawer from './overlays/LibraryDrawer'
import LiveStats from './overlays/LiveStats'

import TaskEditor from './components/TaskEditor'
import JournalScreen from './components/JournalScreen'
import SettingsScreen from './components/SettingsScreen'
import ArchiveScreen from './components/ArchiveScreen'
import TrashScreen from './components/TrashScreen'
import WeekPlanScreen from './components/WeekPlanScreen'
import StatsScreen from './components/StatsScreen'
import StandupModal from './components/modals/StandupModal'
import WeeklyReviewModal from './components/modals/WeeklyReviewModal'
import MonthlyReviewModal from './components/modals/MonthlyReviewModal'
import TimerSwitchModal from './components/modals/TimerSwitchModal'
import SessionIntentModal from './components/modals/SessionIntentModal'
import SessionNoteModal from './components/modals/SessionNoteModal'
import CreditWorkModal from './components/modals/CreditWorkModal'

export type Phase = 'morning' | 'day' | 'evening'
export type Layer = null | 'library' | 'stats' | 'stats-classic' | 'journal' | 'settings' | 'archive' | 'trash' | 'weekplan'

const todayStr = () => new Date().toISOString().slice(0, 10)

// ── Намерение сессии переживает перезагрузку окна ──────────────────────────────
const INTENT_KEY = 'focusboard_intent'
const SUBTASK_KEY = 'focusboard_subtask'
const persistIntent = (intent: string, subId: number | null) => {
  try {
    if (intent) sessionStorage.setItem(INTENT_KEY, intent)
    else sessionStorage.removeItem(INTENT_KEY)
    if (subId !== null) sessionStorage.setItem(SUBTASK_KEY, String(subId))
    else sessionStorage.removeItem(SUBTASK_KEY)
  } catch { /* sessionStorage недоступен — молча пропускаем */ }
}
const clearIntent = () => {
  try {
    sessionStorage.removeItem(INTENT_KEY)
    sessionStorage.removeItem(SUBTASK_KEY)
  } catch { /* noop */ }
}

export default function App() {
  const [phase, setPhase] = useState<Phase>('day')
  const [layer, setLayer] = useState<Layer>(null)
  const [missions, setMissions] = useState<Mission[]>([])
  const [missionsLoaded, setMissionsLoaded] = useState(false)
  const [todayCheckin, setTodayCheckin] = useState<{ exists: boolean; mood?: number | null; goal?: string | null } | null>(null)
  const [selectedTask, setSelectedTask] = useState<Task | null | undefined>(undefined)
  const [showStandup, setShowStandup] = useState(false)
  const [showWeeklyReview, setShowWeeklyReview] = useState(false)
  const [showMonthlyReview, setShowMonthlyReview] = useState(false)
  const [isQuarterlyReview, setIsQuarterlyReview] = useState(false)
  const [showTimerSwitch, setShowTimerSwitch] = useState(false)
  const [pendingSwitchTaskId, setPendingSwitchTaskId] = useState<number | null>(null)
  const [pendingStartTaskId, setPendingStartTaskId] = useState<number | null>(null)
  const [sessionIntent, setSessionIntent] = useState('')
  const [sessionSubtaskId, setSessionSubtaskId] = useState<number | null>(null)
  const [postStopSessionId, setPostStopSessionId] = useState<number | null>(null)
  const [creditTaskId, setCreditTaskId] = useState<number | null>(null)

  const { tasks, directions, refresh, updateTask, deleteTask, takeNow, reorderTasks, undo } = useTasks()
  const { timerState, start, pause, resume, stop } = useTimer()
  const { pomodoroState, pomodoroEnabled, skipPomodoro } = usePomodoro(timerState.isRunning, pause)

  const nowTask = tasks.find(t => t.slot === 'now' && !t.done_at && !t.deleted_at) ?? null
  const inTunnel = timerState.isRunning || timerState.isPaused

  // ── Миссии дня ──────────────────────────────────────────────────────────────
  const refreshMissions = useCallback(async () => {
    try {
      const ms = await api2.getMissions(todayStr())
      setMissions(ms)
      return ms
    } catch { return [] as Mission[] }
    finally { setMissionsLoaded(true) }
  }, [])

  // Восстановление намерения после перезагрузки окна (таймер поднимается в useTimer)
  useEffect(() => {
    try {
      const savedIntent = sessionStorage.getItem(INTENT_KEY)
      const savedSub = sessionStorage.getItem(SUBTASK_KEY)
      if (savedIntent) setSessionIntent(savedIntent)
      if (savedSub !== null) setSessionSubtaskId(Number(savedSub))
    } catch { /* noop */ }
  }, [])

  // ── Определение фазы при запуске ───────────────────────────────────────────
  useEffect(() => {
    const today = todayStr()
    api.getTodayCheckin().then(setTodayCheckin).catch(() => {})
    refreshMissions().then(ms => {
      const wizardDone = localStorage.getItem(`v2_morning_${today}`)
      const eveningDone = localStorage.getItem(`v2_evening_${today}`)
      if (ms.length === 0 && !wizardDone && !eveningDone) setPhase('morning')
    })
  }, [refreshMissions])

  // Смена даты в полночь: заново к утру
  useEffect(() => {
    let last = todayStr()
    const id = setInterval(() => {
      const t = todayStr()
      if (t !== last) { last = t; refresh(); refreshMissions(); setPhase('morning'); setTodayCheckin(null) }
    }, 60_000)
    return () => clearInterval(id)
  }, [refresh, refreshMissions])

  // Недельный/квартальный обзор — по прежнему расписанию v1
  useEffect(() => {
    const flag = (k: string) => localStorage.getItem(k) !== 'false'
    const now = new Date()
    if (flag('weekly_review_enabled') && [0, 5, 6].includes(now.getDay()) && now.getHours() >= 17) {
      const weekKey = `weekly_review_${now.getFullYear()}_${Math.ceil(now.getDate() / 7)}_${now.getMonth()}`
      if (!localStorage.getItem(weekKey)) { setShowWeeklyReview(true); localStorage.setItem(weekKey, '1') }
    }
    if (localStorage.getItem('monthly_review_enabled') === 'true' && now.getDate() <= 3) {
      const monthKey = `monthly_review_${now.getFullYear()}_${now.getMonth()}`
      if (!localStorage.getItem(monthKey)) {
        setIsQuarterlyReview([0, 3, 6, 9].includes(now.getMonth()))
        setShowMonthlyReview(true)
        localStorage.setItem(monthKey, '1')
      }
    }
  }, [])

  // ── Таймер и туннель ────────────────────────────────────────────────────────
  const requestStart = useCallback((taskId: number) => {
    const intentEnabled = localStorage.getItem('intent_enabled') !== 'false'
    if (intentEnabled) setPendingStartTaskId(taskId)
    else start(taskId)
  }, [start])

  // «В фокус» на миссии/задаче: сделать текущей и запустить
  const focusOnTask = useCallback(async (taskId: number) => {
    if (timerState.isRunning) { setPendingSwitchTaskId(taskId); setShowTimerSwitch(true); return }
    await takeNow(taskId)
    requestStart(taskId)
  }, [timerState.isRunning, takeNow, requestStart])

  const handleTimerSwitchConfirm = useCallback(async () => {
    setShowTimerSwitch(false)
    const { sessionId } = await stop()
    if (sessionId !== null) setPostStopSessionId(sessionId)
    clearIntent()  // сбросить старое намерение; модалка намерения перезапишет, если включена
    if (pendingSwitchTaskId !== null) {
      await takeNow(pendingSwitchTaskId)
      requestStart(pendingSwitchTaskId)
      setPendingSwitchTaskId(null)
    }
  }, [stop, takeNow, requestStart, pendingSwitchTaskId])

  const handleStop = useCallback(async () => {
    const { sessionId } = await stop()
    if (sessionId !== null) setPostStopSessionId(sessionId)
    clearIntent()
    window.dispatchEvent(new CustomEvent('gamification-updated'))
    refreshMissions()
  }, [stop, refreshMissions])

  const handleDoneNow = useCallback(async () => {
    if (!nowTask) return
    let sid: number | null = null
    if (timerState.isRunning || timerState.isPaused) {
      const { sessionId } = await stop()
      sid = sessionId
    }
    await updateTask(nowTask.id, { slot: 'queue', done_at: new Date().toISOString() })
    if (sid !== null) setPostStopSessionId(sid)
    clearIntent()
    window.dispatchEvent(new CustomEvent('gamification-updated'))
    refreshMissions()
  }, [nowTask, timerState, stop, updateTask, refreshMissions])

  const handleMarkDone = useCallback(async (taskId: number) => {
    if (nowTask && taskId === nowTask.id) { await handleDoneNow(); return }
    await updateTask(taskId, { done_at: new Date().toISOString() } as any)
    window.dispatchEvent(new CustomEvent('gamification-updated'))
    refreshMissions()
    // Работал вне таймера? Мягко предложим зачесть время в фокус.
    const sess = await api.getTaskSessions(taskId).catch(() => [])
    if (sess.length === 0) setCreditTaskId(taskId)
  }, [nowTask, handleDoneNow, updateTask, refreshMissions])

  // ── Хоткеи: Space таймер, ⌘Z undo, ⌘L библиотека, Esc слой ─────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
      if (e.key === ' ' && e.target === document.body) {
        e.preventDefault()
        if (timerState.isRunning) pause()
        else if (timerState.isPaused) resume()
        else {
          const nextMission = missions.find(m => !m.done_at)
          const missionTask = nextMission ? tasks.find(t => t.id === nextMission.task_id) : null
          let target = nowTask ?? missionTask ?? null
          if (!target) {
            // Пустой день: взять первую активную задачу (ближайший дедлайн → первая)
            const active = tasks.filter(t => !t.done_at && !t.deleted_at && !t.someday && t.slot !== 'now')
            const ms = (t: Task) => (t.deadline ? new Date(t.deadline).getTime() : Number.POSITIVE_INFINITY)
            const withDl = active.filter(t => t.deadline).sort((a, b) => ms(a) - ms(b))
            target = withDl[0] ?? active[0] ?? null
          }
          if (target) focusOnTask(target.id)
        }
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey && !typing) { e.preventDefault(); undo() }
      if ((e.metaKey || e.ctrlKey) && e.key === 'l') { e.preventDefault(); setLayer(l => l === 'library' ? null : 'library') }
      if (e.key === 'Escape' && layer && selectedTask === undefined) setLayer(null)
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [timerState, nowTask, missions, tasks, pause, resume, focusOnTask, undo, layer, selectedTask])

  // Чек-ин из дневника обновляет цель дня
  useEffect(() => {
    const h = () => { api.getTodayCheckin().then(setTodayCheckin).catch(() => {}) }
    window.addEventListener('journal-updated', h)
    return () => window.removeEventListener('journal-updated', h)
  }, [])

  // Клик по утреннему уведомлению открывает приложение на фазе «Утро» (#morning)
  useEffect(() => {
    const openIfMorningHash = () => {
      if (window.location.hash === '#morning') { setLayer(null); setPhase('morning') }
    }
    openIfMorningHash()
    window.addEventListener('hashchange', openIfMorningHash)
    return () => window.removeEventListener('hashchange', openIfMorningHash)
  }, [])

  const openEditor = useCallback((t: Task | null) => setSelectedTask(t), [])

  const finishMorning = useCallback(() => {
    localStorage.setItem(`v2_morning_${todayStr()}`, '1')
    refreshMissions()
    setPhase('day')
  }, [refreshMissions])

  const finishEvening = useCallback(() => {
    localStorage.setItem(`v2_evening_${todayStr()}`, '1')
    setPhase('day')
  }, [])

  // ── Рендер ──────────────────────────────────────────────────────────────────
  return (
    <div className="h-screen flex flex-col bg-bg text-text overflow-hidden">
      {!inTunnel && phase !== 'morning' && (
        <TopBar
          phase={phase}
          onPhase={setPhase}
          layer={layer}
          onLayer={setLayer}
          onStandup={() => setShowStandup(true)}
          onTaskCreated={() => { refresh(); refreshMissions() }}
          onOpenEditor={id => { const t = tasks.find(x => x.id === id); if (t) setSelectedTask(t) }}
        />
      )}

      <div className="flex-1 overflow-hidden relative">
        {phase === 'morning' && !inTunnel && (
          <MorningWizard
            tasks={tasks}
            directions={directions}
            checkin={todayCheckin}
            onDone={finishMorning}
            onSkip={finishMorning}
            onCheckinSaved={(mood, goal) => setTodayCheckin({ exists: true, mood, goal })}
          />
        )}

        {phase === 'day' && !inTunnel && (
          <PhaseDay
            missions={missions}
            missionsLoaded={missionsLoaded}
            tasks={tasks}
            directions={directions}
            checkin={todayCheckin}
            nowTaskId={nowTask?.id ?? null}
            onFocus={focusOnTask}
            onMarkDone={handleMarkDone}
            onEdit={t => setSelectedTask(t)}
            onOpenLibrary={() => setLayer('library')}
            onOpenMorning={() => setPhase('morning')}
            onOpenEvening={() => setPhase('evening')}
            onRemoveMission={async id => { await api2.deleteMission(id).catch(() => {}); refreshMissions() }}
          />
        )}

        {phase === 'evening' && !inTunnel && (
          <PhaseEvening
            tasks={tasks}
            directions={directions}
            missions={missions}
            onClose={finishEvening}
          />
        )}

        {inTunnel && nowTask && (
          <FocusTunnel
            task={nowTask}
            directions={directions}
            timer={timerState}
            intent={sessionIntent}
            pomodoroPhase={pomodoroEnabled ? pomodoroState.phase : 'idle'}
            pomodoroRemaining={pomodoroState.remaining}
            onSkipPomodoro={skipPomodoro}
            onPause={pause}
            onResume={resume}
            onStop={handleStop}
            onDone={handleDoneNow}
          />
        )}
        {inTunnel && !nowTask && (
          // Задачу удалили/закрыли под работающим таймером — мягко останавливаем
          <div className="h-full flex items-center justify-center">
            <button onClick={handleStop} className="btn-primary">Завершить сессию</button>
          </div>
        )}
      </div>

      {/* ── Слои ── */}
      {layer === 'library' && !inTunnel && (
        <LibraryDrawer
          tasks={tasks}
          directions={directions}
          missions={missions}
          nowTaskId={nowTask?.id}
          onClose={() => setLayer(null)}
          onTaskClick={t => setSelectedTask(t)}
          onNewTask={() => setSelectedTask(null)}
          onFocus={focusOnTask}
          onMarkDone={handleMarkDone}
          onAddMission={async taskId => {
            const cur = missions.map(m => ({ task_id: m.task_id }))
            if (cur.length >= 3 || cur.some(m => m.task_id === taskId)) return
            await api2.setMissions(todayStr(), [...cur, { task_id: taskId }]).catch(() => {})
            refreshMissions()
          }}
          onPriorityChange={async (id, p) => { await updateTask(id, { priority: p } as any) }}
          onChangeDirection={async (id, d) => { await updateTask(id, { direction_id: d, in_queue: false } as any) }}
          onReorderInDirection={async (d, ids) => { await api.reorderInDirection(d, ids); await refresh() }}
          onReorderSprint={async ids => { await api.reorderSprint(ids); await refresh() }}
          onReorder={reorderTasks}
          onUpdateDirection={(id, data) => api.updateDirection(id, data).then(refresh).catch(() => {})}
        />
      )}

      {layer === 'stats' && <LiveStats directions={directions} onClose={() => setLayer(null)} onClassic={() => setLayer('stats-classic')} />}
      {layer === 'stats-classic' && <div className="absolute inset-0 top-0 z-40 bg-bg"><StatsScreen onClose={() => setLayer('stats')} /></div>}
      {layer === 'journal' && <div className="absolute inset-0 z-40 bg-bg"><JournalScreen onClose={() => setLayer(null)} /></div>}
      {layer === 'settings' && <div className="absolute inset-0 z-40 bg-bg"><SettingsScreen directions={directions} onClose={() => setLayer(null)} onDirectionChange={refresh} onNavigate={s => setLayer((s as string) === 'archive' ? 'archive' : (s as string) === 'trash' ? 'trash' : null)} /></div>}
      {layer === 'archive' && <div className="absolute inset-0 z-40 bg-bg"><ArchiveScreen directions={directions} onClose={() => setLayer(null)} onChanged={() => { refresh(); refreshMissions() }} /></div>}
      {layer === 'trash' && <div className="absolute inset-0 z-40 bg-bg"><TrashScreen onClose={() => setLayer(null)} onRestored={refresh} /></div>}
      {layer === 'weekplan' && <div className="absolute inset-0 z-40 bg-bg"><WeekPlanScreen directions={directions} onClose={() => setLayer(null)} onChanged={refresh} /></div>}

      {/* ── Редактор и модалки ── */}
      {selectedTask !== undefined && (
        <TaskEditor
          task={selectedTask}
          directions={directions}
          onClose={() => setSelectedTask(undefined)}
          onSaved={async () => { await refresh(); await refreshMissions(); setSelectedTask(undefined) }}
          onDeleted={async () => { await refresh(); await refreshMissions(); setSelectedTask(undefined) }}
          onTakenNow={() => { if (selectedTask) { setSelectedTask(undefined); focusOnTask(selectedTask.id) } }}
          onMarkDone={selectedTask && !selectedTask.done_at ? async () => { await handleMarkDone(selectedTask.id); setSelectedTask(undefined) } : undefined}
        />
      )}

      {showStandup && <StandupModal onClose={() => setShowStandup(false)} />}
      {showWeeklyReview && <WeeklyReviewModal tasks={tasks} directions={directions} onClose={() => setShowWeeklyReview(false)} onLater={() => setShowWeeklyReview(false)} />}
      {showMonthlyReview && <MonthlyReviewModal isQuarterly={isQuarterlyReview} tasks={tasks} directions={directions} onClose={() => setShowMonthlyReview(false)} onLater={() => setShowMonthlyReview(false)} />}

      {showTimerSwitch && (
        <TimerSwitchModal
          onCancel={() => { setShowTimerSwitch(false); setPendingSwitchTaskId(null) }}
          onConfirm={handleTimerSwitchConfirm}
        />
      )}

      {pendingStartTaskId !== null && (
        <SessionIntentModal
          taskId={pendingStartTaskId}
          taskTitle={tasks.find(t => t.id === pendingStartTaskId)?.title ?? ''}
          onStart={(intent, subId) => { setSessionIntent(intent); setSessionSubtaskId(subId); persistIntent(intent, subId); const id = pendingStartTaskId; setPendingStartTaskId(null); start(id!) }}
          onSkip={() => { setSessionIntent(''); setSessionSubtaskId(null); persistIntent('', null); const id = pendingStartTaskId; setPendingStartTaskId(null); start(id!) }}
        />
      )}

      {postStopSessionId !== null && (
        <SessionNoteModal
          sessionId={postStopSessionId}
          intent={sessionIntent || undefined}
          subtaskId={sessionSubtaskId}
          onClose={() => { setPostStopSessionId(null); setSessionIntent(''); setSessionSubtaskId(null); clearIntent() }}
        />
      )}

      {creditTaskId !== null && (
        <CreditWorkModal
          taskId={creditTaskId}
          taskTitle={tasks.find(t => t.id === creditTaskId)?.title ?? ''}
          onClose={() => { setCreditTaskId(null); refresh(); refreshMissions() }}
        />
      )}
    </div>
  )
}
