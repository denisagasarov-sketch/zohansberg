export type TaskStatus = 'active' | 'completed' | 'overdue' | 'stuck' | 'inbox' | 'no-next-step'

export interface Step {
  id: string
  title: string
  taskId: string
  completed: boolean
  order: number
}

export interface Task {
  id: string
  title: string
  subGoalId: string
  directionId: string
  status: TaskStatus
  deadline?: string
  steps: Step[]
  totalTime: number // accumulated seconds (manual + timer)
  createdAt: string
  notes?: string
}

export interface SubGoal {
  id: string
  title: string
  goalId: string
  directionId: string
  order: number
  taskIds: string[]
}

export interface Goal {
  id: string
  title: string
  directionId: string
}

export interface Direction {
  id: string
  name: string
  goalId: string
}

export type Page = 1 | 2 | 3

export interface TimerState {
  taskId: string | null
  running: boolean
  startedAt: number | null // Date.now() when last started
  accumulatedMs: number    // ms accumulated before current run
}
