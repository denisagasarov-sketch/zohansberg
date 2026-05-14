import { useState } from 'react'
import { playSound } from '../../sound'

interface Props {
  onClose: () => void
  onSave: (mood: number, goal: string, content: string) => void
}

const MOODS = [
  { value: 1, emoji: '😔' },
  { value: 2, emoji: '😐' },
  { value: 3, emoji: '🙂' },
  { value: 4, emoji: '😄' },
  { value: 5, emoji: '🚀' },
]

function formatDate() {
  const now = new Date()
  const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
  return `${now.getDate()} ${months[now.getMonth()]}`
}

export default function CheckinModal({ onClose, onSave }: Props) {
  const [mood, setMood] = useState<number | null>(null)
  const [goal, setGoal] = useState('')
  const [content, setContent] = useState('')

  const handleSave = () => {
    if (!mood) return
    playSound('checkin_save')
    onSave(mood, goal, content)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/70" />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[#f0f0f0] font-semibold">Доброе утро</h2>
            <p className="text-[#666] text-sm">{formatDate()}</p>
          </div>
          <button onClick={onClose} className="text-[#666] hover:text-[#f0f0f0] text-xl leading-none">×</button>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-[#666] mb-3">Как ты сегодня?</label>
          <div className="flex gap-3 justify-center">
            {MOODS.map(m => (
              <button
                key={m.value}
                onClick={() => setMood(m.value)}
                className={`text-3xl transition-all duration-150 ${
                  mood === m.value ? 'scale-125' : 'opacity-50 hover:opacity-80'
                }`}
              >
                {m.emoji}
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <label className="block text-sm text-[#666] mb-1.5">Главная цель дня</label>
          <textarea
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="Что важно сделать сегодня?"
            rows={2}
            className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838]"
          />
        </div>

        <div className="mb-5">
          <label className="block text-sm text-[#666] mb-1.5">Свободные мысли</label>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Что у тебя на уме?"
            rows={3}
            className="w-full bg-[#141414] border border-[#252525] rounded px-3 py-2 text-[#f0f0f0] text-sm focus:outline-none focus:border-[#5060a0] resize-none placeholder-[#383838]"
          />
        </div>

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-[#666] hover:text-[#f0f0f0] text-sm transition-colors">Пропустить</button>
          <button
            onClick={handleSave}
            disabled={!mood}
            className="px-5 py-2 bg-[#5060a0] hover:bg-[#8090c8] disabled:opacity-40 rounded-lg text-sm text-white transition-colors"
          >
            Начать день →
          </button>
        </div>
      </div>
    </div>
  )
}
