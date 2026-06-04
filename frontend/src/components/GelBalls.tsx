import { useRef, useEffect } from 'react'

// Bright, mostly-flat gel balls that drift and get pushed around by the cursor.
const COLORS = [
  '#ff5c7c', // pink-red
  '#5cc8ff', // sky
  '#ffd24c', // yellow
  '#6cff8e', // green
  '#b07cff', // violet
  '#ff9f5c', // orange
  '#5cf0e0', // teal
]

interface Ball {
  x: number; y: number
  vx: number; vy: number
  r: number
  color: string
}

const HEIGHT = 260

export default function GelBalls() {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mouse = useRef<{ x: number; y: number; on: boolean }>({ x: 0, y: 0, on: false })

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    let w = 0
    const h = HEIGHT
    let balls: Ball[] = []
    let raf = 0

    const init = () => {
      w = canvas.clientWidth
      canvas.width = w * dpr
      canvas.height = h * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      // density scales with width
      const count = Math.max(10, Math.round((w * h) / 9000))
      balls = Array.from({ length: count }).map(() => {
        const r = 16 + Math.random() * 16
        return {
          x: r + Math.random() * (w - 2 * r),
          y: r + Math.random() * (h - 2 * r),
          vx: (Math.random() - 0.5) * 0.5,
          vy: (Math.random() - 0.5) * 0.5,
          r,
          color: COLORS[Math.floor(Math.random() * COLORS.length)],
        }
      })
    }

    const step = () => {
      ctx.clearRect(0, 0, w, h)
      const m = mouse.current

      for (let i = 0; i < balls.length; i++) {
        const b = balls[i]

        // cursor repulsion
        if (m.on) {
          const dx = b.x - m.x, dy = b.y - m.y
          const d2 = dx * dx + dy * dy
          const R = 110
          if (d2 < R * R && d2 > 0.01) {
            const d = Math.sqrt(d2)
            const force = (1 - d / R) * 1.6
            b.vx += (dx / d) * force
            b.vy += (dy / d) * force
          }
        }

        // gentle brownian drift so they never fully stop
        b.vx += (Math.random() - 0.5) * 0.05
        b.vy += (Math.random() - 0.5) * 0.05

        // friction
        b.vx *= 0.96
        b.vy *= 0.96

        b.x += b.vx
        b.y += b.vy

        // walls (soft bounce)
        if (b.x < b.r) { b.x = b.r; b.vx = Math.abs(b.vx) }
        if (b.x > w - b.r) { b.x = w - b.r; b.vx = -Math.abs(b.vx) }
        if (b.y < b.r) { b.y = b.r; b.vy = Math.abs(b.vy) }
        if (b.y > h - b.r) { b.y = h - b.r; b.vy = -Math.abs(b.vy) }
      }

      // soft ball-ball separation (jelly feel)
      for (let i = 0; i < balls.length; i++) {
        for (let j = i + 1; j < balls.length; j++) {
          const a = balls[i], c = balls[j]
          const dx = c.x - a.x, dy = c.y - a.y
          const dist = Math.hypot(dx, dy)
          const min = a.r + c.r
          if (dist > 0 && dist < min) {
            const overlap = (min - dist) / 2
            const ux = dx / dist, uy = dy / dist
            a.x -= ux * overlap; a.y -= uy * overlap
            c.x += ux * overlap; c.y += uy * overlap
          }
        }
      }

      // draw
      for (const b of balls) {
        const g = ctx.createRadialGradient(b.x - b.r * 0.3, b.y - b.r * 0.3, b.r * 0.1, b.x, b.y, b.r)
        g.addColorStop(0, '#ffffff')
        g.addColorStop(0.22, b.color)
        g.addColorStop(1, b.color)
        ctx.beginPath()
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2)
        ctx.fillStyle = g
        ctx.fill()
      }

      raf = requestAnimationFrame(step)
    }

    init()
    step()

    const ro = new ResizeObserver(() => init())
    ro.observe(canvas)

    return () => { cancelAnimationFrame(raf); ro.disconnect() }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{ width: '100%', height: HEIGHT, display: 'block', borderRadius: 8 }}
      onMouseMove={e => {
        const r = e.currentTarget.getBoundingClientRect()
        mouse.current = { x: e.clientX - r.left, y: e.clientY - r.top, on: true }
      }}
      onMouseLeave={() => { mouse.current.on = false }}
    />
  )
}
