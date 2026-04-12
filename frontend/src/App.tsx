import { useStore } from './store/useStore'
import { Nav } from './components/Nav'
import { FocusPage } from './components/focus/FocusPage'
import { DirectionPage } from './components/direction/DirectionPage'
import { RegistryPage } from './components/registry/RegistryPage'

const PAGE_TITLES: Record<number, string> = {
  1: 'Focus',
  2: 'Direction Map',
  3: 'Registry',
}

export function App() {
  const { currentPage } = useStore()

  return (
    <div className="min-h-screen bg-[#0a0a0b] text-[#c8c8d4] font-sans flex flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-[#1f1f23] flex-shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-[#2a2a31]">Chief Console</span>
          <span className="text-[#1f1f23]">/</span>
          <span className="text-sm font-medium text-[#6b6b7a]">{PAGE_TITLES[currentPage]}</span>
        </div>
        <div className="text-[10px] font-mono text-[#2a2a31] tracking-wider">v4</div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden px-6 pt-5 pb-16 max-w-5xl mx-auto w-full">
        <div className="h-full">
          {currentPage === 1 && <FocusPage />}
          {currentPage === 2 && <DirectionPage />}
          {currentPage === 3 && <RegistryPage />}
        </div>
      </main>

      <Nav />
    </div>
  )
}
