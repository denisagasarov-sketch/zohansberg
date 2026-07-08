// Нить дня: единая хронологическая лента — цель утра, закрытые шаги, заметки сессий,
// мысли, завершённые задачи. Контекст дня «держится» и виден вечером одним потоком.
import { useState, useEffect, useCallback } from 'react'
import type { DayThread, DayThreadEvent } from '../types'
import { api } from '../api'
import Icon, { MoodIcon, type IconName } from './Icon'
import { localKey } from '../utils/sprint'

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

export default function DayThreadBlock({ onOpenTask }: { onOpenTask?: (taskId: number) => void } = {}) {
  const [thread, setThread] = useState<DayThread | null>(null)
  const [open, setOpen] = useState(true)

  const load = useCallback(() => {
    api.getDayThread(localKey(new Date())).then(setThread).catch(() => {})
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
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <button onClick={() => setOpen(v => !v)} className="w-full px-4 py-2.5 flex items-center gap-2 text-left hover:bg-raised/60 transition-colors">
        <span className="section-label">Нить дня</span>
        <span className="text-xs text-[#9c958a]">{fmt(totals.seconds)} · {totals.subtasks_done} шаг. · {totals.tasks_done} задач</span>
        <span className="ml-auto text-[#9c958a] text-xs">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="px-4 pb-3 border-t border-[#2a2723] pt-3">
          {checkin?.goal && (
            <div className="flex items-start gap-2 mb-3">
              <span className="text-[#eab26c] shrink-0 mt-0.5">{checkin.mood ? <MoodIcon mood={checkin.mood} size={16} /> : <Icon name="sun" size={16} />}</span>
              <div>
                <div className="text-[10px] text-[#d89a4e] uppercase tracking-wide">Цель дня</div>
                <div className="text-sm text-[#ece7df]">{checkin.goal}</div>
              </div>
            </div>
          )}
          {events.length === 0 ? (
            <div className="text-xs text-[#9c958a]">Пока пусто — начни первый подход</div>
          ) : (
            <ul className="space-y-1.5">
              {events.map((e, i) => {
                const clickable = !!(e.task_id && onOpenTask)
                return (
                <li
                  key={i}
                  onClick={clickable ? () => onOpenTask!(e.task_id!) : undefined}
                  title={clickable ? 'Открыть задачу' : undefined}
                  className={`flex items-start gap-2 text-sm rounded ${clickable ? 'cursor-pointer hover:bg-raised/60 -mx-1 px-1' : ''}`}
                >
                  <span className="text-[#6f695f] text-[10px] tabular-nums w-9 shrink-0 mt-0.5">{time(e.at)}</span>
                  <span className={`shrink-0 mt-0.5 ${e.kind === 'subtask_done' || e.kind === 'task_done' ? 'text-[#82a877]' : 'text-[#9c958a]'}`}><Icon name={eventIcon(e.kind)} size={13} /></span>
                  <span className="flex-1">
                    <span className={e.kind === 'thought' || e.kind === 'session_note' ? 'text-[#b0a793]' : 'text-[#ddd6cb]'}>{e.text}</span>
                    {e.task && <span className="text-[10px] text-[#6f695f]"> · {e.task}</span>}
                    {e.seconds ? <span className="text-[10px] text-[#e0a458]"> · {fmt(e.seconds)}</span> : null}
                  </span>
                </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
