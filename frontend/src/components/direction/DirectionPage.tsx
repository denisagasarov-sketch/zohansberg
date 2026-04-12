import { useState } from 'react'
import { useStore } from '../../store/useStore'
import { InlineEdit } from '../InlineEdit'
import { SubGoalItem } from './SubGoalItem'
import { formatDuration } from '../../utils/time'

export function DirectionPage() {
  const {
    directions, selectedDirectionId, setSelectedDirection,
    goals, getGoalByDirection, getSubGoalsByGoal,
    updateGoal, addSubGoal,
    totalTimeForGoal, totalTimeForDirection,
  } = useStore()

  const goal = getGoalByDirection(selectedDirectionId)
  const subGoals = goal ? getSubGoalsByGoal(goal.id) : []
  const directionTime = totalTimeForDirection(selectedDirectionId)

  return (
    <div className="flex flex-col h-full">
      {/* Direction tabs */}
      <div className="flex gap-0.5 mb-5 flex-wrap">
        {directions.map(d => (
          <button
            key={d.id}
            onClick={() => setSelectedDirection(d.id)}
            className={`px-3 py-1.5 text-xs font-mono rounded transition-all ${
              selectedDirectionId === d.id
                ? 'bg-[#1f1f23] border border-[#3a3a44] text-[#e8e8f0]'
                : 'text-[#4a4a55] hover:text-[#8b8b9a] border border-transparent hover:border-[#2a2a31]'
            }`}
          >
            {d.name}
          </button>
        ))}
      </div>

      {goal && (
        <div className="flex-1 overflow-y-auto min-h-0">
          {/* Goal header */}
          <div className="mb-5 pb-4 border-b border-[#1f1f23]">
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <div className="text-[10px] uppercase tracking-widest text-[#4a4a55] font-mono mb-1.5">Direction goal</div>
                <InlineEdit
                  value={goal.title}
                  onSave={(v) => updateGoal(goal.id, { title: v })}
                  className="text-base font-medium text-[#c8c8d4] leading-snug"
                />
              </div>
              {directionTime > 0 && (
                <div className="flex-shrink-0 text-right">
                  <div className="text-[10px] uppercase tracking-wider text-[#4a4a55] font-mono mb-0.5">Total time</div>
                  <div className="font-mono text-sm text-[#6b6b7a]">{formatDuration(directionTime)}</div>
                </div>
              )}
            </div>
          </div>

          {/* Sub-goals */}
          <div className="flex flex-col gap-3">
            {subGoals.map(sg => (
              <SubGoalItem key={sg.id} subGoalId={sg.id} goalId={goal.id} />
            ))}
          </div>

          {/* Add sub-goal */}
          <AddSubGoalInput goalId={goal.id} directionId={selectedDirectionId} />
        </div>
      )}
    </div>
  )
}

function AddSubGoalInput({ goalId, directionId }: { goalId: string; directionId: string }) {
  const { addSubGoal } = useStore()
  const [value, setValue] = useState('')

  const commit = () => {
    const t = value.trim()
    if (!t) return
    addSubGoal(goalId, directionId, t)
    setValue('')
  }

  return (
    <div className="mt-4 flex items-center gap-2">
      <input
        type="text"
        value={value}
        onChange={e => setValue(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') commit() }}
        placeholder="+ Add sub-goal..."
        className="flex-1 bg-transparent border-b border-[#2a2a31] focus:border-[#3b82f6] outline-none text-sm text-[#8b8b9a] placeholder-[#2a2a31] py-1.5 transition-colors"
      />
      {value.trim() && (
        <button onClick={commit} className="text-xs text-[#3b82f6] font-mono">Add</button>
      )}
    </div>
  )
}
