const express = require('express')
const cors = require('cors')
const { db, initSchema, cleanupTrash } = require('./db')

// ─── Bootstrap ────────────────────────────────────────────────────────────────

initSchema()
cleanupTrash()

const app = express()
const PORT = process.env.PORT || 3001

app.use(cors({ origin: 'http://localhost:5173' }))
app.use(express.json())

// ─── Utility ──────────────────────────────────────────────────────────────────

function nowIso() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19)
}

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

/** Move the current 'now' task (if any, excluding excludeId) to top of 'next'. */
function evictNowTask(excludeId = null) {
  let q = `SELECT id FROM tasks WHERE slot = 'now' AND deleted_at IS NULL`
  if (excludeId != null) q += ` AND id != ${Number(excludeId)}`
  const current = db.prepare(q).get()
  if (current) {
    db.prepare(`UPDATE tasks SET slot_order = slot_order + 1 WHERE slot = 'next' AND deleted_at IS NULL`).run()
    db.prepare(`UPDATE tasks SET slot = 'next', slot_order = 0, updated_at = ? WHERE id = ?`)
      .run(nowIso(), current.id)
  }
}

// ─── Directions ───────────────────────────────────────────────────────────────

// GET /api/directions — all non-archived, sorted by order_index
app.get('/api/directions', (_req, res) => {
  try {
    const rows = db.prepare(`SELECT * FROM directions WHERE archived = 0 ORDER BY order_index ASC, id ASC`).all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/directions/all — include archived
app.get('/api/directions/all', (_req, res) => {
  try {
    const rows = db.prepare(`SELECT * FROM directions ORDER BY order_index ASC, id ASC`).all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/directions
app.post('/api/directions', (req, res) => {
  try {
    const { name } = req.body
    if (!name?.trim()) return res.status(400).json({ error: 'name is required' })
    const maxOrder = db.prepare(`SELECT COALESCE(MAX(order_index), -1) AS m FROM directions`).get().m
    const result = db.prepare(`INSERT INTO directions (name, order_index) VALUES (?, ?)`).run(name.trim(), maxOrder + 1)
    const row = db.prepare(`SELECT * FROM directions WHERE id = ?`).get(result.lastInsertRowid)
    res.status(201).json(row)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/directions/:id
app.patch('/api/directions/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const existing = db.prepare(`SELECT * FROM directions WHERE id = ?`).get(id)
    if (!existing) return res.status(404).json({ error: 'Not found' })

    const { name, order_index, archived } = req.body
    const fields = []
    const vals = []
    if (name !== undefined) { fields.push('name = ?'); vals.push(name) }
    if (order_index !== undefined) { fields.push('order_index = ?'); vals.push(order_index) }
    if (archived !== undefined) { fields.push('archived = ?'); vals.push(archived ? 1 : 0) }
    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })

    vals.push(id)
    db.prepare(`UPDATE directions SET ${fields.join(', ')} WHERE id = ?`).run(...vals)
    res.json(db.prepare(`SELECT * FROM directions WHERE id = ?`).get(id))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// DELETE /api/directions/:id — archive
app.delete('/api/directions/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const existing = db.prepare(`SELECT * FROM directions WHERE id = ?`).get(id)
    if (!existing) return res.status(404).json({ error: 'Not found' })
    db.prepare(`UPDATE directions SET archived = 1 WHERE id = ?`).run(id)
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Tasks ────────────────────────────────────────────────────────────────────

const TASK_WITH_DIR = `
  SELECT t.*, d.name AS direction_name
  FROM tasks t
  LEFT JOIN directions d ON d.id = t.direction_id
`

// GET /api/tasks — active tasks
app.get('/api/tasks', (_req, res) => {
  try {
    const rows = db
      .prepare(`${TASK_WITH_DIR} WHERE t.deleted_at IS NULL ORDER BY t.slot_order ASC, t.id ASC`)
      .all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/tasks/trash
app.get('/api/tasks/trash', (_req, res) => {
  try {
    const rows = db
      .prepare(`${TASK_WITH_DIR} WHERE t.deleted_at IS NOT NULL ORDER BY t.deleted_at DESC`)
      .all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/tasks/done — optional ?direction_id=&search=
app.get('/api/tasks/done', (req, res) => {
  try {
    const { direction_id, search } = req.query
    const conditions = [`t.deleted_at IS NULL`, `t.status = 'done'`]
    const params = []
    if (direction_id) { conditions.push(`t.direction_id = ?`); params.push(Number(direction_id)) }
    if (search) { conditions.push(`t.title LIKE ?`); params.push(`%${search}%`) }
    const rows = db
      .prepare(`${TASK_WITH_DIR} WHERE ${conditions.join(' AND ')} ORDER BY t.done_at DESC`)
      .all(...params)
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/take-now
app.post('/api/tasks/take-now', (req, res) => {
  try {
    const { task_id } = req.body
    if (!task_id) return res.status(400).json({ error: 'task_id is required' })
    const task = db.prepare(`SELECT * FROM tasks WHERE id = ? AND deleted_at IS NULL`).get(Number(task_id))
    if (!task) return res.status(404).json({ error: 'Task not found' })
    evictNowTask(task_id)
    db.prepare(`UPDATE tasks SET slot = 'now', slot_order = 0, updated_at = ? WHERE id = ?`)
      .run(nowIso(), Number(task_id))
    res.json(db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(Number(task_id)))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/reorder — {slot, ordered_ids}
app.post('/api/tasks/reorder', (req, res) => {
  try {
    const { slot, ordered_ids } = req.body
    if (!slot || !Array.isArray(ordered_ids)) return res.status(400).json({ error: 'slot and ordered_ids required' })
    const update = db.prepare(`UPDATE tasks SET slot_order = ?, updated_at = ? WHERE id = ?`)
    db.transaction(() => {
      ordered_ids.forEach((id, idx) => update.run(idx, nowIso(), Number(id)))
    })()
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/reset-order — {slot}
app.post('/api/tasks/reset-order', (req, res) => {
  try {
    const { slot } = req.body
    if (!slot) return res.status(400).json({ error: 'slot is required' })
    db.prepare(`UPDATE tasks SET slot_order = 0, updated_at = ? WHERE slot = ? AND deleted_at IS NULL`)
      .run(nowIso(), slot)
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/cleanup-trash — physically delete old trash
app.post('/api/tasks/cleanup-trash', (_req, res) => {
  try {
    const result = db
      .prepare(`DELETE FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-30 days')`)
      .run()
    res.json({ deleted: result.changes })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks — create task
app.post('/api/tasks', (req, res) => {
  try {
    const { title, direction_id, priority, slot, deadline, duration_plan, notes } = req.body
    if (!title?.trim()) return res.status(400).json({ error: 'title is required' })
    if (slot === 'now') evictNowTask()
    const result = db.prepare(`
      INSERT INTO tasks (title, direction_id, priority, slot, deadline, duration_plan, notes)
      VALUES (?, ?, ?, ?, ?, ?, ?)
    `).run(
      title.trim(),
      direction_id ?? null,
      priority ?? 'medium',
      slot ?? 'later',
      deadline ?? null,
      duration_plan ?? null,
      notes ?? null,
    )
    res.status(201).json(db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(result.lastInsertRowid))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/tasks/:id
app.patch('/api/tasks/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const existing = db.prepare(`SELECT * FROM tasks WHERE id = ?`).get(id)
    if (!existing) return res.status(404).json({ error: 'Not found' })

    const allowed = ['title', 'direction_id', 'priority', 'status', 'slot', 'slot_order',
                     'deadline', 'duration_plan', 'duration_fact', 'notes']
    const fields = []
    const vals = []

    for (const key of allowed) {
      if (key in req.body) {
        fields.push(`${key} = ?`)
        vals.push(req.body[key])
      }
    }

    // Enforce single 'now' slot
    if (req.body.slot === 'now' && existing.slot !== 'now') {
      evictNowTask(id)
    }

    // done_at management
    if (req.body.status === 'done' && existing.status !== 'done') {
      fields.push('done_at = ?'); vals.push(nowIso())
    } else if (req.body.status !== undefined && req.body.status !== 'done' && existing.status === 'done') {
      fields.push('done_at = ?'); vals.push(null)
    }

    // Always bump updated_at
    fields.push('updated_at = ?'); vals.push(nowIso())

    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })

    vals.push(id)
    db.prepare(`UPDATE tasks SET ${fields.join(', ')} WHERE id = ?`).run(...vals)
    res.json(db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(id))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// DELETE /api/tasks/:id — soft delete
app.delete('/api/tasks/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const existing = db.prepare(`SELECT * FROM tasks WHERE id = ?`).get(id)
    if (!existing) return res.status(404).json({ error: 'Not found' })
    db.prepare(`UPDATE tasks SET deleted_at = ?, updated_at = ? WHERE id = ?`).run(nowIso(), nowIso(), id)
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/:id/restore
app.post('/api/tasks/:id/restore', (req, res) => {
  try {
    const id = Number(req.params.id)
    const task = db.prepare(`SELECT * FROM tasks WHERE id = ?`).get(id)
    if (!task) return res.status(404).json({ error: 'Not found' })
    db.prepare(`UPDATE tasks SET deleted_at = NULL, updated_at = ? WHERE id = ?`).run(nowIso(), id)
    res.json(db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(id))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Work Sessions ────────────────────────────────────────────────────────────

// POST /api/sessions — start session
app.post('/api/sessions', (req, res) => {
  try {
    const { task_id, started_at } = req.body
    if (!task_id) return res.status(400).json({ error: 'task_id is required' })
    const result = db.prepare(`INSERT INTO work_sessions (task_id, started_at) VALUES (?, ?)`)
      .run(Number(task_id), started_at ?? nowIso())
    res.status(201).json(db.prepare(`SELECT * FROM work_sessions WHERE id = ?`).get(result.lastInsertRowid))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/sessions/:id — end session
app.patch('/api/sessions/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const session = db.prepare(`SELECT * FROM work_sessions WHERE id = ?`).get(id)
    if (!session) return res.status(404).json({ error: 'Not found' })

    const { ended_at, duration_actual } = req.body
    const fields = []
    const vals = []
    if (ended_at !== undefined) { fields.push('ended_at = ?'); vals.push(ended_at) }
    if (duration_actual !== undefined) { fields.push('duration_actual = ?'); vals.push(duration_actual) }
    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })

    vals.push(id)
    db.prepare(`UPDATE work_sessions SET ${fields.join(', ')} WHERE id = ?`).run(...vals)

    // Accumulate duration_fact on the task
    if (duration_actual != null && session.task_id) {
      db.prepare(`UPDATE tasks SET duration_fact = COALESCE(duration_fact, 0) + ?, updated_at = ? WHERE id = ?`)
        .run(Number(duration_actual), nowIso(), session.task_id)
    }

    res.json(db.prepare(`SELECT * FROM work_sessions WHERE id = ?`).get(id))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/sessions/today/:task_id — sum of duration_actual today
app.get('/api/sessions/today/:task_id', (req, res) => {
  try {
    const task_id = Number(req.params.task_id)
    const row = db.prepare(`
      SELECT COALESCE(SUM(duration_actual), 0) AS total
      FROM work_sessions
      WHERE task_id = ? AND date(started_at) = date('now')
    `).get(task_id)
    res.json({ total: row.total })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/sessions/stats?period=week|month|all
app.get('/api/sessions/stats', (req, res) => {
  try {
    const { period } = req.query
    let dateFilter = ''
    if (period === 'week') dateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`
    else if (period === 'month') dateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`

    const rows = db.prepare(`
      SELECT
        t.direction_id,
        d.name AS direction_name,
        date(ws.started_at) AS day,
        SUM(ws.duration_actual) AS total_seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.duration_actual IS NOT NULL ${dateFilter}
      GROUP BY t.direction_id, date(ws.started_at)
      ORDER BY day ASC
    `).all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Journal ──────────────────────────────────────────────────────────────────

// GET /api/journal — all entries grouped by day
app.get('/api/journal', (_req, res) => {
  try {
    const rows = db.prepare(`SELECT * FROM journal_entries ORDER BY created_at DESC`).all()
    const grouped = {}
    for (const entry of rows) {
      const day = entry.created_at.slice(0, 10)
      if (!grouped[day]) grouped[day] = []
      grouped[day].push(entry)
    }
    res.json(grouped)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/journal/today-checkin
app.get('/api/journal/today-checkin', (_req, res) => {
  try {
    const row = db.prepare(`
      SELECT id FROM journal_entries
      WHERE type = 'checkin' AND date(created_at) = date('now')
      LIMIT 1
    `).get()
    res.json({ exists: !!row })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/journal
app.post('/api/journal', (req, res) => {
  try {
    const { type, mood, goal, content } = req.body
    if (!type) return res.status(400).json({ error: 'type is required' })
    const result = db.prepare(`INSERT INTO journal_entries (type, mood, goal, content) VALUES (?, ?, ?, ?)`)
      .run(type, mood ?? null, goal ?? null, content ?? null)
    res.status(201).json(db.prepare(`SELECT * FROM journal_entries WHERE id = ?`).get(result.lastInsertRowid))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Settings ─────────────────────────────────────────────────────────────────

// GET /api/settings
app.get('/api/settings', (_req, res) => {
  try {
    const rows = db.prepare(`SELECT key, value FROM settings`).all()
    const obj = {}
    for (const r of rows) obj[r.key] = r.value
    res.json(obj)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/settings — upsert {key, value}
app.patch('/api/settings', (req, res) => {
  try {
    const { key, value } = req.body
    if (!key) return res.status(400).json({ error: 'key is required' })
    db.prepare(`
      INSERT INTO settings (key, value) VALUES (?, ?)
      ON CONFLICT(key) DO UPDATE SET value = excluded.value
    `).run(key, value ?? null)
    res.json({ key, value })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Recommendation ───────────────────────────────────────────────────────────

// GET /api/recommendation?skip_id=N
app.get('/api/recommendation', (req, res) => {
  try {
    const skipId = req.query.skip_id ? Number(req.query.skip_id) : null
    const today = todayStr()
    const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10)
    const skipClause = skipId != null ? ` AND id != ${skipId}` : ''

    const base = `
      FROM tasks
      WHERE deleted_at IS NULL
        AND slot != 'now'
        AND status NOT IN ('done', 'frozen')
    `

    // 1. From slot 'next'
    let task = db.prepare(`
      SELECT * ${base} ${skipClause} AND slot = 'next'
      ORDER BY slot_order ASC,
               CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END ASC
      LIMIT 1
    `).get()
    if (task) return res.json({ task, reason: 'следующая задача' })

    // 2. Deadline today
    task = db.prepare(`SELECT * ${base} ${skipClause} AND deadline = ? ORDER BY slot_order ASC LIMIT 1`).get(today)
    if (task) return res.json({ task, reason: 'дедлайн сегодня' })

    // 3. Deadline tomorrow
    task = db.prepare(`SELECT * ${base} ${skipClause} AND deadline = ? ORDER BY slot_order ASC LIMIT 1`).get(tomorrow)
    if (task) return res.json({ task, reason: 'дедлайн завтра' })

    // 4. High priority
    task = db.prepare(`SELECT * ${base} ${skipClause} AND priority = 'high' ORDER BY slot_order ASC LIMIT 1`).get()
    if (task) return res.json({ task, reason: 'самая приоритетная' })

    // 5. Longest without update
    task = db.prepare(`SELECT * ${base} ${skipClause} ORDER BY updated_at ASC LIMIT 1`).get()
    if (task) return res.json({ task, reason: 'давно не обновлялась' })

    res.json({ task: null, reason: null })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Stats ────────────────────────────────────────────────────────────────────

// GET /api/stats?period=week|month|all
app.get('/api/stats', (req, res) => {
  try {
    const { period } = req.query
    let taskDateFilter = ''
    let wsDateFilter = ''
    let journalFilter = ''

    if (period === 'week') {
      taskDateFilter = `AND date(t.done_at) >= date('now', '-7 days')`
      wsDateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`
      journalFilter = `AND date(created_at) >= date('now', '-7 days')`
    } else if (period === 'month') {
      taskDateFilter = `AND date(t.done_at) >= date('now', '-30 days')`
      wsDateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`
      journalFilter = `AND date(created_at) >= date('now', '-30 days')`
    }

    // Tasks done by direction
    const tasksDone = db.prepare(`
      SELECT t.direction_id, d.name AS direction_name, COUNT(*) AS count
      FROM tasks t
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE t.status = 'done' AND t.deleted_at IS NULL ${taskDateFilter}
      GROUP BY t.direction_id
    `).all()

    // Time worked by direction and day
    const timeWorked = db.prepare(`
      SELECT
        t.direction_id,
        d.name AS direction_name,
        date(ws.started_at) AS day,
        SUM(ws.duration_actual) AS total_seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.duration_actual IS NOT NULL ${wsDateFilter}
      GROUP BY t.direction_id, date(ws.started_at)
      ORDER BY day ASC
    `).all()

    // Mood by day
    const moodByDay = db.prepare(`
      SELECT date(created_at) AS day, AVG(mood) AS avg_mood
      FROM journal_entries
      WHERE type = 'checkin' AND mood IS NOT NULL ${journalFilter}
      GROUP BY date(created_at)
      ORDER BY day ASC
    `).all()

    // Journal stats
    const totalEntries = db.prepare(`SELECT COUNT(*) AS c FROM journal_entries WHERE 1=1 ${journalFilter}`).get().c
    const checkinDays = db.prepare(`
      SELECT COUNT(DISTINCT date(created_at)) AS c
      FROM journal_entries WHERE type = 'checkin' ${journalFilter}
    `).get().c

    // Top words from journal content
    const contentRows = db.prepare(`
      SELECT content FROM journal_entries
      WHERE content IS NOT NULL AND content != '' ${journalFilter}
    `).all()

    const stopWords = new Set([
      'и','в','на','с','по','к','у','о','за','из','от','то','не','но','а','да','или',
      'the','a','an','is','are','was','to','of','in','it','for','that','this',
    ])
    const wordCount = {}
    for (const { content } of contentRows) {
      const words = content.toLowerCase().match(/[а-яёa-z]{3,}/gi) || []
      for (const w of words) {
        if (!stopWords.has(w)) wordCount[w] = (wordCount[w] || 0) + 1
      }
    }
    const topWords = Object.entries(wordCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([word, count]) => ({ word, count }))

    res.json({
      tasks_done: tasksDone,
      time_worked: timeWorked,
      mood_by_day: moodByDay,
      journal_stats: {
        total_entries: totalEntries,
        checkin_days: checkinDays,
        top_words: topWords,
      },
    })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── AI ───────────────────────────────────────────────────────────────────────

function getOpenAiKey() {
  const row = db.prepare(`SELECT value FROM settings WHERE key = 'openai_api_key'`).get()
  return row?.value ?? null
}

// POST /api/settings/test-key — validate stored OpenAI key
app.post('/api/settings/test-key', async (_req, res) => {
  const key = getOpenAiKey()
  if (!key) return res.json({ valid: false, error: 'No key saved' })
  try {
    const r = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] }),
    })
    res.json({ valid: r.ok })
  } catch (err) {
    res.json({ valid: false, error: err.message })
  }
})

// POST /api/ai/analyze — proxy journal text to OpenAI
app.post('/api/ai/analyze', async (req, res) => {
  const key = getOpenAiKey()
  if (!key) return res.status(400).json({ error: 'OpenAI API key not configured' })

  const { text } = req.body
  if (!text) return res.status(400).json({ error: 'text is required' })

  try {
    const r = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        max_tokens: 800,
        messages: [
          {
            role: 'user',
            content: `Вот мои записи в дневнике за последнее время:\n\n${text}\n\nПроанализируй: динамику настроения, паттерны, дай краткое резюме недели (3-5 предложений). Отвечай по-русски.`,
          },
        ],
      }),
    })
    if (!r.ok) {
      const errBody = await r.json().catch(() => ({}))
      return res.status(r.status).json({ error: errBody?.error?.message ?? 'OpenAI request failed' })
    }
    const data = await r.json()
    res.json({ result: data.choices?.[0]?.message?.content ?? '' })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// ─── Start ────────────────────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`Focus Board backend → http://localhost:${PORT}`)
})
