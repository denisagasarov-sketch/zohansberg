import { useState, useEffect } from 'react'
import { api } from '../../api'

interface Props {
  onClose: () => void
}

function fmtSec(s: number) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60)
  if (h > 0) return `${h}ч ${m}м`
  return `${m}м`
}

function buildText(data: any): string {
  const lines: string[] = []

  if (data.yesterday?.length > 0) {
    lines.push('📌 Вчера:')
    data.yesterday.forEach((r: any) => {
      const note = r.notes?.split(' | ').filter(Boolean).join(', ')
      lines.push(`• ${r.title}${r.direction ? ` [${r.direction}]` : ''} — ${fmtSec(r.seconds)}${note ? ` (${note})` : ''}`)
    })
  } else if (data.today_done?.length > 0) {
    lines.push('✅ Выполнено сегодня:')
    data.today_done.forEach((t: string) => lines.push(`• ${t}`))
  }

  lines.push('')

  if (data.today?.length > 0) {
    lines.push('🔄 Сейчас в работе:')
    data.today.forEach((r: any) => {
      lines.push(`• ${r.title}${r.direction ? ` [${r.direction}]` : ''}`)
    })
  } else if (data.today_plan?.length > 0) {
    lines.push('📋 План на сегодня:')
    data.today_plan.forEach((t: string) => lines.push(`• ${t}`))
  }

  return lines.join('\n').trim()
}

export default function StandupModal({ onClose }: Props) {
  const [data, setData] = useState<any>(null)
  const [copied, setCopied] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getStandup().then(d => { setData(d); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  const text = data ? buildText(data) : ''

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-2xl w-full max-w-md shadow-2xl overflow-hidden"
        style={{ animation: 'fadeSlideIn 0.18s ease-out' }}>

        <div className="px-5 pt-5 pb-3 border-b border-[#252525]">
          <div className="text-[10px] font-semibold tracking-widest text-[#5060a0] uppercase mb-1">Стендап</div>
          <h2 className="text-lg font-bold text-[#f0f0f0]">Что скажу команде</h2>
        </div>

        <div className="px-5 py-4">
          {loading ? (
            <p className="text-sm text-[#555]">Загрузка…</p>
          ) : (
            <textarea
              value={text}
              onChange={() => {}}
              readOnly
              rows={Math.min(15, text.split('\n').length + 1)}
              className="w-full bg-[#141414] border border-[#252525] rounded-xl px-3 py-3 text-sm text-[#c0c0c0] resize-none focus:outline-none font-mono leading-relaxed"
            />
          )}
        </div>

        <div className="px-5 pb-5 flex gap-2">
          <button onClick={onClose} className="flex-1 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-xl text-sm text-[#666] transition-colors">
            Закрыть
          </button>
          <button onClick={handleCopy} disabled={!text}
            className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-colors ${copied ? 'bg-[#1a3a1a] text-[#7ab87a]' : 'bg-[#5060a0] hover:bg-[#8090c8] text-white'}`}>
            {copied ? '✓ Скопировано' : 'Копировать'}
          </button>
        </div>
      </div>
    </div>
  )
}
