// Полоска над «Сейчас»: цель дня из утреннего чек-ина.
// Раньше чек-ин исчезал сразу после сохранения — данные вносились «в никуда».
import Icon, { MoodIcon } from './Icon'

export interface TodayCheckin {
  exists: boolean
  mood?: number | null
  goal?: string | null
  content?: string | null
}

interface Props {
  checkin: TodayCheckin | null
  onCheckin: () => void
  onOpenJournal: () => void
}

export default function TodayGoalBar({ checkin, onCheckin, onOpenJournal }: Props) {
  if (!checkin) return null

  if (!checkin.exists) {
    return (
      <button
        onClick={onCheckin}
        className="w-full border border-dashed border-border-strong hover:border-accent/60 rounded-xl px-4 py-1.5 flex items-center justify-center gap-2 text-[13px] text-text-muted hover:text-accent-light transition-colors"
      >
        <Icon name="sun" size={15} />
        <span>Утренний чек-ин — задай цель дня</span>
      </button>
    )
  }

  // Показываем только осознанную цель — свободные мысли из чек-ина сюда не подставляем
  const goalText = checkin.goal?.trim() || ''
  return (
    <div
      onClick={onOpenJournal}
      title="Открыть дневник"
      className="px-1.5 py-0.5 flex items-center gap-2.5 cursor-pointer group select-none"
    >
      <span className="text-accent-light shrink-0">{checkin.mood ? <MoodIcon mood={checkin.mood} size={17} /> : <Icon name="sun" size={17} />}</span>
      <span className="section-label shrink-0">Цель дня</span>
      <span className="flex-1 text-[13px] text-text truncate">
        {goalText || <span className="text-text-secondary">без цели — просто хороший день</span>}
      </span>
      <span className="text-text-faint group-hover:text-text-secondary transition-colors shrink-0"><Icon name="book" size={14} /></span>
    </div>
  )
}
