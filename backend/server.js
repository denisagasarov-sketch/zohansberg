const express = require('express')
const cors = require('cors')
const fs = require('fs')
const path = require('path')
const os = require('os')
const { db, initSchema, cleanupTrash } = require('./db')

// ─── Bootstrap ────────────────────────────────────────────────────────────────

initSchema()
cleanupTrash()

// ─── Maintenance: ежедневный бэкап + WAL checkpoint ──────────────────────────
// База — единственная копия всех данных; бэкапим раз в день в BACKUP_DIR
// (по умолчанию ~/FocusBoardBackups), храним последние 30. WAL-checkpoint
// нужен потому, что процесс живёт вечно (KeepAlive) и сам его не делает —
// без этого focus.db-wal растёт неограниченно.
const BACKUP_DIR = process.env.BACKUP_DIR || path.join(os.homedir(), 'FocusBoardBackups')

async function dailyBackup() {
  try {
    fs.mkdirSync(BACKUP_DIR, { recursive: true })
    const stamp = new Date().toISOString().slice(0, 10)
    const dest = path.join(BACKUP_DIR, `focus-${stamp}.db`)
    if (!fs.existsSync(dest)) {
      await db.backup(dest) // онлайн-бэкап средствами SQLite — безопасен при работе
      console.log(`[backup] saved ${dest}`)
    }
    const files = fs.readdirSync(BACKUP_DIR).filter(f => /^focus-.*\.db$/.test(f)).sort()
    for (const f of files.slice(0, -30)) fs.unlinkSync(path.join(BACKUP_DIR, f))
  } catch (err) {
    console.error('[backup] failed:', err.message)
  }
}

function walCheckpoint() {
  try { db.pragma('wal_checkpoint(TRUNCATE)') } catch (err) { console.error('[wal]', err.message) }
}

dailyBackup()
walCheckpoint()
setInterval(dailyBackup, 6 * 60 * 60 * 1000)  // проверка 4 раза в день, файл на дату один
setInterval(walCheckpoint, 60 * 60 * 1000)

// ─── Recurring helpers ────────────────────────────────────────────────────────

function todayStr() { return new Date().toISOString().slice(0, 10) }

function nextRecurrenceDate(recurrence, fromDate) {
  const d = new Date(fromDate + 'T12:00:00')
  if (recurrence === 'daily') { d.setDate(d.getDate() + 1) }
  else if (recurrence === 'weekdays') {
    do { d.setDate(d.getDate() + 1) } while ([0, 6].includes(d.getDay()))
  } else if (recurrence === 'weekly') { d.setDate(d.getDate() + 7) }
  else if (recurrence === 'monthly') { d.setMonth(d.getMonth() + 1) }
  return d.toISOString().slice(0, 10)
}

function spawnRecurringNext(task) {
  const nextDate = nextRecurrenceDate(task.recurrence, todayStr())
  const existing = db.prepare(
    `SELECT id FROM tasks WHERE recurrence_last_date = ? AND title = ? AND deleted_at IS NULL AND done_at IS NULL`
  ).get(nextDate, task.title)
  if (existing) return
  db.prepare(`
    INSERT INTO tasks (title, direction_id, priority, notes, recurrence, recurrence_last_date, deadline, duration_plan, in_queue, someday, created_at, updated_at)
    VALUES (?,?,?,?,?,?,?,?,1,0,datetime('now'),datetime('now'))
  `).run(task.title, task.direction_id, task.priority, task.notes, task.recurrence, nextDate, nextDate, task.duration_plan)
  db.prepare(`UPDATE tasks SET recurrence_last_date = ? WHERE id = ?`).run(nextDate, task.id)
}

const app = express()
const PORT = process.env.PORT || 3001

// Allow the Vite dev server (Safari Web App) and the Electron app's bundled
// frontend (served on 4173). Requests with no Origin (same-origin, curl) pass too.
const ALLOWED_ORIGINS = new Set(['http://localhost:5173', 'http://localhost:4173'])
app.use(cors({ origin: (origin, cb) => cb(null, !origin || ALLOWED_ORIGINS.has(origin)) }))
app.use(express.json())

// ─── Client-side crash capture ─────────────────────────────────────────────────
// The Safari Web App window has no devtools we can read, and renderer-level JS
// crashes never reach the OS logs. This gives them a paper trail in client-errors.log.
app.post('/api/client-error', (req, res) => {
  try {
    const { kind, message, stack, url, userAgent, ts } = req.body || {}
    const line = JSON.stringify({ at: new Date().toISOString(), kind, message, stack, url, userAgent, ts }) + '\n'
    fs.appendFileSync(path.join(__dirname, 'client-errors.log'), line)
  } catch { /* never let logging break the response */ }
  res.json({ ok: true })
})

// ─── Utility ──────────────────────────────────────────────────────────────────

function nowIso() {
  return new Date().toISOString().replace('T', ' ').slice(0, 19)
}

/** Move the current 'now' task (if any, excluding excludeId) back to 'queue'. */
function evictNowTask(excludeId = null) {
  let q = `SELECT id FROM tasks WHERE slot = 'now' AND deleted_at IS NULL`
  if (excludeId != null) q += ` AND id != ${Number(excludeId)}`
  const current = db.prepare(q).get()
  if (current) {
    // Shift existing queue tasks to make room at position 0
    db.prepare(`UPDATE tasks SET slot_order = slot_order + 1, updated_at = ? WHERE in_queue = 1 AND deleted_at IS NULL`)
      .run(nowIso())
    // Place evicted task at the front of the queue
    db.prepare(`UPDATE tasks SET slot = 'queue', in_queue = 1, slot_order = 0, updated_at = ? WHERE id = ?`)
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

    const { name, order_index, archived, notes, weekly_goal_seconds } = req.body
    const fields = []
    const vals = []
    if (name !== undefined) { fields.push('name = ?'); vals.push(name) }
    if (order_index !== undefined) { fields.push('order_index = ?'); vals.push(order_index) }
    if (archived !== undefined) { fields.push('archived = ?'); vals.push(archived ? 1 : 0) }
    if (notes !== undefined) { fields.push('notes = ?'); vals.push(notes || null) }
    if (weekly_goal_seconds !== undefined) { fields.push('weekly_goal_seconds = ?'); vals.push(Number(weekly_goal_seconds) || 0) }
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
    const conditions = [`t.deleted_at IS NULL`, `t.done_at IS NOT NULL`]
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
    db.prepare(`UPDATE tasks SET slot = 'now', slot_order = 0, in_queue = 0, updated_at = ? WHERE id = ?`)
      .run(nowIso(), Number(task_id))
    res.json(db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(Number(task_id)))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// POST /api/tasks/evict-now — move current now-task to front of queue
app.post('/api/tasks/evict-now', (_req, res) => {
  try {
    evictNowTask()
    res.json({ ok: true })
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

// POST /api/tasks/reorder-direction — batch-update direction_order for tasks in a direction
app.post('/api/tasks/reorder-direction', (req, res) => {
  try {
    const { direction_id, ordered_ids } = req.body
    if (!Array.isArray(ordered_ids)) return res.status(400).json({ error: 'ordered_ids required' })
    const update = db.prepare(`UPDATE tasks SET direction_order = ?, updated_at = ? WHERE id = ?`)
    const now = nowIso()
    db.transaction(() => { ordered_ids.forEach((id, idx) => update.run(idx, now, id)) })()
    res.json({ ok: true })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})


// POST /api/tasks — create task
app.post('/api/tasks', (req, res) => {
  try {
    const { title, direction_id, priority, slot, deadline, duration_plan, notes, recurrence, in_queue } = req.body
    if (typeof title !== 'string' || !title.trim()) return res.status(400).json({ error: 'title is required' })
    const safeSlot = slot === 'now' ? 'now' : 'queue'
    if (safeSlot === 'now') evictNowTask()
    // Задача, созданная «в очередь», должна попадать в список «Следом»: очередь
    // фильтруется по in_queue=1. Явный in_queue уважаем, иначе queue-задача → в очередь.
    const inQueueVal = in_queue !== undefined ? (in_queue ? 1 : 0) : (safeSlot === 'queue' ? 1 : 0)
    const result = db.prepare(`
      INSERT INTO tasks (title, direction_id, priority, slot, deadline, duration_plan, notes, recurrence, in_queue)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(
      title.trim(),
      direction_id ?? null,
      priority ?? 'none',
      safeSlot,
      deadline ?? null,
      duration_plan ?? null,
      notes ?? null,
      recurrence ?? null,
      inQueueVal,
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

    const allowed = ['title', 'direction_id', 'priority', 'slot', 'slot_order',
                     'deadline', 'duration_plan', 'duration_fact', 'notes',
                     'direction_order', 'done_at', 'in_queue', 'someday',
                     'recurrence', 'recurrence_last_date']
    const fields = []
    const vals = []

    for (const key of allowed) {
      if (key in req.body) {
        // Normalize slot values
        if (key === 'slot') {
          vals.push(req.body[key] === 'now' ? 'now' : 'queue')
        } else if (key === 'in_queue' || key === 'someday') {
          vals.push(req.body[key] ? 1 : 0)
        } else {
          vals.push(req.body[key])
        }
        fields.push(`${key} = ?`)
      }
    }

    // Enforce single 'now' slot
    if (req.body.slot === 'now' && existing.slot !== 'now') {
      evictNowTask(id)
    }

    // When marking done (done_at set) and task is currently 'now', move to queue
    if ('done_at' in req.body && req.body.done_at && existing.slot === 'now' && !('slot' in req.body)) {
      fields.push('slot = ?'); vals.push('queue')
    }

    // Always bump updated_at
    fields.push('updated_at = ?'); vals.push(nowIso())

    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })

    vals.push(id)
    db.prepare(`UPDATE tasks SET ${fields.join(', ')} WHERE id = ?`).run(...vals)
    const updated = db.prepare(`${TASK_WITH_DIR} WHERE t.id = ?`).get(id)

    // If marking done and task has recurrence — spawn next instance
    if ('done_at' in req.body && req.body.done_at && existing.recurrence) {
      spawnRecurringNext(existing)
    }

    res.json(updated)
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

// ─── Subtasks (шаги / микро-подходы) ────────────────────────────────────────────

// GET /api/tasks/:id/subtasks
app.get('/api/tasks/:id/subtasks', (req, res) => {
  try {
    const rows = db.prepare(
      `SELECT * FROM subtasks WHERE task_id = ? ORDER BY order_index ASC, id ASC`
    ).all(Number(req.params.id))
    res.json(rows)
  } catch (err) { res.status(500).json({ error: err.message }) }
})

// POST /api/tasks/:id/subtasks — {title}
app.post('/api/tasks/:id/subtasks', (req, res) => {
  try {
    const task_id = Number(req.params.id)
    const task = db.prepare(`SELECT id FROM tasks WHERE id = ? AND deleted_at IS NULL`).get(task_id)
    if (!task) return res.status(404).json({ error: 'Task not found' })
    const { title } = req.body
    if (typeof title !== 'string' || !title.trim()) return res.status(400).json({ error: 'title is required' })
    const maxOrder = db.prepare(`SELECT COALESCE(MAX(order_index), -1) AS m FROM subtasks WHERE task_id = ?`).get(task_id).m
    const result = db.prepare(`INSERT INTO subtasks (task_id, title, order_index) VALUES (?, ?, ?)`)
      .run(task_id, title.trim(), maxOrder + 1)
    res.status(201).json(db.prepare(`SELECT * FROM subtasks WHERE id = ?`).get(result.lastInsertRowid))
  } catch (err) { res.status(500).json({ error: err.message }) }
})

// PATCH /api/subtasks/:id — {title?, done?}  (done:true/false переключает done_at)
app.patch('/api/subtasks/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    const existing = db.prepare(`SELECT * FROM subtasks WHERE id = ?`).get(id)
    if (!existing) return res.status(404).json({ error: 'Not found' })
    const fields = [], vals = []
    if (typeof req.body.title === 'string' && req.body.title.trim()) { fields.push('title = ?'); vals.push(req.body.title.trim()) }
    if ('done' in req.body) { fields.push('done_at = ?'); vals.push(req.body.done ? nowIso() : null) }
    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })
    vals.push(id)
    db.prepare(`UPDATE subtasks SET ${fields.join(', ')} WHERE id = ?`).run(...vals)
    res.json(db.prepare(`SELECT * FROM subtasks WHERE id = ?`).get(id))
  } catch (err) { res.status(500).json({ error: err.message }) }
})

// DELETE /api/subtasks/:id
app.delete('/api/subtasks/:id', (req, res) => {
  try {
    const id = Number(req.params.id)
    // Отвязываем сессии от шага (время работы по задаче сохраняется), затем удаляем шаг
    db.transaction(() => {
      db.prepare(`UPDATE work_sessions SET subtask_id = NULL WHERE subtask_id = ?`).run(id)
      db.prepare(`DELETE FROM subtasks WHERE id = ?`).run(id)
    })()
    res.json({ ok: true })
  } catch (err) { res.status(500).json({ error: err.message }) }
})

// POST /api/tasks/:id/subtasks/reorder — {ordered_ids}
app.post('/api/tasks/:id/subtasks/reorder', (req, res) => {
  try {
    const { ordered_ids } = req.body
    if (!Array.isArray(ordered_ids)) return res.status(400).json({ error: 'ordered_ids required' })
    const upd = db.prepare(`UPDATE subtasks SET order_index = ? WHERE id = ?`)
    db.transaction(() => ordered_ids.forEach((sid, i) => upd.run(i, Number(sid))))()
    res.json({ ok: true })
  } catch (err) { res.status(500).json({ error: err.message }) }
})

// ─── Work Sessions ────────────────────────────────────────────────────────────

// POST /api/sessions — start session
app.post('/api/sessions', (req, res) => {
  try {
    const { task_id, started_at, subtask_id } = req.body
    if (!task_id) return res.status(400).json({ error: 'task_id is required' })
    const result = db.prepare(`INSERT INTO work_sessions (task_id, started_at, subtask_id) VALUES (?, ?, ?)`)
      .run(Number(task_id), started_at ?? nowIso(), subtask_id != null ? Number(subtask_id) : null)
    res.status(201).json(db.prepare(`SELECT * FROM work_sessions WHERE id = ?`).get(result.lastInsertRowid))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/sessions/active — returns the most recent open session (no ended_at), or null
app.get('/api/sessions/active', (_req, res) => {
  try {
    const session = db.prepare(`
      SELECT * FROM work_sessions WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1
    `).get()
    res.json(session ?? null)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// PATCH /api/sessions/:id/heartbeat — auto-save elapsed time while timer is running
app.patch('/api/sessions/:id/heartbeat', (req, res) => {
  try {
    const id = Number(req.params.id)
    const session = db.prepare(`SELECT id FROM work_sessions WHERE id = ? AND ended_at IS NULL`).get(id)
    if (!session) return res.status(404).json({ error: 'Active session not found' })
    db.prepare(`UPDATE work_sessions SET elapsed_seconds = ? WHERE id = ?`)
      .run(Number(req.body.elapsed_seconds) || 0, id)
    res.json({ ok: true })
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

    const { ended_at, duration_actual, note } = req.body
    const fields = []
    const vals = []
    // Валидируем длительность: мусор (NaN/строка/отрицательное) раньше затирал
    // duration_fact задачи в NULL. Теперь такое отклоняем.
    let durNum = null
    if (duration_actual !== undefined) {
      durNum = Number(duration_actual)
      if (!Number.isFinite(durNum) || durNum < 0) {
        return res.status(400).json({ error: 'duration_actual must be a non-negative number' })
      }
      fields.push('duration_actual = ?'); vals.push(durNum)
    }
    if (ended_at !== undefined) { fields.push('ended_at = ?'); vals.push(ended_at) }
    if (note !== undefined) { fields.push('note = ?'); vals.push(note) }
    if (!fields.length) return res.status(400).json({ error: 'No fields to update' })

    vals.push(id)
    db.prepare(`UPDATE work_sessions SET ${fields.join(', ')} WHERE id = ?`).run(...vals)

    // Начисляем в duration_fact ТОЛЬКО при первом закрытии сессии (open → closed).
    // Иначе повторный PATCH (ретрай/двойной клик «стоп») задваивал учтённое время.
    if (durNum != null && session.task_id && session.ended_at == null) {
      db.prepare(`UPDATE tasks SET duration_fact = COALESCE(duration_fact, 0) + ?, updated_at = ? WHERE id = ?`)
        .run(durNum, nowIso(), session.task_id)
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

// POST /api/tasks/:id/sessions — manually add a session
app.post('/api/tasks/:id/sessions', (req, res) => {
  try {
    const task_id = Number(req.params.id)
    const task = db.prepare(`SELECT id FROM tasks WHERE id = ? AND deleted_at IS NULL`).get(task_id)
    if (!task) return res.status(404).json({ error: 'Task not found' })

    const { started_at, ended_at, duration_seconds, note } = req.body
    if (!started_at || !ended_at || !duration_seconds) {
      return res.status(400).json({ error: 'started_at, ended_at, duration_seconds are required' })
    }

    const dur = Number(duration_seconds)
    // Ручная сессия: раньше принимались отрицательное/перевёрнутое время и портили статистику
    if (!Number.isFinite(dur) || dur <= 0) {
      return res.status(400).json({ error: 'duration_seconds must be a positive number' })
    }
    if (String(ended_at) < String(started_at)) {
      return res.status(400).json({ error: 'ended_at must be after started_at' })
    }
    const result = db.prepare(
      `INSERT INTO work_sessions (task_id, started_at, ended_at, duration_actual, note) VALUES (?, ?, ?, ?, ?)`
    ).run(task_id, started_at, ended_at, dur, note ?? null)

    db.prepare(`UPDATE tasks SET duration_fact = COALESCE(duration_fact, 0) + ?, updated_at = ? WHERE id = ?`)
      .run(dur, nowIso(), task_id)

    res.status(201).json(db.prepare(`SELECT * FROM work_sessions WHERE id = ?`).get(result.lastInsertRowid))
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/sessions/task/:task_id — all sessions for a task
app.get('/api/sessions/task/:task_id', (req, res) => {
  try {
    const task_id = Number(req.params.task_id)
    const rows = db.prepare(`
      SELECT id, started_at, ended_at, duration_actual, note
      FROM work_sessions
      WHERE task_id = ?
      ORDER BY started_at DESC
    `).all(task_id)
    res.json(rows)
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

// GET /api/journal — all entries as flat array
app.get('/api/journal', (_req, res) => {
  try {
    const rows = db.prepare(`SELECT * FROM journal_entries ORDER BY created_at DESC`).all()
    res.json(rows)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/journal/today-checkin — вместе с содержимым, чтобы цель дня
// можно было показывать на главном экране весь день
app.get('/api/journal/today-checkin', (_req, res) => {
  try {
    const row = db.prepare(`
      SELECT id, mood, goal, content FROM journal_entries
      WHERE type = 'checkin' AND date(created_at) = date('now')
      ORDER BY id DESC LIMIT 1
    `).get()
    res.json({ exists: !!row, mood: row?.mood ?? null, goal: row?.goal ?? null, content: row?.content ?? null })
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


// ─── Stats ────────────────────────────────────────────────────────────────────

// GET /api/stats?period=week|month|all
app.get('/api/stats', (req, res) => {
  try {
    const { period } = req.query
    let taskDateFilter = ''
    let wsDateFilter = ''
    let journalFilter = ''

    if (period === 'week') {
      taskDateFilter = `AND date(done_at) >= date('now', '-7 days')`
      wsDateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`
      journalFilter = `AND date(created_at) >= date('now', '-7 days')`
    } else if (period === 'month') {
      taskDateFilter = `AND date(done_at) >= date('now', '-30 days')`
      wsDateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`
      journalFilter = `AND date(created_at) >= date('now', '-30 days')`
    }

    // Tasks done by direction
    const tasksDone = db.prepare(`
      SELECT t.direction_id, d.name AS direction_name, COUNT(*) AS count
      FROM tasks t
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE t.done_at IS NOT NULL AND t.deleted_at IS NULL ${taskDateFilter}
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

// POST /api/ai/suggest-title — 3 AI title suggestions via OpenAI
const AI_LOG = path.join(__dirname, 'ai-suggest.log')
function aiLog(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`
  process.stderr.write(line)
  try {
    // Ротация: при 1 МБ переносим в .old (одна прошлая копия), лог не растёт бесконечно
    if (fs.existsSync(AI_LOG) && fs.statSync(AI_LOG).size > 1_000_000) {
      fs.renameSync(AI_LOG, AI_LOG + '.old')
    }
    fs.appendFileSync(AI_LOG, line)
  } catch { /* логирование не должно ронять запрос */ }
}

app.post('/api/ai/suggest-title', async (req, res) => {
  const key = getOpenAiKey()
  if (!key) {
    aiLog('ERROR: no OpenAI key configured')
    return res.status(400).json({ error: 'OpenAI API key not configured' })
  }

  const { title, direction, deadline, notes, recentTasks } = req.body
  if (!title?.trim()) return res.status(400).json({ error: 'title is required' })

  // Use passed recentTasks if provided, otherwise fetch from DB
  const recent = Array.isArray(recentTasks) && recentTasks.length > 0
    ? recentTasks
    : db.prepare(`SELECT title FROM tasks WHERE done_at IS NOT NULL ORDER BY done_at DESC LIMIT 10`).all().map(t => t.title)

  const recentContext = recent.length ? recent.map(t => `- ${t}`).join('\n') : '(нет)'

  const prompt = `Ты помогаешь формулировать задачи конкретно и измеримо.

Контекст задачи:
- Название: ${title.trim()}
- Направление: ${direction || 'не указано'}
- Дедлайн: ${deadline || 'не указан'}
- Заметки: ${notes || 'нет'}
- Последние завершённые задачи пользователя: ${recentContext}

Правила хорошей формулировки:
- Начинается с глагола действия
- Содержит конкретный результат который можно проверить
- Максимум 10 слов
- НЕ просто синоним исходной фразы — предложи другой угол

Плохо: 'Разработать CRM для лидов' (то же самое другими словами)
Хорошо: 'Настроить Notion как CRM и завести первые 10 лидов'
Хорошо: 'Выбрать CRM-платформу и описать требования в 5 пунктах'
Хорошо: 'Создать шаблон карточки лида и протестировать на 3 контактах'

Верни JSON массив из 3 разных формулировок.
Только массив, без объяснений.`

  const requestBody = {
    model: 'gpt-4o-mini',
    max_tokens: 300,
    messages: [{ role: 'user', content: prompt }],
  }

  aiLog(`suggest-title: "${title.trim()}"`)

  try {
    const r = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody),
    })
    const rawText = await r.text()
    aiLog(`OpenAI status: ${r.status}`)
    if (!r.ok) aiLog(`OpenAI error body: ${rawText.slice(0, 500)}`)

    if (!r.ok) {
      let errMsg = rawText
      try { errMsg = JSON.parse(rawText)?.error?.message ?? rawText } catch {}
      return res.status(r.status).json({ error: errMsg })
    }
    const data = JSON.parse(rawText)
    const text = data.choices?.[0]?.message?.content ?? ''
    const match = text.match(/\[[\s\S]*?\]/)
    const suggestions = match ? JSON.parse(match[0]) : []
    res.json({ suggestions })
  } catch (err) {
    console.error('[suggest-title] unexpected error:', err)
    res.status(500).json({ error: err.message })
  }
})

app.post('/api/ai/parse-task', async (req, res) => {
  const key = getOpenAiKey()
  if (!key) return res.status(400).json({ error: 'OpenAI API key not configured' })

  const { text } = req.body
  if (!text?.trim()) return res.status(400).json({ error: 'text is required' })

  const directions = db.prepare(`SELECT id, name FROM directions WHERE archived = 0`).all()
  const dirList = directions.map(d => `${d.id}: ${d.name}`).join(', ')
  const today = new Date().toISOString().slice(0, 10)

  const prompt = `Разбери текст задачи и верни JSON.

Текст: "${text.trim()}"
Сегодня: ${today}
Доступные направления: ${dirList || 'нет'}

Верни ТОЛЬКО JSON объект без объяснений:
{
  "title": "чёткое название задачи (глагол + результат)",
  "direction_id": число или null,
  "deadline": "YYYY-MM-DD" или null,
  "duration_plan": число часов или null
}

Правила:
- title: начни с глагола, максимум 10 слов, конкретный результат
- direction_id: выбери подходящее направление из списка или null
- deadline: парси "завтра", "в пятницу", "через неделю" и т.д.
- duration_plan: только если явно упомянуто ("на час", "2 часа")`

  try {
    const r = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini', max_tokens: 150, messages: [{ role: 'user', content: prompt }] }),
    })
    if (!r.ok) return res.status(r.status).json({ error: 'OpenAI error' })
    const data = await r.json()
    const text2 = data.choices?.[0]?.message?.content ?? '{}'
    const match = text2.match(/\{[\s\S]*\}/)
    const parsed = match ? JSON.parse(match[0]) : {}
    res.json(parsed)
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/sessions/worklog?period=week|month|all
// Returns heatmap (day→seconds), top tasks, and formatted log text for GPT
app.get('/api/sessions/worklog', (req, res) => {
  try {
    const period = req.query.period || 'week'
    let dateFilter = ''
    let periodLabel = ''
    if (period === 'week') { dateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`; periodLabel = 'последнюю неделю' }
    else if (period === 'month') { dateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`; periodLabel = 'последний месяц' }
    else { periodLabel = 'всё время' }

    // Heatmap: seconds per day
    const heatmap = db.prepare(`
      SELECT date(ws.started_at) AS day, SUM(ws.duration_actual) AS seconds
      FROM work_sessions ws
      WHERE ws.duration_actual IS NOT NULL ${dateFilter}
      GROUP BY day ORDER BY day ASC
    `).all()

    // Top tasks by total time worked
    const topTasks = db.prepare(`
      SELECT t.id, t.title, COALESCE(d.name, 'Без направления') AS direction_name,
             SUM(ws.duration_actual) AS total_seconds,
             MIN(date(ws.started_at)) AS first_day
      FROM work_sessions ws
      JOIN tasks t ON ws.task_id = t.id
      LEFT JOIN directions d ON t.direction_id = d.id
      WHERE ws.duration_actual IS NOT NULL ${dateFilter}
      GROUP BY t.id ORDER BY total_seconds DESC LIMIT 10
    `).all()

    // Detailed session list for GPT prompt (last 100 sessions)
    const sessions = db.prepare(`
      SELECT ws.started_at, ws.duration_actual,
             t.title AS task_title,
             COALESCE(d.name, 'Без направления') AS direction_name
      FROM work_sessions ws
      JOIN tasks t ON ws.task_id = t.id
      LEFT JOIN directions d ON t.direction_id = d.id
      WHERE ws.duration_actual IS NOT NULL ${dateFilter}
      ORDER BY ws.started_at DESC LIMIT 100
    `).all()

    // Format log text for GPT
    const days = {}
    for (const s of sessions) {
      const day = s.started_at.slice(0, 10)
      if (!days[day]) days[day] = []
      const h = (s.duration_actual / 3600).toFixed(1)
      days[day].push(`  • ${s.task_title} [${s.direction_name}] — ${h}ч`)
    }
    const logLines = Object.entries(days)
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([day, lines]) => `${day}:\n${lines.join('\n')}`)
    const logText = `Вот мой рабочий журнал за ${periodLabel}:\n\n${logLines.join('\n\n')}`

    res.json({ heatmap, top_tasks: topTasks, log_text: logText, period_label: periodLabel })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/stats/dashboard?period=week|month|all
// New unified endpoint for the dashboard stats screen
app.get('/api/stats/dashboard', (req, res) => {
  try {
    const { period } = req.query
    let dateFilter = ''
    let taskDateFilter = ''
    if (period === 'week') {
      dateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`
      taskDateFilter = `AND date(done_at) >= date('now', '-7 days')`
    } else if (period === 'month') {
      dateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`
      taskDateFilter = `AND date(done_at) >= date('now', '-30 days')`
    }

    // Raw sessions for timeline (only completed sessions with end time)
    const sessions = db.prepare(`
      SELECT ws.id, ws.started_at, ws.ended_at, ws.duration_actual, ws.note,
             t.direction_id, t.title AS task_title,
             COALESCE(d.name, 'Без направления') AS direction_name
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.ended_at IS NOT NULL AND ws.duration_actual > 0 ${dateFilter}
      ORDER BY ws.started_at ASC
    `).all()

    // Time by direction (for donut chart)
    const timeByDirection = db.prepare(`
      SELECT t.direction_id,
             COALESCE(d.name, 'Без направления') AS direction_name,
             SUM(ws.duration_actual) AS total_seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.duration_actual IS NOT NULL AND ws.duration_actual > 0 ${dateFilter}
      GROUP BY t.direction_id
      ORDER BY total_seconds DESC
    `).all()

    // Time by day and direction (for stacked bar chart)
    const timeByDayDirection = db.prepare(`
      SELECT date(ws.started_at) AS day,
             t.direction_id,
             COALESCE(d.name, 'Без направления') AS direction_name,
             SUM(ws.duration_actual) AS total_seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.duration_actual IS NOT NULL AND ws.duration_actual > 0 ${dateFilter}
      GROUP BY date(ws.started_at), t.direction_id
      ORDER BY day ASC
    `).all()

    // Total time
    const totalSeconds = timeByDirection.reduce((s, r) => s + (r.total_seconds || 0), 0)

    // Tasks done count
    const tasksDoneCount = db.prepare(`
      SELECT COUNT(*) AS c FROM tasks
      WHERE done_at IS NOT NULL AND deleted_at IS NULL ${taskDateFilter}
    `).get().c

    // Top direction
    const topDirection = timeByDirection[0] ?? null

    // All non-archived directions (for consistent color assignment)
    const directions = db.prepare(`SELECT id, name FROM directions WHERE archived = 0 ORDER BY id ASC`).all()

    res.json({
      total_seconds: totalSeconds,
      tasks_done_count: tasksDoneCount,
      top_direction: topDirection,
      sessions,
      time_by_direction: timeByDirection,
      time_by_day_direction: timeByDayDirection,
      directions,
    })
  } catch (err) {
    res.status(500).json({ error: err.message })
  }
})

// GET /api/today-summary
app.get('/api/today-summary', (_req, res) => {
  try {
    const today = todayStr()
    const done_count = db.prepare(`SELECT COUNT(*) AS n FROM tasks WHERE date(done_at) = ? AND deleted_at IS NULL`).get(today).n
    const time_row = db.prepare(`SELECT COALESCE(SUM(duration_actual),0) AS s FROM work_sessions WHERE date(started_at) = ?`).get(today)

    // All sessions today
    const sessions_today = db.prepare(`
      SELECT id, task_id, started_at, ended_at, duration_actual, note
      FROM work_sessions
      WHERE date(started_at) = ? AND ended_at IS NOT NULL
      ORDER BY started_at ASC
    `).all(today)

    const sessionsByTask = {}
    for (const s of sessions_today) {
      if (!sessionsByTask[s.task_id]) sessionsByTask[s.task_id] = []
      sessionsByTask[s.task_id].push(s)
    }

    // Tasks completed today with time spent on them today
    const done_tasks_raw = db.prepare(`
      SELECT t.id, t.title, t.done_at,
             COALESCE(SUM(ws.duration_actual), 0) AS time_seconds
      FROM tasks t
      LEFT JOIN work_sessions ws ON ws.task_id = t.id AND date(ws.started_at) = ?
      WHERE date(t.done_at) = ? AND t.deleted_at IS NULL
      GROUP BY t.id
      ORDER BY t.done_at ASC
    `).all(today, today)

    const done_tasks = done_tasks_raw.map(t => ({ ...t, sessions: sessionsByTask[t.id] || [] }))

    // Tasks not completed but worked on today
    const worked_tasks_raw = db.prepare(`
      SELECT t.id, t.title, COALESCE(SUM(ws.duration_actual), 0) AS time_seconds
      FROM work_sessions ws
      JOIN tasks t ON t.id = ws.task_id
      WHERE date(ws.started_at) = ? AND t.done_at IS NULL AND t.deleted_at IS NULL
      GROUP BY t.id
      HAVING time_seconds > 0
      ORDER BY time_seconds DESC
    `).all(today)

    const worked_tasks = worked_tasks_raw.map(t => ({ ...t, sessions: sessionsByTask[t.id] || [] }))

    res.json({ done_count, time_seconds: time_row.s, done_tasks, worked_tasks })
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// GET /api/weekly-summary — last 7 days stats for weekly review
app.get('/api/weekly-summary', (_req, res) => {
  try {
    const done_count = db.prepare(
      `SELECT COUNT(*) AS n FROM tasks WHERE date(done_at) >= date('now','-6 days') AND deleted_at IS NULL`
    ).get().n

    const time_seconds = db.prepare(
      `SELECT COALESCE(SUM(duration_actual),0) AS s FROM work_sessions WHERE date(started_at) >= date('now','-6 days')`
    ).get().s

    const by_direction = db.prepare(`
      SELECT t.direction_id, COALESCE(d.name,'Без направления') AS direction_name,
             SUM(ws.duration_actual) AS seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE date(ws.started_at) >= date('now','-6 days') AND ws.duration_actual > 0
      GROUP BY t.direction_id ORDER BY seconds DESC
    `).all()

    const done_tasks = db.prepare(`
      SELECT t.title, COALESCE(d.name,'') AS direction
      FROM tasks t LEFT JOIN directions d ON d.id = t.direction_id
      WHERE date(t.done_at) >= date('now','-6 days') AND t.deleted_at IS NULL
      ORDER BY t.done_at ASC LIMIT 20
    `).all()

    res.json({ done_count, time_seconds, by_direction, done_tasks })
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// ─── Day Thread (нить дня) ──────────────────────────────────────────────────
// GET /api/day-thread?date=YYYY-MM-DD — единая хронологическая лента дня:
// утренняя цель, закрытые шаги, заметки сессий, мысли, завершённые задачи.
app.get('/api/day-thread', (req, res) => {
  try {
    const date = req.query.date || todayStr()

    const checkin = db.prepare(`
      SELECT mood, goal, content, created_at FROM journal_entries
      WHERE type = 'checkin' AND date(created_at) = ? ORDER BY id DESC LIMIT 1
    `).get(date)

    const events = []

    // Закрытые шаги (микро-победы)
    db.prepare(`
      SELECT s.title, s.done_at, t.title AS task_title
      FROM subtasks s JOIN tasks t ON t.id = s.task_id
      WHERE date(s.done_at) = ? ORDER BY s.done_at ASC
    `).all(date).forEach(r => events.push({
      at: r.done_at, kind: 'subtask_done', text: r.title, task: r.task_title,
    }))

    // Сессии с заметками
    db.prepare(`
      SELECT ws.started_at, ws.duration_actual, ws.note, t.title AS task_title
      FROM work_sessions ws JOIN tasks t ON t.id = ws.task_id
      WHERE date(ws.started_at) = ? AND ws.note IS NOT NULL AND ws.note != ''
      ORDER BY ws.started_at ASC
    `).all(date).forEach(r => events.push({
      at: r.started_at, kind: 'session_note', text: r.note, task: r.task_title, seconds: r.duration_actual,
    }))

    // Свободные мысли
    db.prepare(`
      SELECT content, created_at FROM journal_entries
      WHERE type = 'thought' AND date(created_at) = ? ORDER BY created_at ASC
    `).all(date).forEach(r => events.push({ at: r.created_at, kind: 'thought', text: r.content }))

    // Завершённые задачи
    db.prepare(`
      SELECT title, done_at FROM tasks
      WHERE date(done_at) = ? AND deleted_at IS NULL ORDER BY done_at ASC
    `).all(date).forEach(r => events.push({ at: r.done_at, kind: 'task_done', text: r.title }))

    events.sort((a, b) => String(a.at).localeCompare(String(b.at)))

    const totalSeconds = db.prepare(
      `SELECT COALESCE(SUM(duration_actual),0) AS s FROM work_sessions WHERE date(started_at) = ?`
    ).get(date).s
    const subtasksDone = db.prepare(`SELECT COUNT(*) AS n FROM subtasks WHERE date(done_at) = ?`).get(date).n
    const tasksDone = db.prepare(`SELECT COUNT(*) AS n FROM tasks WHERE date(done_at) = ? AND deleted_at IS NULL`).get(date).n

    res.json({ date, checkin: checkin ?? null, events, totals: { seconds: totalSeconds, subtasks_done: subtasksDone, tasks_done: tasksDone } })
  } catch (e) { res.status(500).json({ error: e.message }) }
})

// ─── Gamification (streak, кольца дня, тепловая карта) ────────────────────────
// GET /api/gamification — серия дней, показатели сегодня, heatmap за год.
app.get('/api/gamification', (_req, res) => {
  try {
    // Активные дни = были сессии, закрытые задачи/шаги или чек-ин
    const activeDays = new Set()
    const collect = (rows) => rows.forEach(r => r.d && activeDays.add(r.d))
    collect(db.prepare(`SELECT DISTINCT date(started_at) AS d FROM work_sessions WHERE duration_actual > 0`).all())
    collect(db.prepare(`SELECT DISTINCT date(done_at) AS d FROM tasks WHERE done_at IS NOT NULL`).all())
    collect(db.prepare(`SELECT DISTINCT date(done_at) AS d FROM subtasks WHERE done_at IS NOT NULL`).all())
    collect(db.prepare(`SELECT DISTINCT date(created_at) AS d FROM journal_entries WHERE type='checkin'`).all())

    // Текущая серия: считаем назад от сегодня (или вчера, если сегодня ещё пусто)
    const dstr = (dt) => dt.toISOString().slice(0, 10)
    let streak = 0
    const cur = new Date()
    if (!activeDays.has(dstr(cur))) cur.setDate(cur.getDate() - 1) // серия не рвётся, если сегодня ещё не начал
    while (activeDays.has(dstr(cur))) { streak++; cur.setDate(cur.getDate() - 1) }

    // Лучшая серия за всё время
    const sorted = [...activeDays].sort()
    let best = 0, run = 0, prev = null
    for (const d of sorted) {
      if (prev) {
        const diff = (new Date(d) - new Date(prev)) / 86400000
        run = diff === 1 ? run + 1 : 1
      } else run = 1
      best = Math.max(best, run); prev = d
    }

    // Сегодня: время в фокусе + закрытые шаги/задачи
    const today = todayStr()
    const todaySeconds = db.prepare(`SELECT COALESCE(SUM(duration_actual),0) AS s FROM work_sessions WHERE date(started_at)=?`).get(today).s
    const todaySubtasks = db.prepare(`SELECT COUNT(*) AS n FROM subtasks WHERE date(done_at)=?`).get(today).n
    const todayTasks = db.prepare(`SELECT COUNT(*) AS n FROM tasks WHERE date(done_at)=? AND deleted_at IS NULL`).get(today).n

    // Тепловая карта за последние 365 дней (день → секунды)
    const heatmap = db.prepare(`
      SELECT date(started_at) AS day, SUM(duration_actual) AS seconds
      FROM work_sessions
      WHERE duration_actual > 0 AND date(started_at) >= date('now','-365 days')
      GROUP BY day
    `).all()

    res.json({
      streak, best_streak: best, active_days_total: activeDays.size,
      today: { seconds: todaySeconds, subtasks_done: todaySubtasks, tasks_done: todayTasks },
      heatmap,
    })
  } catch (e) { res.status(500).json({ error: e.message }) }
})

// ─── Day Plan ────────────────────────────────────────────────────────────────

// GET /api/day-plan?date=YYYY-MM-DD
app.get('/api/day-plan', (req, res) => {
  try {
    const date = req.query.date || todayStr()
    const rows = db.prepare(`
      SELECT dp.id, dp.task_id, dp.order_index,
             t.title, t.priority, t.direction_id, t.done_at, t.deleted_at
      FROM day_plan dp
      JOIN tasks t ON t.id = dp.task_id
      WHERE dp.date = ? AND t.deleted_at IS NULL
      ORDER BY dp.order_index ASC
    `).all(date)
    res.json(rows)
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// POST /api/day-plan — replace plan for a date
app.post('/api/day-plan', (req, res) => {
  try {
    const { date, task_ids } = req.body
    if (!date || !Array.isArray(task_ids)) return res.status(400).json({ error: 'date and task_ids required' })
    // Транзакция: иначе сбой между DELETE и INSERT стирает план дня
    db.transaction(() => {
      db.prepare(`DELETE FROM day_plan WHERE date = ?`).run(date)
      const insert = db.prepare(`INSERT INTO day_plan (date, task_id, order_index) VALUES (?, ?, ?)`)
      task_ids.forEach((id, i) => insert.run(date, Number(id), i))
    })()
    res.json({ ok: true })
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// GET /api/stats/weekly-time — current week's time per direction
app.get('/api/stats/weekly-time', (_req, res) => {
  try {
    const rows = db.prepare(`
      SELECT t.direction_id, COALESCE(SUM(ws.duration_actual), 0) AS seconds
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      WHERE date(ws.started_at) >= date('now', '-6 days') AND ws.duration_actual > 0
      GROUP BY t.direction_id
    `).all()
    res.json(rows)
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// ─── Standup ──────────────────────────────────────────────────────────────────

// GET /api/standup — yesterday + today sessions grouped by task
app.get('/api/standup', (_req, res) => {
  try {
    const today = todayStr()
    const yesterday = new Date()
    yesterday.setDate(yesterday.getDate() - 1)
    const yStr = yesterday.toISOString().slice(0, 10)

    const fetch = (date) => db.prepare(`
      SELECT t.title, COALESCE(d.name,'') AS direction,
             SUM(ws.duration_actual) AS seconds,
             GROUP_CONCAT(ws.note, ' | ') AS notes
      FROM work_sessions ws
      JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE date(ws.started_at) = ? AND ws.duration_actual > 0 AND ws.ended_at IS NOT NULL
      GROUP BY ws.task_id
      ORDER BY seconds DESC
    `).all(date)

    const todayDone = db.prepare(
      `SELECT title FROM tasks WHERE date(done_at) = ? AND deleted_at IS NULL ORDER BY done_at ASC`
    ).all(today).map(r => r.title)

    const todayPlan = db.prepare(`
      SELECT t.title FROM day_plan dp JOIN tasks t ON t.id = dp.task_id
      WHERE dp.date = ? AND t.done_at IS NULL AND t.deleted_at IS NULL
      ORDER BY dp.order_index ASC
    `).all(today).map(r => r.title)

    res.json({
      yesterday: fetch(yStr),
      today: fetch(today),
      today_done: todayDone,
      today_plan: todayPlan,
    })
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// GET /api/monthly-summary?months=1|3 — stats for last N months
app.get('/api/monthly-summary', (req, res) => {
  try {
    const months = parseInt(req.query.months) || 1
    const since = months === 1
      ? `date('now','start of month')`
      : `date('now','-${months - 1} months','start of month')`

    const done_count = db.prepare(
      `SELECT COUNT(*) AS n FROM tasks WHERE date(done_at) >= ${since} AND deleted_at IS NULL`
    ).get().n

    const time_seconds = db.prepare(
      `SELECT COALESCE(SUM(duration_actual),0) AS s FROM work_sessions WHERE date(started_at) >= ${since}`
    ).get().s

    const by_direction = db.prepare(`
      SELECT t.direction_id, COALESCE(d.name,'Без направления') AS direction_name,
             SUM(ws.duration_actual) AS seconds,
             COUNT(DISTINCT ws.task_id) AS task_count
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE date(ws.started_at) >= ${since} AND ws.duration_actual > 0
      GROUP BY t.direction_id ORDER BY seconds DESC
    `).all()

    const done_tasks = db.prepare(`
      SELECT t.title, COALESCE(d.name,'') AS direction
      FROM tasks t LEFT JOIN directions d ON d.id = t.direction_id
      WHERE date(t.done_at) >= ${since} AND t.deleted_at IS NULL
      ORDER BY t.done_at ASC LIMIT 30
    `).all()

    // Active days (days with at least one session)
    const active_days = db.prepare(
      `SELECT COUNT(DISTINCT date(started_at)) AS n FROM work_sessions WHERE date(started_at) >= ${since}`
    ).get().n

    res.json({ done_count, time_seconds, by_direction, done_tasks, active_days })
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// ─── Export ──────────────────────────────────────────────────────────────────

// GET /api/export/sessions.csv?period=week|month|all
app.get('/api/export/sessions.csv', (req, res) => {
  try {
    const { period } = req.query
    let dateFilter = ''
    if (period === 'week') dateFilter = `AND date(ws.started_at) >= date('now', '-7 days')`
    else if (period === 'month') dateFilter = `AND date(ws.started_at) >= date('now', '-30 days')`

    const rows = db.prepare(`
      SELECT
        date(ws.started_at) AS date,
        time(ws.started_at) AS time_start,
        time(ws.ended_at)   AS time_end,
        ws.duration_actual  AS duration_seconds,
        t.title             AS task,
        COALESCE(d.name, '') AS direction,
        COALESCE(ws.note, '') AS note
      FROM work_sessions ws
      LEFT JOIN tasks t ON t.id = ws.task_id
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE ws.ended_at IS NOT NULL AND ws.duration_actual > 0 ${dateFilter}
      ORDER BY ws.started_at ASC
    `).all()

    const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`
    const header = ['Дата', 'Начало', 'Конец', 'Секунд', 'Задача', 'Направление', 'Комментарий']
    const lines = [
      header.map(escape).join(','),
      ...rows.map(r => [r.date, r.time_start, r.time_end, r.duration_seconds, r.task, r.direction, r.note].map(escape).join(','))
    ]

    res.setHeader('Content-Type', 'text/csv; charset=utf-8')
    res.setHeader('Content-Disposition', `attachment; filename="focusboard-sessions.csv"`)
    res.send('﻿' + lines.join('\r\n'))
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// GET /api/export/tasks.csv
app.get('/api/export/tasks.csv', (_req, res) => {
  try {
    const rows = db.prepare(`
      SELECT
        t.title,
        COALESCE(d.name, '') AS direction,
        t.priority,
        t.deadline,
        date(t.done_at) AS done_date,
        COALESCE(t.notes, '') AS notes
      FROM tasks t
      LEFT JOIN directions d ON d.id = t.direction_id
      WHERE t.deleted_at IS NULL
      ORDER BY t.done_at DESC NULLS LAST, t.id DESC
    `).all()

    const escape = v => `"${String(v ?? '').replace(/"/g, '""')}"`
    const header = ['Задача', 'Направление', 'Приоритет', 'Дедлайн', 'Выполнена', 'Заметки']
    const lines = [
      header.map(escape).join(','),
      ...rows.map(r => [r.title, r.direction, r.priority ?? '', r.deadline ?? '', r.done_date ?? '', r.notes].map(escape).join(','))
    ]

    res.setHeader('Content-Type', 'text/csv; charset=utf-8')
    res.setHeader('Content-Disposition', `attachment; filename="focusboard-tasks.csv"`)
    res.send('﻿' + lines.join('\r\n'))
  } catch(e) { res.status(500).json({ error: e.message }) }
})

// ─── Frontend static (SPA) ───────────────────────────────────────────────────

app.use(express.static(path.join(__dirname, '..', 'frontend', 'dist')))
app.use((_req, res) => {
  res.sendFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'))
})

// ─── Start ────────────────────────────────────────────────────────────────────

// Только localhost: API с личными задачами не должен быть виден другим
// устройствам в той же Wi-Fi-сети.
app.listen(PORT, '127.0.0.1', () => {
  console.log(`Focus Board backend → http://127.0.0.1:${PORT}`)
})
