import { useState, useEffect } from 'react'

interface Props {
  elapsed: number       // how long paused (seconds), shown as rest time
  onResume: () => void
}

const TIPS = [
  'Встань и потянись',
  'Выпей стакан воды',
  'Посмотри вдаль 20 секунд',
  'Сделай несколько глубоких вдохов',
  'Разомни шею и плечи',
  'Выйди на свежий воздух',
  'Закрой глаза и отдохни',
]

function padZ(n: number) { return String(n).padStart(2, '0') }

export default function BreakScreen({ elapsed, onResume }: Props) {
  const [tip] = useState(() => TIPS[Math.floor(Math.random() * TIPS.length)])
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const id = setInterval(() => setSeconds(s => s + 1), 1000)
    return () => clearInterval(id)
  }, [])

  const m = Math.floor(seconds / 60)
  const s = seconds % 60

  return (
    <div
      className="fixed inset-0 z-40 flex flex-col items-center justify-center"
      style={{ background: 'linear-gradient(160deg, #0d1a0d 0%, #0d0d1a 100%)' }}
    >
      {/* Tip */}
      <div className="text-[10px] font-semibold tracking-widest text-[#4a7a4a] uppercase mb-6">{tip}</div>

      {/* Big break clock */}
      <div className="text-8xl font-mono font-bold tabular-nums text-[#2a4a2a] mb-2 select-none">
        {padZ(m)}:{padZ(s)}
      </div>
      <div className="text-sm text-[#2a4a2a] mb-16">перерыв</div>

      {/* Resume button */}
      <button
        onClick={onResume}
        className="px-8 py-3 bg-[#1a3a1a] hover:bg-[#2a5a2a] border border-[#4a7a4a]/40 rounded-2xl text-sm text-[#7ab87a] transition-colors font-medium"
      >
        ▶ Вернуться к работе
      </button>

      {/* Elapsed session time hint */}
      <p className="mt-6 text-[10px] text-[#1a3a1a]">
        Сессия: {padZ(Math.floor(elapsed / 60))}:{padZ(elapsed % 60)}
      </p>
    </div>
  )
}
