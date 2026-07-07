import type { Task } from '../../types'

interface Props {
  queueTasks: Task[]
  onStartNext: (taskId: number) => void
  onChoose: () => void
  onLeaveEmpty: () => void
}

export default function AfterDoneModal({ queueTasks, onStartNext, onChoose, onLeaveEmpty }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onLeaveEmpty} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-xl p-6 w-full max-w-sm shadow-2xl">
        <h2 className="text-[#f0f0f0] font-semibold mb-1">Задача выполнена</h2>
        <p className="text-[#666] text-sm mb-5">Что дальше?</p>

        <div className="flex flex-col gap-2">
          {queueTasks.length > 0 && (
            <button
              onClick={() => onStartNext(queueTasks[0].id)}
              className="px-4 py-2.5 bg-[#5060a0] hover:bg-[#8090c8] rounded-lg text-sm text-white transition-colors text-left"
            >
              <div className="text-xs text-[#8090c8]/70 mb-0.5">Начать первую из очереди</div>
              <div className="font-medium truncate">{queueTasks[0].title}</div>
            </button>
          )}
          <button
            onClick={onChoose}
            className="px-4 py-2.5 bg-[#252525] hover:bg-[#383838] rounded-lg text-sm text-[#f0f0f0] transition-colors"
          >
            Выбрать сам
          </button>
          <button
            onClick={onLeaveEmpty}
            className="px-4 py-2.5 text-[#666] hover:text-[#f0f0f0] text-sm transition-colors"
          >
            Оставить пустым
          </button>
        </div>
      </div>
    </div>
  )
}
