import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Task, Step, SubGoal, Goal, Direction, TimerState, Page, TaskStatus } from '../types'
import { TASKS, SUBGOALS, GOALS, DIRECTIONS } from '../data/seed'
import { uid } from '../utils/time'

interface AppState {
  // Data
  tasks: Record<string, Task>
  subGoals: Record<string, SubGoal>
  goals: Record<string, Goal>
  directions: Direction[]

  // UI state
  currentPage: Page
  focusTaskId: string
  selectedDirectionId: string
  searchQuery: string
  statusFilter: TaskStatus | 'all'
  directionFilter: string // 'all' or directionId

  // Timer
  timer: TimerState

  // Navigation
  setPage: (page: Page) => void

  // Focus
  setFocusTask: (taskId: string) => void

  // Direction
  setSelectedDirection: (directionId: string) => void

  // Registry filters
  setSearchQuery: (q: string) => void
  setStatusFilter: (f: TaskStatus | 'all') => void
  setDirectionFilter: (f: string) => void

  // Task CRUD
  addTask: (partial: Partial<Task> & { title: string; subGoalId: string; directionId: string }) => string
  updateTask: (id: string, patch: Partial<Task>) => void
  deleteTask: (id: string) => void

  // Step CRUD
  addStep: (taskId: string, title: string) => void
  updateStep: (taskId: string, stepId: string, patch: Partial<Step>) => void
  deleteStep: (taskId: string, stepId: string) => void
  reorderSteps: (taskId: string, steps: Step[]) => void
  toggleStep: (taskId: string, stepId: string) => void

  // SubGoal CRUD
  addSubGoal: (goalId: string, directionId: string, title: string) => void
  updateSubGoal: (id: string, patch: Partial<SubGoal>) => void
  deleteSubGoal: (id: string) => void

  // Goal CRUD
  updateGoal: (id: string, patch: Partial<Goal>) => void

  // Timer
  timerStart: (taskId: string) => void
  timerPause: () => void
  timerStop: () => void
  timerTick: () => void

  // Selectors (computed)
  getTasksBySubGoal: (subGoalId: string) => Task[]
  getSubGoalsByGoal: (goalId: string) => SubGoal[]
  getGoalByDirection: (directionId: string) => Goal | undefined
  getDirectionById: (id: string) => Direction | undefined
  totalTimeForTask: (taskId: string) => number
  totalTimeForSubGoal: (subGoalId: string) => number
  totalTimeForGoal: (goalId: string) => number
  totalTimeForDirection: (directionId: string) => number
  filteredTasks: () => Task[]
}

const toRecord = <T extends { id: string }>(arr: T[]): Record<string, T> =>
  Object.fromEntries(arr.map(x => [x.id, x]))

export const useStore = create<AppState>()(
  persist(
    (set, get) => ({
      tasks: toRecord(TASKS),
      subGoals: toRecord(SUBGOALS),
      goals: toRecord(GOALS),
      directions: DIRECTIONS,

      currentPage: 1,
      focusTaskId: TASKS.find(t => t.status === 'active')?.id ?? TASKS[0].id,
      selectedDirectionId: DIRECTIONS[0].id,
      searchQuery: '',
      statusFilter: 'all',
      directionFilter: 'all',

      timer: {
        taskId: null,
        running: false,
        startedAt: null,
        accumulatedMs: 0,
      },

      setPage: (page) => set({ currentPage: page }),
      setFocusTask: (taskId) => set({ focusTaskId: taskId }),
      setSelectedDirection: (id) => set({ selectedDirectionId: id }),
      setSearchQuery: (q) => set({ searchQuery: q }),
      setStatusFilter: (f) => set({ statusFilter: f }),
      setDirectionFilter: (f) => set({ directionFilter: f }),

      addTask: (partial) => {
        const newId = `t_${uid()}`
        const task: Task = {
          id: newId,
          title: partial.title,
          subGoalId: partial.subGoalId,
          directionId: partial.directionId,
          status: partial.status ?? 'active',
          totalTime: 0,
          createdAt: new Date().toISOString().slice(0, 10),
          steps: [],
          ...partial,
        }
        const sg = get().subGoals[partial.subGoalId]
        set(s => ({
          tasks: { ...s.tasks, [newId]: task },
          subGoals: sg
            ? { ...s.subGoals, [sg.id]: { ...sg, taskIds: [...sg.taskIds, newId] } }
            : s.subGoals,
        }))
        return newId
      },

      updateTask: (id, patch) =>
        set(s => ({ tasks: { ...s.tasks, [id]: { ...s.tasks[id], ...patch } } })),

      deleteTask: (id) => {
        const task = get().tasks[id]
        set(s => {
          const tasks = { ...s.tasks }
          delete tasks[id]
          const subGoals = { ...s.subGoals }
          if (task?.subGoalId && subGoals[task.subGoalId]) {
            subGoals[task.subGoalId] = {
              ...subGoals[task.subGoalId],
              taskIds: subGoals[task.subGoalId].taskIds.filter(tid => tid !== id),
            }
          }
          return { tasks, subGoals }
        })
      },

      addStep: (taskId, title) => {
        const task = get().tasks[taskId]
        if (!task) return
        const newStep: Step = {
          id: `${taskId}_s${uid()}`,
          title,
          taskId,
          completed: false,
          order: task.steps.length,
        }
        set(s => ({
          tasks: { ...s.tasks, [taskId]: { ...task, steps: [...task.steps, newStep] } },
        }))
      },

      updateStep: (taskId, stepId, patch) => {
        const task = get().tasks[taskId]
        if (!task) return
        set(s => ({
          tasks: {
            ...s.tasks,
            [taskId]: {
              ...task,
              steps: task.steps.map(st => st.id === stepId ? { ...st, ...patch } : st),
            },
          },
        }))
      },

      deleteStep: (taskId, stepId) => {
        const task = get().tasks[taskId]
        if (!task) return
        set(s => ({
          tasks: {
            ...s.tasks,
            [taskId]: { ...task, steps: task.steps.filter(st => st.id !== stepId) },
          },
        }))
      },

      reorderSteps: (taskId, steps) => {
        const task = get().tasks[taskId]
        if (!task) return
        set(s => ({ tasks: { ...s.tasks, [taskId]: { ...task, steps } } }))
      },

      toggleStep: (taskId, stepId) => {
        const task = get().tasks[taskId]
        if (!task) return
        set(s => ({
          tasks: {
            ...s.tasks,
            [taskId]: {
              ...task,
              steps: task.steps.map(st =>
                st.id === stepId ? { ...st, completed: !st.completed } : st
              ),
            },
          },
        }))
      },

      addSubGoal: (goalId, directionId, title) => {
        const newId = `sg_${uid()}`
        const sgs = Object.values(get().subGoals).filter(sg => sg.goalId === goalId)
        const sg: SubGoal = {
          id: newId,
          title,
          goalId,
          directionId,
          order: sgs.length,
          taskIds: [],
        }
        set(s => ({ subGoals: { ...s.subGoals, [newId]: sg } }))
      },

      updateSubGoal: (id, patch) =>
        set(s => ({ subGoals: { ...s.subGoals, [id]: { ...s.subGoals[id], ...patch } } })),

      deleteSubGoal: (id) => {
        set(s => {
          const subGoals = { ...s.subGoals }
          const sg = subGoals[id]
          const tasks = { ...s.tasks }
          sg?.taskIds.forEach(tid => delete tasks[tid])
          delete subGoals[id]
          return { subGoals, tasks }
        })
      },

      updateGoal: (id, patch) =>
        set(s => ({ goals: { ...s.goals, [id]: { ...s.goals[id], ...patch } } })),

      timerStart: (taskId) => {
        const { timer } = get()
        // If switching tasks, save accumulated to old task
        if (timer.taskId && timer.taskId !== taskId && timer.running) {
          const elapsed = timer.startedAt ? Date.now() - timer.startedAt : 0
          const totalMs = timer.accumulatedMs + elapsed
          get().updateTask(timer.taskId, {
            totalTime: get().tasks[timer.taskId].totalTime + Math.floor(totalMs / 1000),
          })
        }
        const newAccumulated = timer.taskId === taskId ? timer.accumulatedMs : 0
        set({ timer: { taskId, running: true, startedAt: Date.now(), accumulatedMs: newAccumulated } })
      },

      timerPause: () => {
        const { timer } = get()
        if (!timer.running || !timer.startedAt) return
        const elapsed = Date.now() - timer.startedAt
        set({ timer: { ...timer, running: false, startedAt: null, accumulatedMs: timer.accumulatedMs + elapsed } })
      },

      timerStop: () => {
        const { timer } = get()
        if (!timer.taskId) return
        let totalMs = timer.accumulatedMs
        if (timer.running && timer.startedAt) {
          totalMs += Date.now() - timer.startedAt
        }
        const task = get().tasks[timer.taskId]
        if (task) {
          get().updateTask(timer.taskId, { totalTime: task.totalTime + Math.floor(totalMs / 1000) })
        }
        set({ timer: { taskId: null, running: false, startedAt: null, accumulatedMs: 0 } })
      },

      timerTick: () => {
        // No-op: components derive current ms from timer.startedAt + accumulatedMs
      },

      getTasksBySubGoal: (subGoalId) => {
        const sg = get().subGoals[subGoalId]
        if (!sg) return []
        return sg.taskIds.map(id => get().tasks[id]).filter(Boolean)
      },

      getSubGoalsByGoal: (goalId) =>
        Object.values(get().subGoals)
          .filter(sg => sg.goalId === goalId)
          .sort((a, b) => a.order - b.order),

      getGoalByDirection: (directionId) => {
        const dir = get().directions.find(d => d.id === directionId)
        if (!dir) return undefined
        return get().goals[dir.goalId]
      },

      getDirectionById: (id) => get().directions.find(d => d.id === id),

      totalTimeForTask: (taskId) => {
        const task = get().tasks[taskId]
        if (!task) return 0
        const { timer } = get()
        let bonus = 0
        if (timer.taskId === taskId) {
          bonus = timer.accumulatedMs / 1000
          if (timer.running && timer.startedAt) {
            bonus += (Date.now() - timer.startedAt) / 1000
          }
        }
        return task.totalTime + Math.floor(bonus)
      },

      totalTimeForSubGoal: (subGoalId) => {
        const sg = get().subGoals[subGoalId]
        if (!sg) return 0
        return sg.taskIds.reduce((acc, tid) => acc + get().totalTimeForTask(tid), 0)
      },

      totalTimeForGoal: (goalId) => {
        const sgs = get().getSubGoalsByGoal(goalId)
        return sgs.reduce((acc, sg) => acc + get().totalTimeForSubGoal(sg.id), 0)
      },

      totalTimeForDirection: (directionId) => {
        const goal = get().getGoalByDirection(directionId)
        if (!goal) return 0
        return get().totalTimeForGoal(goal.id)
      },

      filteredTasks: () => {
        const { tasks, searchQuery, statusFilter, directionFilter } = get()
        return Object.values(tasks).filter(t => {
          if (statusFilter !== 'all' && t.status !== statusFilter) return false
          if (directionFilter !== 'all' && t.directionId !== directionFilter) return false
          if (searchQuery) {
            const q = searchQuery.toLowerCase()
            if (!t.title.toLowerCase().includes(q)) return false
          }
          return true
        })
      },
    }),
    {
      name: 'chief-console-v4',
      partialize: (state) => ({
        tasks: state.tasks,
        subGoals: state.subGoals,
        goals: state.goals,
        directions: state.directions,
        focusTaskId: state.focusTaskId,
        selectedDirectionId: state.selectedDirectionId,
      }),
    }
  )
)
