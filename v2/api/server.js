// v2-api — ДОПОЛНИТЕЛЬНЫЙ бэкенд Focus Board v2 на :3002.
// Та же база, что у v1 (WAL, busy_timeout — безопасная параллельная работа).
// Правила безопасности:
//   • Существующие таблицы v1 НЕ изменяются (никаких ALTER).
//   • Всё новое живёт в таблицах с префиксом v2_.
//   • Чтение v1-данных (tasks, work_sessions) — только SELECT.
const express = require('express')
const cors = require('cors')
const path = require('path')
const Database = require('better-sqlite3')

const DB_PATH = process.env.DB_PATH
  || path.join(__dirname, '..', '..', 'backend', 'data', 'focus.db')

const db = new Database(DB_PATH)
db.pragma('journal_mode = WAL')
db.pragma('busy_timeout = 4000')

db.exec(`
  CREATE TABLE IF NOT EXISTS v2_day_missions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    task_id      INTEGER NOT NULL,
    slot         INTEGER NOT NULL DEFAULT 1,
    hours_budget REAL,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(date, task_id)
  );
  CREATE INDEX IF NOT EXISTS idx_v2_missions_date ON v2_day_missions(date);
`)

const app = express()
app.use(cors())
app.use(express.json())

// ── Миссии дня («3 главных») ──────────────────────────────────────────────────

// GET /api2/missions?date=YYYY-MM-DD — миссии с данными задач и временем за этот день
app.get('/api2/missions', (req, res) => {
  const date = String(req.query.date || '').slice(0, 10)
  if (!date) return res.status(400).json({ error: 'date required' })
  const rows = db.prepare(`
    SELECT m.id, m.date, m.task_id, m.slot, m.hours_budget,
           t.title, t.direction_id, t.priority, t.done_at, t.notes, t.duration_plan
    FROM v2_day_missions m
    JOIN tasks t ON t.id = m.task_id
    WHERE m.date = ? AND t.deleted_at IS NULL
    ORDER BY m.slot ASC
  `).all(date)
  const timeStmt = db.prepare(`
    SELECT COALESCE(SUM(duration_actual), 0) AS s
    FROM work_sessions
    WHERE task_id = ? AND date(started_at, 'localtime') = ?
  `)
  res.json(rows.map(r => ({ ...r, seconds_today: timeStmt.get(r.task_id, date).s })))
})

// POST /api2/missions { date, missions: [{ task_id, hours_budget }] } — заменить набор дня
app.post('/api2/missions', (req, res) => {
  const { date, missions } = req.body || {}
  if (!date || !Array.isArray(missions)) return res.status(400).json({ error: 'date and missions[] required' })
  if (missions.length > 3) return res.status(400).json({ error: 'max 3 missions' })
  const tx = db.transaction(() => {
    db.prepare('DELETE FROM v2_day_missions WHERE date = ?').run(date)
    const ins = db.prepare('INSERT INTO v2_day_missions (date, task_id, slot, hours_budget) VALUES (?, ?, ?, ?)')
    missions.forEach((m, i) => ins.run(date, m.task_id, i + 1, m.hours_budget ?? null))
  })
  tx()
  res.json({ ok: true })
})

// PATCH /api2/missions/:id { hours_budget }
app.patch('/api2/missions/:id', (req, res) => {
  const { hours_budget } = req.body || {}
  db.prepare('UPDATE v2_day_missions SET hours_budget = ? WHERE id = ?').run(hours_budget ?? null, Number(req.params.id))
  res.json({ ok: true })
})

// DELETE /api2/missions/:id
app.delete('/api2/missions/:id', (req, res) => {
  db.prepare('DELETE FROM v2_day_missions WHERE id = ?').run(Number(req.params.id))
  res.json({ ok: true })
})

// ── Живая статистика ──────────────────────────────────────────────────────────

// GET /api2/heatmap?days=90 — матрица день-недели × час (сек фокуса)
app.get('/api2/heatmap', (req, res) => {
  const days = Math.min(365, Number(req.query.days) || 90)
  const rows = db.prepare(`
    SELECT CAST(strftime('%w', started_at, 'localtime') AS INTEGER) AS weekday,
           CAST(strftime('%H', started_at, 'localtime') AS INTEGER) AS hour,
           SUM(duration_actual) AS seconds,
           COUNT(*) AS sessions
    FROM work_sessions
    WHERE duration_actual > 0
      AND started_at >= datetime('now', ?)
    GROUP BY weekday, hour
  `).all(`-${days} days`)
  res.json({ days, rows })
})

// GET /api2/flow — инсайты «когда я в потоке»
app.get('/api2/flow', (_req, res) => {
  const bestHours = db.prepare(`
    SELECT CAST(strftime('%H', started_at, 'localtime') AS INTEGER) AS hour,
           SUM(duration_actual) AS seconds
    FROM work_sessions
    WHERE duration_actual > 0 AND started_at >= datetime('now', '-90 days')
    GROUP BY hour ORDER BY seconds DESC LIMIT 3
  `).all()
  const bestWeekday = db.prepare(`
    SELECT CAST(strftime('%w', started_at, 'localtime') AS INTEGER) AS weekday,
           SUM(duration_actual) AS seconds
    FROM work_sessions
    WHERE duration_actual > 0 AND started_at >= datetime('now', '-90 days')
    GROUP BY weekday ORDER BY seconds DESC LIMIT 1
  `).get() || null
  const agg = db.prepare(`
    SELECT COUNT(*) AS sessions,
           COALESCE(AVG(duration_actual), 0) AS avg_seconds,
           COALESCE(MAX(duration_actual), 0) AS longest_seconds,
           COALESCE(SUM(duration_actual), 0) AS total_seconds
    FROM work_sessions
    WHERE duration_actual > 0 AND started_at >= datetime('now', '-90 days')
  `).get()
  // Медиана длины сессии
  const median = db.prepare(`
    SELECT duration_actual AS m FROM work_sessions
    WHERE duration_actual > 0 AND started_at >= datetime('now', '-90 days')
    ORDER BY duration_actual
    LIMIT 1 OFFSET (
      SELECT COUNT(*) / 2 FROM work_sessions
      WHERE duration_actual > 0 AND started_at >= datetime('now', '-90 days')
    )
  `).get() || { m: 0 }
  res.json({ best_hours: bestHours, best_weekday: bestWeekday, ...agg, median_seconds: median.m })
})

// GET /api2/today-sessions?date=YYYY-MM-DD — сессии дня для таймлайна
app.get('/api2/today-sessions', (req, res) => {
  const date = String(req.query.date || '').slice(0, 10)
  if (!date) return res.status(400).json({ error: 'date required' })
  const rows = db.prepare(`
    SELECT w.id, w.started_at, w.ended_at, w.duration_actual, w.note,
           t.id AS task_id, t.title, t.direction_id
    FROM work_sessions w
    JOIN tasks t ON t.id = w.task_id
    WHERE date(w.started_at, 'localtime') = ?
    ORDER BY w.started_at ASC
  `).all(date)
  res.json(rows)
})

// GET /api2/direction-balance?days=30 — сек по направлениям (для орбит)
app.get('/api2/direction-balance', (req, res) => {
  const days = Math.min(365, Number(req.query.days) || 30)
  const rows = db.prepare(`
    SELECT t.direction_id, COALESCE(SUM(w.duration_actual), 0) AS seconds, COUNT(w.id) AS sessions
    FROM work_sessions w
    JOIN tasks t ON t.id = w.task_id
    WHERE w.duration_actual > 0 AND w.started_at >= datetime('now', ?)
    GROUP BY t.direction_id
  `).all(`-${days} days`)
  res.json({ days, rows })
})

const PORT = process.env.V2_API_PORT || 3002
app.listen(PORT, '127.0.0.1', () => {
  console.log(`Focus Board v2-api → http://127.0.0.1:${PORT} (db: ${DB_PATH})`)
})
