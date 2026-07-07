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
        className="w-full bg-[#1c1c1c] border border-dashed border-[#383838] hover:border-[#5060a0] rounded-lg px-4 py-2 flex items-center gap-2 text-sm text-[#666] hover:text-[#8090c8] transition-colors"
      >
        <Icon name="sun" size={16} />
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
      className="bg-[#1c1c1c] border border-[#252525] hover:border-[#383838] rounded-lg px-4 py-2 flex items-center gap-2.5 cursor-pointer transition-colors"
    >
      <span className="text-[#8090c8] shrink-0">{checkin.mood ? <MoodIcon mood={checkin.mood} size={18} /> : <Icon name="sun" size={18} />}</span>
      <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase shrink-0">Цель дня</span>
      <span className="flex-1 text-sm text-[#f0f0f0] truncate">
        {goalText || <span className="text-[#666]">без цели — просто хороший день</span>}
      </span>
      <span className="text-[#383838] shrink-0"><Icon name="book" size={15} /></span>
    </div>
  )
}
