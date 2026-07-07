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
      <div className="absolute inset-0 bg-black/65 backdrop-blur-[4px]" onClick={onLeaveEmpty} />
      <div className="relative z-10 animate-scale-in bg-overlay border border-border-strong rounded-2xl p-6 w-full max-w-sm shadow-2xl">
        <h2 className="text-[#ece7df] font-semibold mb-1">Задача выполнена</h2>
        <p className="text-[#9c958a] text-sm mb-5">Что дальше?</p>

        <div className="flex flex-col gap-2">
          {queueTasks.length > 0 && (
            <button
              onClick={() => onStartNext(queueTasks[0].id)}
              className="px-4 py-2.5 bg-accent hover:bg-accent-light rounded-lg text-sm text-[#1c1610] font-medium transition-colors text-left"
            >
              <div className="text-xs text-[#eab26c]/70 mb-0.5">Начать первую из очереди</div>
              <div className="font-medium truncate">{queueTasks[0].title}</div>
            </button>
          )}
          <button
            onClick={onChoose}
            className="px-4 py-2.5 bg-raised hover:bg-border-strong rounded-lg text-sm text-[#ece7df] transition-colors"
          >
            Выбрать сам
          </button>
          <button
            onClick={onLeaveEmpty}
            className="px-4 py-2.5 text-[#9c958a] hover:text-[#ece7df] text-sm transition-colors"
          >
            Оставить пустым
          </button>
        </div>
      </div>
    </div>
  )
}
