// Монохромные лайн-иконки (stroke=currentColor). Заменяют эмодзи по всему UI.
// Наследуют цвет от родителя, размер задаётся пропом size.
interface Props { name: IconName; size?: number; className?: string; style?: React.CSSProperties }
export type IconName =
  | 'target' | 'book' | 'chart' | 'archive' | 'settings' | 'sunset' | 'message'
  | 'flame' | 'check' | 'note' | 'thought' | 'sparkles' | 'sun' | 'moon'
  | 'clock' | 'bolt' | 'calendar' | 'trash' | 'play'

const P: Record<IconName, JSX.Element> = {
  target: <><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="0.6" fill="currentColor" stroke="none"/></>,
  book: <><path d="M5 4h11a2 2 0 0 1 2 2v14H7a2 2 0 0 1-2-2z"/><path d="M5 16h13"/></>,
  chart: <><path d="M4 20V4"/><path d="M4 20h16"/><rect x="7" y="11" width="3" height="6"/><rect x="13" y="7" width="3" height="10"/></>,
  archive: <><rect x="4" y="5" width="16" height="4"/><path d="M5 9v10h14V9"/><path d="M10 13h4"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"/></>,
  sunset: <><circle cx="12" cy="13" r="4"/><path d="M12 3v2M4 13H2M22 13h-2M5 6l1.5 1.5M19 6l-1.5 1.5M2 20h20"/></>,
  message: <><path d="M4 5h16v11H9l-4 4z"/></>,
  flame: <><path d="M12 3c1 3-1 4-1 6a3 3 0 0 0 6 0c0 4-2 6-2 6a4 4 0 0 1-8 0c0-3 2-4 3-6 1.5 1 2 3 2 3 1-2 2-4 2-9z"/></>,
  check: <><path d="M5 12l4 4 10-10"/></>,
  note: <><path d="M5 4h10l4 4v12H5z"/><path d="M15 4v4h4M8 13h7M8 16h5"/></>,
  thought: <><path d="M6 10a5 5 0 0 1 9-3 4 4 0 0 1 1 8H8a4 4 0 0 1-2-5z"/></>,
  sparkles: <><path d="M12 4l1.5 4L18 9.5 13.5 11 12 15l-1.5-4L6 9.5 10.5 8z"/></>,
  sun: <><circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M6 6l1.5 1.5M16.5 16.5L18 18M18 6l-1.5 1.5M7.5 16.5L6 18"/></>,
  moon: <><path d="M18 14a7 7 0 0 1-9-9 7 7 0 1 0 9 9z"/></>,
  clock: <><circle cx="12" cy="12" r="8"/><path d="M12 7v5l3 2"/></>,
  bolt: <><path d="M13 3L5 13h6l-1 8 8-10h-6z"/></>,
  calendar: <><rect x="4" y="5" width="16" height="16" rx="1"/><path d="M4 9h16M8 3v4M16 3v4"/></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/></>,
  play: <><path d="M7 5l12 7-12 7z"/></>,
}

export default function Icon({ name, size = 18, className, style }: Props) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      className={className} style={style} aria-hidden="true">
      {P[name]}
    </svg>
  )
}

// Иконка настроения 1–5 (лайн-лицо) вместо эмодзи
export function MoodIcon({ mood, size = 20 }: { mood: number; size?: number }) {
  const mouth = mood <= 1 ? 'M8.5 16c1-1.5 2-2 3.5-2s2.5.5 3.5 2'
    : mood === 2 ? 'M8.5 15.5h7'
    : mood === 3 ? 'M8.5 15h7'
    : 'M8.5 14.5c1 1.5 2 2 3.5 2s2.5-.5 3.5-2'
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M9 10h.01M15 10h.01" />
      <path d={mouth} />
    </svg>
  )
}
