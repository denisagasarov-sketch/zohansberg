interface Props {
  taskTitle: string
  onStay: () => void
  onSwitch: () => void
}

export default function FocusSwitchModal({ taskTitle, onStay, onSwitch }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/65 backdrop-blur-[4px]" onClick={onStay} />
      <div className="relative z-10 animate-scale-in bg-overlay border border-border-strong rounded-2xl p-6 w-full max-w-xs shadow-2xl">
        <h2 className="text-[#ece7df] font-semibold mb-1">Режим фокуса активен</h2>
        <p className="text-[#9c958a] text-sm mb-1">Ты точно хочешь переключиться?</p>
        <p className="text-[#4a463f] text-xs mb-5 truncate">→ {taskTitle}</p>
        <p className="text-[#6f695f] text-xs mb-5">Текущее время будет сохранено.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={onStay} className="px-4 py-2 bg-raised hover:bg-border-strong rounded-lg text-sm text-[#9c958a] transition-colors">
            Остаться
          </button>
          <button onClick={onSwitch} className="px-4 py-2 bg-accent hover:bg-accent-light rounded-lg text-sm text-[#1c1610] font-medium transition-colors">
            Переключиться
          </button>
        </div>
      </div>
    </div>
  )
}
