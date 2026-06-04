const ROWS = 5
const COLS = 9

// Soft blue→violet palette, hue drifts per row for depth
function scaleGradient(row: number) {
  const h1 = 222 + row * 6
  const h2 = 258 + row * 6
  return `linear-gradient(150deg, hsl(${h1} 45% 55%), hsl(${h2} 45% 42%))`
}

// Decorative "fish-scale" shimmer: rows of overlapping scales swaying in a wave
export default function GradientScales() {
  return (
    <div className="flex flex-col items-center py-2 overflow-hidden pointer-events-none select-none" aria-hidden>
      {Array.from({ length: ROWS }).map((_, row) => (
        <div
          key={row}
          className="flex"
          style={{ marginTop: row === 0 ? 0 : -12, marginLeft: row % 2 ? 18 : 0 }}
        >
          {Array.from({ length: COLS }).map((_, col) => (
            <div
              key={col}
              style={{
                width: 24,
                height: 24,
                margin: '0 1px',
                borderRadius: '0 0 50% 50% / 0 0 100% 100%',
                background: scaleGradient(row),
                animation: 'scaleSway 3.2s ease-in-out infinite',
                animationDelay: `${(col * 0.14 + row * 0.22).toFixed(2)}s`,
                boxShadow: 'inset 0 -2px 4px rgba(255,255,255,0.12)',
              }}
            />
          ))}
        </div>
      ))}
    </div>
  )
}
