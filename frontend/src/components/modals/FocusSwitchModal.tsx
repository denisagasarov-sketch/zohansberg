interface Props {
  taskTitle: string
  onStay: () => void
  onSwitch: () => void
}

export default function FocusSwitchModal({ taskTitle, onStay, onSwitch }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onStay} />
      <div className="relative z-10 bg-[#1c1c1c] border border-[#252525] rounded-xl p-6 w-full max-w-xs shadow-2xl">
        <h2 className="text-[#f0f0f0] font-semibold mb-1">Режим фокуса активен</h2>
        <p className="text-[#666] text-sm mb-1">Ты точно хочешь переключиться?</p>
        <p className="text-[#383838] text-xs mb-5 truncate">→ {taskTitle}</p>
        <p className="text-[#555] text-xs mb-5">Текущее время будет сохранено.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onStay} className="px-4 py-2 bg-[#252525] hover:bg-[#383838] rounded-lg text-sm text-[#666] transition-colors">
            Остаться
          </button>
          <button onClick={onSwitch} className="px-4 py-2 bg-[#5060a0] hover:bg-[#8090c8] rounded-lg text-sm text-white transition-colors">
            Переключиться
          </button>
        </div>
      </div>
    </div>
  )
}
