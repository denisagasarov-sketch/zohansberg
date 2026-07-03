// Полоска над «Сейчас»: цель дня из утреннего чек-ина.
// Раньше чек-ин исчезал сразу после сохранения — данные вносились «в никуда».
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

const MOOD_EMOJI: Record<number, string> = { 1: '😔', 2: '😐', 3: '🙂', 4: '😄', 5: '🚀' }

export default function TodayGoalBar({ checkin, onCheckin, onOpenJournal }: Props) {
  if (!checkin) return null

  if (!checkin.exists) {
    return (
      <button
        onClick={onCheckin}
        className="w-full bg-[#1c1c1c] border border-dashed border-[#383838] hover:border-[#5060a0] rounded-lg px-4 py-2 flex items-center gap-2 text-sm text-[#666] hover:text-[#8090c8] transition-colors"
      >
        <span>☀</span>
        <span>Утренний чек-ин — задай цель дня</span>
      </button>
    )
  }

  const goalText = checkin.goal?.trim() || checkin.content?.trim() || ''
  return (
    <div
      onClick={onOpenJournal}
      title="Открыть дневник"
      className="bg-[#1c1c1c] border border-[#252525] hover:border-[#383838] rounded-lg px-4 py-2 flex items-center gap-2.5 cursor-pointer transition-colors"
    >
      <span className="text-base leading-none">{MOOD_EMOJI[checkin.mood ?? 0] ?? '☀'}</span>
      <span className="text-[10px] font-semibold tracking-widest text-[#383838] uppercase shrink-0">Цель дня</span>
      <span className="flex-1 text-sm text-[#f0f0f0] truncate">
        {goalText || <span className="text-[#666]">без цели — просто хороший день</span>}
      </span>
      <span className="text-[#383838] text-xs shrink-0">📓</span>
    </div>
  )
}
