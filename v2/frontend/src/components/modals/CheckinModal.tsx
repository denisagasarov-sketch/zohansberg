import { useState } from 'react'
import { playSound } from '../../sound'
import { MoodIcon } from '../Icon'

interface Props {
  onClose: () => void
  onSave: (mood: number, goal: string, content: string) => void
}

const MOODS = [1, 2, 3, 4, 5]

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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: 'radial-gradient(80% 60% at 50% 0%, rgba(30,26,21,0.97) 0%, rgba(16,15,14,0.98) 100%)' }}>
      <div className="relative z-10 animate-rise-in bg-overlay border border-border-strong rounded-2xl p-6 w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-[#ece7df] font-semibold">Доброе утро</h2>
            <p className="text-[#9c958a] text-sm">{formatDate()}</p>
          </div>
          <button onClick={onClose} className="text-[#9c958a] hover:text-[#ece7df] text-xl leading-none">×</button>
        </div>

        <div className="mb-4">
          <label className="block text-sm text-[#9c958a] mb-3">Как ты сегодня?</label>
          <div className="flex gap-4 justify-center">
            {MOODS.map(m => (
              <button
                key={m}
                onClick={() => setMood(m)}
                className={`transition-all duration-150 ${
                  mood === m ? 'text-[#eab26c] scale-125' : 'text-[#6f695f] hover:text-[#8d8679]'
                }`}
                aria-label={`Настроение ${m}`}
              >
                <MoodIcon mood={m} size={30} />
              </button>
            ))}
          </div>
        </div>

        <div className="mb-3">
          <label className="block text-sm text-[#9c958a] mb-1.5">Главная цель дня</label>
          <textarea
            value={goal}
            onChange={e => setGoal(e.target.value)}
            placeholder="Что важно сделать сегодня?"
            rows={2}
            className="w-full bg-[#0f0e0d] border border-[#2a2723] rounded px-3 py-2 text-[#ece7df] text-sm focus:outline-none focus:border-[#e0a458] resize-none placeholder-[#4a463f]"
          />
        </div>

        <div className="mb-5">
          <label className="block text-sm text-[#9c958a] mb-1.5">Свободные мысли</label>
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            placeholder="Что у тебя на уме?"
            rows={3}
            className="w-full bg-[#0f0e0d] border border-[#2a2723] rounded px-3 py-2 text-[#ece7df] text-sm focus:outline-none focus:border-[#e0a458] resize-none placeholder-[#4a463f]"
          />
        </div>

        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-[#9c958a] hover:text-[#ece7df] text-sm transition-colors">Пропустить</button>
          <button
            onClick={handleSave}
            disabled={!mood}
            className="px-5 py-2 bg-accent hover:bg-accent-light disabled:opacity-40 rounded-lg text-sm text-[#1c1610] font-medium transition-colors"
          >
            Начать день →
          </button>
        </div>
      </div>
    </div>
  )
}
