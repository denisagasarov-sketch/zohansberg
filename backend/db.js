const Database = require('better-sqlite3')
const path = require('path')
const fs = require('fs')

const dataDir = path.join(__dirname, 'data')
if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true })

const db = new Database(path.join(dataDir, 'focus.db'))

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
  `)
  try { db.exec(`ALTER TABLE tasks ADD COLUMN is_important INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN is_urgent INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE tasks ADD COLUMN direction_order INTEGER NOT NULL DEFAULT 0`) } catch {}
  try { db.exec(`ALTER TABLE work_sessions ADD COLUMN note TEXT`) } catch {}

  // Migrate slots: next/later/someday → queue, remove old CHECK constraint
  const migrated = db.prepare(`SELECT value FROM settings WHERE key = 'slot_v2_queue'`).get()
  if (!migrated) {
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
    console.log('[startup] Migrated slots to v2 (now/queue)')
  }
}

function cleanupTrash() {
  const result = db
    .prepare("DELETE FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-30 days')")
    .run()
  if (result.changes > 0) {
    console.log(`[startup] Cleaned up ${result.changes} trashed task(s) older than 30 days`)
  }
}

module.exports = { db, initSchema, cleanupTrash }
