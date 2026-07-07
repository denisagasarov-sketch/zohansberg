interface Props {
  onCancel: () => void
  onConfirm: () => void
}

export default function TimerSwitchModal({ onCancel, onConfirm }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-[4px]" onClick={onCancel} />
      <div className="relative z-10 animate-scale-in bg-overlay border border-border-strong rounded-2xl p-6 w-full max-w-xs shadow-2xl">
        <h2 className="text-[#ece7df] font-semibold mb-1">Таймер активен</h2>
        <p className="text-[#9c958a] text-sm mb-5">Остановить и переключить?</p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-raised hover:bg-border-strong rounded-lg text-sm text-[#9c958a] transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-accent hover:bg-accent-light rounded-lg text-sm text-[#1c1610] font-medium transition-colors"
          >
            Остановить и переключить
          </button>
        </div>
      </div>
    </div>
  )
}
