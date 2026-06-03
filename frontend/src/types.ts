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
}

export interface WorkSession {
  id: number
  task_id: number
  started_at: string
  ended_at: string | null
  duration_actual: number | null
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

export type Screen = 'main' | 'settings' | 'archive' | 'stats' | 'journal' | 'trash'
