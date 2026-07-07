// Нить дня: единая хронологическая лента — цель утра, закрытые шаги, заметки сессий,
// мысли, завершённые задачи. Контекст дня «держится» и виден вечером одним потоком.
import { useState, useEffect, useCallback } from 'react'
import type { DayThread, DayThreadEvent } from '../types'
import { api } from '../api'
import Icon, { MoodIcon, type IconName } from './Icon'

function fmt(s: number): string {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}ч ${m}м` : `${m}м`
}
function time(iso: string) {
  return new Date(iso.replace(' ', 'T')).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}
function eventIcon(k: DayThreadEvent['kind']): IconName {
  return k === 'subtask_done' ? 'check' : k === 'task_done' ? 'target' : k === 'session_note' ? 'note' : 'thought'
}

export default function DayThreadBlock() {
  const [thread, setThread] = useState<DayThread | null>(null)
  const [open, setOpen] = useState(true)

  const load = useCallback(() => {
    api.getDayThread(new Date().toISOString().slice(0, 10)).then(setThread).catch(() => {})
  }, [])
  useEffect(() => {
    load()
    const h = () => load()
    window.addEventListener('gamification-updated', h)
    window.addEventListener('journal-updated', h)
    return () => { window.removeEventListener('gamification-updated', h); window.removeEventListener('journal-updated', h) }
  }, [load])

  if (!thread) return null
  const { events, totals, checkin } = thread
  if (events.length === 0 && !checkin?.goal) return null

  return (
    <div className="bg-[#1c1c1c] border border-[#252525] rounded-lg overflow-hidden">
      <button onClick={() => setOpen(v => !v)} className="w-full px-4 py-2.5 flex items-center gap-2 text-left hover:bg-[#252525]/40 transition-colors">
        <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase">Нить дня</span>
        <span className="text-xs text-[#666]">{fmt(totals.seconds)} · {totals.subtasks_done} шаг. · {totals.tasks_done} задач</span>
        <span className="ml-auto text-[#666] text-xs">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="px-4 pb-3 border-t border-[#252525] pt-3">
          {checkin?.goal && (
            <div className="flex items-start gap-2 mb-3">
              <span className="text-[#8090c8] shrink-0 mt-0.5">{checkin.mood ? <MoodIcon mood={checkin.mood} size={16} /> : <Icon name="sun" size={16} />}</span>
              <div>
                <div className="text-[10px] text-[#5a6db0] uppercase tracking-wide">Цель дня</div>
                <div className="text-sm text-[#f0f0f0]">{checkin.goal}</div>
              </div>
            </div>
          )}
          {events.length === 0 ? (
            <div className="text-xs text-[#666]">Пока пусто — начни первый подход</div>
          ) : (
            <ul className="space-y-1.5">
              {events.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <span className="text-[#555] text-[10px] tabular-nums w-9 shrink-0 mt-0.5">{time(e.at)}</span>
                  <span className={`shrink-0 mt-0.5 ${e.kind === 'subtask_done' || e.kind === 'task_done' ? 'text-[#4a9d5f]' : 'text-[#666]'}`}><Icon name={eventIcon(e.kind)} size={13} /></span>
                  <span className="flex-1">
                    <span className={e.kind === 'thought' || e.kind === 'session_note' ? 'text-[#9aa4c8]' : 'text-[#e0e0e0]'}>{e.text}</span>
                    {e.task && <span className="text-[10px] text-[#555]"> · {e.task}</span>}
                    {e.seconds ? <span className="text-[10px] text-[#5060a0]"> · {fmt(e.seconds)}</span> : null}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
