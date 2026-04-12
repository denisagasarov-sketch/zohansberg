import { useStore } from '../store/useStore'
import type { Page } from '../types'

const PAGES: { id: Page; label: string; desc: string }[] = [
  { id: 1, label: '1', desc: 'Focus' },
  { id: 2, label: '2', desc: 'Direction' },
  { id: 3, label: '3', desc: 'Registry' },
]

export function Nav() {
  const { currentPage, setPage } = useStore()

  return (
    <nav className="fixed bottom-0 left-0 right-0 border-t border-[#2a2a31] bg-[#0a0a0b]/95 backdrop-blur-sm z-50">
      <div className="flex items-center justify-center gap-1 h-12">
        {PAGES.map(p => (
          <button
            key={p.id}
            onClick={() => setPage(p.id)}
            className={`
              flex items-center gap-2 px-6 py-2 text-sm font-mono tracking-wider transition-all
              ${currentPage === p.id
                ? 'text-[#e8e8f0] border-b-2 border-[#3b82f6]'
                : 'text-[#4a4a55] hover:text-[#8b8b9a]'
              }
            `}
          >
            <span className={`w-5 h-5 rounded flex items-center justify-center text-xs font-semibold border
              ${currentPage === p.id
                ? 'border-[#3b82f6] text-[#3b82f6] bg-[#3b82f6]/10'
                : 'border-[#2a2a31] text-[#4a4a55]'
              }`}>
              {p.label}
            </span>
            <span className="hidden sm:inline uppercase text-xs tracking-widest">{p.desc}</span>
          </button>
        ))}
      </div>
    </nav>
  )
}
