interface Props {
  onCancel: () => void
  onConfirm: () => void
}

export default function TimerSwitchModal({ onCancel, onConfirm }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-xl p-6 w-full max-w-xs shadow-2xl">
        <h2 className="text-[#f0f0f0] font-semibold mb-1">Таймер активен</h2>
        <p className="text-[#666] text-sm mb-5">Остановить и переключить?</p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-[#252525] hover:bg-[#383838] rounded-lg text-sm text-[#666] transition-colors"
          >
            Отмена
          </button>
          <button
            onClick={onConfirm}
            className="px-4 py-2 bg-[#5060a0] hover:bg-[#8090c8] rounded-lg text-sm text-white transition-colors"
          >
            Остановить и переключить
          </button>
        </div>
      </div>
    </div>
  )
}
