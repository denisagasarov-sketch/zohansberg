export interface Direction {
  id: number
  name: string
  order_index: number
  archived: number
  created_at: string
  notes: string | null
  weekly_goal_seconds: number
}

export interface Task {
  id: number
  title: string
  direction_id: number | null
  priority: 'I' | 'II' | 'III' | 'none'
  slot: 'now' | 'queue'
  slot_order: number
  direction_order: number
  deadline: string | null
  duration_plan: number | null
  duration_fact: number
  notes: string | null
  created_at: string
  updated_at: string
  in_queue: boolean
  someday: boolean
  done_at: string | null
  deleted_at: string | null
  direction_name?: string
  recurrence: 'daily' | 'weekdays' | 'weekly' | 'monthly' | null
  recurrence_last_date: string | null
}

export interface WorkSession {
  id: number
  task_id: number
  started_at: string
  ended_at: string | null
  duration_actual: number | null
  note?: string | null
  subtask_id?: number | null
}

export interface Subtask {
  id: number
  task_id: number
  title: string
  done_at: string | null
  order_index: number
  created_at: string
}

export interface Gamification {
  streak: number
  best_streak: number
  active_days_total: number
  today: { seconds: number; subtasks_done: number; tasks_done: number }
  heatmap: { day: string; seconds: number }[]
}

export interface DayThreadEvent {
  at: string
  kind: 'subtask_done' | 'session_note' | 'thought' | 'task_done'
  text: string
  task?: string
  seconds?: number | null
}

export interface DayThread {
  date: string
  checkin: { mood: number | null; goal: string | null; content: string | null; created_at: string } | null
  events: DayThreadEvent[]
  totals: { seconds: number; subtasks_done: number; tasks_done: number }
}

export interface JournalEntry {
  id: number
  type: 'checkin' | 'thought'
  mood: number | null
  goal: string | null
  content: string | null
  created_at: string
}

export interface Settings {
  timer_duration?: string
  timer_sound?: string
  sounds_enabled?: string
  sounds_volume?: string
  claude_api_key?: string
}

export type Screen = 'main' | 'settings' | 'archive' | 'stats' | 'journal' | 'trash' | 'horizon'
