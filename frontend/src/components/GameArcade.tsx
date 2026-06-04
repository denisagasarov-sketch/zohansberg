import { useState, lazy, Suspense } from 'react'
import ArtilleryGame from './ArtilleryGame'
import ErrorBoundary from './ErrorBoundary'

// 3D game is loaded lazily so three.js stays out of the main bundle —
// if it fails to load/run, only the game falls back, the app keeps working.
const FreeKick3D = lazy(() => import('./FreeKick3D'))

type Game = 'kick' | 'arty'

export default function GameArcade() {
  const [game, setGame] = useState<Game>(() => (localStorage.getItem('arcade_game') as Game) || 'arty')
  const pick = (g: Game) => { setGame(g); localStorage.setItem('arcade_game', g) }

  const tab = (g: Game, label: string) => (
    <button
      onClick={() => pick(g)}
      className={`px-3 py-1 rounded text-xs transition-colors ${game === g ? 'bg-[#5060a0] text-white' : 'bg-[#252525] text-[#888] hover:bg-[#383838]'}`}
    >{label}</button>
  )

  return (
    <div className="w-full" onClick={e => e.stopPropagation()}>
      <div className="flex gap-1.5 justify-center mb-2">
        {tab('kick', '⚽ Штрафной 3D')}
        {tab('arty', '💥 Артиллерия')}
      </div>
      {game === 'kick' ? (
        <ErrorBoundary fallback={<div className="text-[12px] text-[#777] text-center py-10">3D-режим не запустился в этом окружении</div>}>
          <Suspense fallback={<div className="text-[12px] text-[#666] text-center py-10">Загрузка 3D…</div>}>
            <FreeKick3D />
          </Suspense>
        </ErrorBoundary>
      ) : <ArtilleryGame />}
    </div>
  )
}
