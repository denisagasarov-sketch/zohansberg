const Database = require('better-sqlite3')
const path = require('path')
const fs = require('fs')

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'data', 'focus.db')
const dataDir = path.dirname(DB_PATH)
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true })

const db = new Database(DB_PATH)

db.pragma('journal_mode = WAL')
db.pragma('foreign_keys = ON')

function initSchema() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS directions (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      name        TEXT NOT NULL,
      order_index INTEGER DEFAULT 0,
      archived    INTEGER DEFAULT 0,
      created_at  TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS tasks (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      title         TEXT NOT NULL,
      direction_id  INTEGER REFERENCES directions(id),
      priority      TEXT CHECK(priority IN ('high','medium','low')) DEFAULT 'medium',
      status        TEXT CHECK(status IN ('todo','in_progress','done','frozen')) DEFAULT 'todo',
      slot          TEXT CHECK(slot IN ('now','next','later','someday')) DEFAULT 'later',
      slot_order    INTEGER DEFAULT 0,
      deadline      TEXT,
      duration_plan REAL,
      duration_fact REAL DEFAULT 0,
      notes         TEXT,
      created_at    TEXT DEFAULT (datetime('now')),
      updated_at    TEXT DEFAULT (datetime('now')),
      done_at       TEXT,
      deleted_at    TEXT
    );

    CREATE TABLE IF NOT EXISTS work_sessions (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      task_id         INTEGER REFERENCES tasks(id),
      started_at      TEXT,
      ended_at        TEXT,
      duration_actual INTEGER
    );

    CREATE TABLE IF NOT EXISTS journal_entries (
      id         INTEGER PRIMARY KEY AUTOINCREMENT,
      type       TEXT CHECK(type IN ('checkin','thought')),
      mood       INTEGER,
      goal       TEXT,
      content    TEXT,
      created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS settings (
      key   TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE TABLE IF NOT EXISTS direction_notes (
      id           INTEGER PRIMARY KEY AUTOINCREMENT,
      direction_id INTEGER REFERENCES directions(id),
      content      TEXT,
      created_at   TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS day_plan (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      date        TEXT NOT NULL,
      task_id     INTEGER REFERENCES tasks(id),
      order_index INTEGER NOT NULL DEFAULT 0
    );
  `)
  try { db.exec(`ALTER TABLE directions ADD COLUMN notes TEXT`) } catch {}
  try { db.exec(`ALTER TABLE directions ADD COLUMN weekly_goal_seconds INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN recurrence TEXT`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN recurrence_last_date TEXT`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN is_important INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN is_urgent INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN direction_order INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE work_sessions ADD COLUMN note TEXT`) } catch {}
  try { db.exec(`ALTER TABLE work_sessions ADD COLUMN elapsed_seconds INTEGER DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN in_queue INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN someday INTEGER NOT NULL DEFAULT 0`) } catch {}

  // Migrate slots: next/later/someday → queue, remove old CHECK constraint
  const migrated = db.prepare(`SELECT value FROM settings WHERE key = 'slot_v2_queue'`).get()
  if (!migrated) {
    db.pragma('foreign_keys = OFF')
    db.transaction(() => {
      db.exec(`
        CREATE TABLE tasks_new (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          title         TEXT NOT NULL,
          direction_id  INTEGER REFERENCES directions(id),
          priority      TEXT CHECK(priority IN ('high','medium','low')) DEFAULT 'medium',
          slot          TEXT CHECK(slot IN ('now','queue')) DEFAULT 'queue',
          slot_order    INTEGER DEFAULT 0,
          direction_order INTEGER NOT NULL DEFAULT 0,
          deadline      TEXT,
          duration_plan REAL,
          duration_fact REAL DEFAULT 0,
          notes         TEXT,
          created_at    TEXT DEFAULT (datetime('now')),
          updated_at    TEXT DEFAULT (datetime('now')),
          done_at       TEXT,
          deleted_at    TEXT
        )
      `)
      db.exec(`
        INSERT INTO tasks_new
          (id, title, direction_id, priority, slot, slot_order, direction_order,
           deadline, duration_plan, duration_fact, notes, created_at, updated_at, done_at, deleted_at)
        SELECT
          id, title, direction_id, priority,
          CASE WHEN slot = 'now' THEN 'now' ELSE 'queue' END AS slot,
          slot_order,
          COALESCE(direction_order, 0),
          deadline, duration_plan, duration_fact, notes, created_at, updated_at, done_at, deleted_at
        FROM tasks
      `)
      db.exec(`DROP TABLE tasks`)
      db.exec(`ALTER TABLE tasks_new RENAME TO tasks`)
      db.exec(`INSERT INTO settings (key, value) VALUES ('slot_v2_queue', '1') ON CONFLICT(key) DO UPDATE SET value = '1'`)
    })()
    db.pragma('foreign_keys = ON')
    console.log('[startup] Migrated slots to v2 (now/queue)')
  }

  // Migrate priority: high/medium/low → I/II/III/none
  const priorityMigrated = db.prepare(`SELECT value FROM settings WHERE key = 'priority_v2'`).get()
  if (!priorityMigrated) {
    db.pragma('foreign_keys = OFF')
    db.transaction(() => {
      db.exec(`
        CREATE TABLE tasks_new (
          id              INTEGER PRIMARY KEY AUTOINCREMENT,
          title           TEXT NOT NULL,
          direction_id    INTEGER REFERENCES directions(id),
          priority        TEXT DEFAULT 'none',
          slot            TEXT CHECK(slot IN ('now','queue')) DEFAULT 'queue',
          slot_order      INTEGER DEFAULT 0,
          direction_order INTEGER NOT NULL DEFAULT 0,
          deadline        TEXT,
          duration_plan   REAL,
          duration_fact   REAL DEFAULT 0,
          notes           TEXT,
          in_queue        INTEGER NOT NULL DEFAULT 0,
          someday         INTEGER NOT NULL DEFAULT 0,
          created_at      TEXT DEFAULT (datetime('now')),
          updated_at      TEXT DEFAULT (datetime('now')),
          done_at         TEXT,
          deleted_at      TEXT
        )
      `)
      db.exec(`
        INSERT INTO tasks_new
          (id, title, direction_id, priority, slot, slot_order, direction_order,
           deadline, duration_plan, duration_fact, notes, in_queue, someday,
           created_at, updated_at, done_at, deleted_at)
        SELECT
          id, title, direction_id,
          CASE priority WHEN 'high' THEN 'I' WHEN 'medium' THEN 'II' WHEN 'low' THEN 'III' ELSE 'none' END,
          slot, slot_order, COALESCE(direction_order, 0),
          deadline, duration_plan, duration_fact, notes,
          COALESCE(in_queue, 0), COALESCE(someday, 0),
          created_at, updated_at, done_at, deleted_at
        FROM tasks
      `)
      db.exec(`DROP TABLE tasks`)
      db.exec(`ALTER TABLE tasks_new RENAME TO tasks`)
      db.exec(`INSERT INTO settings (key, value) VALUES ('priority_v2', '1') ON CONFLICT(key) DO UPDATE SET value = '1'`)
    })()
    db.pragma('foreign_keys = ON')
    console.log('[startup] Migrated priority to v2 (I/II/III/none)')
  }

  // Индексы под самые частые запросы (списки задач, статистика, план дня).
  // Создаются в конце: миграции выше пересоздают tasks и снесли бы их.
  db.exec(`
    CREATE INDEX IF NOT EXISTS idx_tasks_deleted   ON tasks(deleted_at);
    CREATE INDEX IF NOT EXISTS idx_tasks_done      ON tasks(done_at);
    CREATE INDEX IF NOT EXISTS idx_sessions_task   ON work_sessions(task_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_start  ON work_sessions(started_at);
    CREATE INDEX IF NOT EXISTS idx_day_plan_date   ON day_plan(date);
  `)
}

function cleanupTrash() {
  // Purge tasks trashed >30 days ago. work_sessions and day_plan reference
  // tasks(id) with no ON DELETE CASCADE, so child rows must go first or the
  // DELETE fails with FOREIGN KEY constraint failed — which, running at
  // startup, used to crash the whole backend (and KeepAlive couldn't revive it).
  // Wrapped so cleanup can never take the server down.
  try {
    const stale = db
      .prepare("SELECT id FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-30 days')")
      .all()
      .map(r => r.id)
    if (stale.length === 0) return
    const placeholders = stale.map(() => '?').join(',')
    const purge = db.transaction(ids => {
      db.prepare(`DELETE FROM work_sessions WHERE task_id IN (${placeholders})`).run(...ids)
      db.prepare(`DELETE FROM day_plan WHERE task_id IN (${placeholders})`).run(...ids)
      return db.prepare(`DELETE FROM tasks WHERE id IN (${placeholders})`).run(...ids)
    })
    const result = purge(stale)
    if (result.changes > 0) {
      console.log(`[startup] Cleaned up ${result.changes} trashed task(s) older than 30 days`)
    }
  } catch (err) {
    console.error('[startup] cleanupTrash skipped due to error:', err.message)
  }
}

module.exports = { db, initSchema, cleanupTrash }
