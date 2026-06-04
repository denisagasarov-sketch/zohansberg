import { useState } from 'react'
import FreeKick3D from './FreeKick3D'
import ArtilleryGame from './ArtilleryGame'

type Game = 'kick' | 'arty'

export default function GameArcade() {
  const [game, setGame] = useState<Game>(() => (localStorage.getItem('arcade_game') as Game) || 'kick')
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
      {game === 'kick' ? <FreeKick3D /> : <ArtilleryGame />}
    </div>
  )
}
