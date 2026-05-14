use dirs::data_dir;
use rusqlite::{Connection, Result};
use std::path::PathBuf;

pub type Db = Connection;

pub fn get_db_path() -> PathBuf {
    let mut path = data_dir().unwrap_or_else(|| PathBuf::from("."));
    path.push("FocusBoard");
    std::fs::create_dir_all(&path).ok();
    path.push("focus.db");
    path
}

pub fn init() -> Result<Db> {
    let path = get_db_path();
    let conn = Connection::open(&path)?;
    conn.execute_batch("PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;")?;
    init_schema(&conn)?;
    Ok(conn)
}

pub fn init_schema(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "
        CREATE TABLE IF NOT EXISTS directions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            direction_id INTEGER REFERENCES directions(id),
            priority TEXT CHECK(priority IN ('high','medium','low')) DEFAULT 'medium',
            status TEXT CHECK(status IN ('todo','in_progress','done','frozen')) DEFAULT 'todo',
            slot TEXT CHECK(slot IN ('now','next','later','someday')) DEFAULT 'later',
            slot_order INTEGER DEFAULT 0,
            deadline TEXT,
            duration_plan REAL,
            duration_fact REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            done_at TEXT,
            deleted_at TEXT
        );
        CREATE TABLE IF NOT EXISTS work_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER REFERENCES tasks(id),
            started_at TEXT,
            ended_at TEXT,
            duration_actual INTEGER
        );
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT CHECK(type IN ('checkin','thought')),
            mood INTEGER,
            goal TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS direction_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction_id INTEGER REFERENCES directions(id),
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    ",
    )
}

pub fn cleanup_trash(conn: &Connection) -> Result<()> {
    conn.execute(
        "DELETE FROM tasks WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-30 days')",
        [],
    )?;
    Ok(())
}
