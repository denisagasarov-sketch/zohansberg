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
      className="fixed inset-0 z-40 flex flex-col items-center justify-center animate-fade-in"
      style={{ background: 'radial-gradient(70% 55% at 50% 42%, #151a13 0%, #0d0f0c 100%)' }}
    >
      {/* Tip */}
      <div className="text-[11px] font-semibold tracking-[0.2em] text-[#7fa878] uppercase mb-8">{tip}</div>

      {/* Big break clock */}
      <div className="text-[96px] font-mono font-semibold tabular-nums leading-none text-[#3d5237] mb-3 select-none">
        {padZ(m)}:{padZ(s)}
      </div>
      <div className="text-sm text-[#3d5237] tracking-wide mb-16">перерыв</div>

      {/* Resume button */}
      <button
        onClick={onResume}
        className="px-8 py-3 bg-[#1b2418] hover:bg-[#243020] border border-[#5f7f58]/40 rounded-2xl text-sm text-[#93b989] transition-colors font-medium"
      >
        ▶ Вернуться к работе
      </button>

      {/* Elapsed session time hint */}
      <p className="mt-8 text-[11px] text-[#2c3627] tabular-nums">
        Сессия: {padZ(Math.floor(elapsed / 60))}:{padZ(elapsed % 60)}
      </p>
    </div>
  )
}
