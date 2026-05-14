use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Mutex;
use tauri::State;

type Db = Mutex<Connection>;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Direction {
    pub id: i64,
    pub name: String,
    pub order_index: i64,
    pub archived: i64,
    pub created_at: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Task {
    pub id: i64,
    pub title: String,
    pub direction_id: Option<i64>,
    pub priority: String,
    pub status: String,
    pub slot: String,
    pub slot_order: i64,
    pub deadline: Option<String>,
    pub duration_plan: Option<f64>,
    pub duration_fact: f64,
    pub notes: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub done_at: Option<String>,
    pub deleted_at: Option<String>,
    pub direction_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct WorkSession {
    pub id: i64,
    pub task_id: i64,
    pub started_at: String,
    pub ended_at: Option<String>,
    pub duration_actual: Option<i64>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct JournalEntry {
    pub id: i64,
    #[serde(rename = "type")]
    pub entry_type: String,
    pub mood: Option<i64>,
    pub goal: Option<String>,
    pub content: Option<String>,
    pub created_at: String,
}

// ─── Directions ────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_directions(db: State<'_, Db>) -> Result<Vec<Direction>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn.prepare(
        "SELECT id, name, order_index, archived, created_at FROM directions WHERE archived=0 ORDER BY order_index, id"
    ).map_err(|e| e.to_string())?;
    let dirs = stmt
        .query_map([], |row| {
            Ok(Direction {
                id: row.get(0)?,
                name: row.get(1)?,
                order_index: row.get(2)?,
                archived: row.get(3)?,
                created_at: row.get(4)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(dirs)
}

#[tauri::command]
pub fn get_all_directions(db: State<'_, Db>) -> Result<Vec<Direction>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn.prepare(
        "SELECT id, name, order_index, archived, created_at FROM directions ORDER BY order_index, id"
    ).map_err(|e| e.to_string())?;
    let dirs = stmt
        .query_map([], |row| {
            Ok(Direction {
                id: row.get(0)?,
                name: row.get(1)?,
                order_index: row.get(2)?,
                archived: row.get(3)?,
                created_at: row.get(4)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(dirs)
}

#[tauri::command]
pub fn create_direction(db: State<'_, Db>, name: String) -> Result<Direction, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute("INSERT INTO directions (name) VALUES (?1)", params![name])
        .map_err(|e| e.to_string())?;
    let id = conn.last_insert_rowid();
    let dir = conn
        .query_row(
            "SELECT id, name, order_index, archived, created_at FROM directions WHERE id=?1",
            params![id],
            |row| {
                Ok(Direction {
                    id: row.get(0)?,
                    name: row.get(1)?,
                    order_index: row.get(2)?,
                    archived: row.get(3)?,
                    created_at: row.get(4)?,
                })
            },
        )
        .map_err(|e| e.to_string())?;
    Ok(dir)
}

#[tauri::command]
pub fn update_direction(
    db: State<'_, Db>,
    id: i64,
    name: Option<String>,
    order_index: Option<i64>,
    archived: Option<i64>,
) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    if let Some(n) = name {
        conn.execute("UPDATE directions SET name=?1 WHERE id=?2", params![n, id])
            .map_err(|e| e.to_string())?;
    }
    if let Some(o) = order_index {
        conn.execute(
            "UPDATE directions SET order_index=?1 WHERE id=?2",
            params![o, id],
        )
        .map_err(|e| e.to_string())?;
    }
    if let Some(a) = archived {
        conn.execute(
            "UPDATE directions SET archived=?1 WHERE id=?2",
            params![a, id],
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn archive_direction(db: State<'_, Db>, id: i64) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute("UPDATE directions SET archived=1 WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

// ─── Tasks helpers ──────────────────────────────────────────────────────────

fn query_tasks(
    conn: &Connection,
    extra_where: &str,
    include_deleted: bool,
) -> Result<Vec<Task>, String> {
    let deleted_clause = if include_deleted {
        String::new()
    } else {
        "t.deleted_at IS NULL AND ".to_string()
    };
    let sql = format!(
        "SELECT t.id, t.title, t.direction_id, t.priority, t.status, t.slot, t.slot_order,
                t.deadline, t.duration_plan, t.duration_fact, t.notes, t.created_at,
                t.updated_at, t.done_at, t.deleted_at, d.name
         FROM tasks t LEFT JOIN directions d ON t.direction_id = d.id
         WHERE {}{}
         ORDER BY t.slot_order, t.priority DESC, t.deadline, t.created_at",
        deleted_clause, extra_where
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let tasks = stmt
        .query_map([], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                direction_id: row.get(2)?,
                priority: row.get(3)?,
                status: row.get(4)?,
                slot: row.get(5)?,
                slot_order: row.get(6)?,
                deadline: row.get(7)?,
                duration_plan: row.get(8)?,
                duration_fact: row.get(9)?,
                notes: row.get(10)?,
                created_at: row.get(11)?,
                updated_at: row.get(12)?,
                done_at: row.get(13)?,
                deleted_at: row.get(14)?,
                direction_name: row.get(15)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(tasks)
}

fn fetch_task_by_id(conn: &Connection, id: i64) -> Result<Task, String> {
    conn.query_row(
        "SELECT t.id, t.title, t.direction_id, t.priority, t.status, t.slot, t.slot_order,
                t.deadline, t.duration_plan, t.duration_fact, t.notes, t.created_at,
                t.updated_at, t.done_at, t.deleted_at, d.name
         FROM tasks t LEFT JOIN directions d ON t.direction_id=d.id
         WHERE t.id=?1",
        params![id],
        |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                direction_id: row.get(2)?,
                priority: row.get(3)?,
                status: row.get(4)?,
                slot: row.get(5)?,
                slot_order: row.get(6)?,
                deadline: row.get(7)?,
                duration_plan: row.get(8)?,
                duration_fact: row.get(9)?,
                notes: row.get(10)?,
                created_at: row.get(11)?,
                updated_at: row.get(12)?,
                done_at: row.get(13)?,
                deleted_at: row.get(14)?,
                direction_name: row.get(15)?,
            })
        },
    )
    .map_err(|e| e.to_string())
}

// ─── Tasks ──────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_tasks(db: State<'_, Db>) -> Result<Vec<Task>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    query_tasks(&conn, "1=1", false)
}

#[tauri::command]
pub fn create_task(
    db: State<'_, Db>,
    title: String,
    direction_id: Option<i64>,
    priority: Option<String>,
    slot: Option<String>,
    deadline: Option<String>,
    duration_plan: Option<f64>,
    notes: Option<String>,
) -> Result<Task, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let priority = priority.unwrap_or_else(|| "medium".to_string());
    let slot = slot.unwrap_or_else(|| "later".to_string());
    conn.execute(
        "INSERT INTO tasks (title, direction_id, priority, slot, deadline, duration_plan, notes)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![
            title,
            direction_id,
            priority,
            slot,
            deadline,
            duration_plan,
            notes
        ],
    )
    .map_err(|e| e.to_string())?;
    let id = conn.last_insert_rowid();
    fetch_task_by_id(&conn, id)
}

#[derive(Debug, Deserialize)]
pub struct UpdateTaskInput {
    pub title: Option<String>,
    pub direction_id: Option<serde_json::Value>,
    pub priority: Option<String>,
    pub status: Option<String>,
    pub slot: Option<String>,
    pub slot_order: Option<i64>,
    pub deadline: Option<serde_json::Value>,
    pub duration_plan: Option<serde_json::Value>,
    pub notes: Option<serde_json::Value>,
}

#[tauri::command]
pub fn update_task(db: State<'_, Db>, id: i64, input: UpdateTaskInput) -> Result<Task, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;

    // If setting slot to 'now', evict the current 'now' task to 'next'
    if input.slot.as_deref() == Some("now") {
        conn.execute(
            "UPDATE tasks SET slot='next', slot_order=0, updated_at=datetime('now')
             WHERE slot='now' AND deleted_at IS NULL AND id != ?1",
            params![id],
        )
        .map_err(|e| e.to_string())?;
    }

    // Build dynamic UPDATE using safe string interpolation for literals only;
    // values that originate from user input are escaped via replace on quotes.
    let mut parts: Vec<String> = vec!["updated_at=datetime('now')".to_string()];

    if let Some(ref v) = input.title {
        parts.push(format!("title='{}'", v.replace('\'', "''")));
    }
    if let Some(ref v) = input.priority {
        parts.push(format!("priority='{}'", v.replace('\'', "''")));
    }
    if let Some(ref v) = input.status {
        parts.push(format!("status='{}'", v.replace('\'', "''")));
        if v == "done" {
            parts.push("done_at=datetime('now')".to_string());
        } else {
            parts.push("done_at=NULL".to_string());
        }
    }
    if let Some(ref v) = input.slot {
        parts.push(format!("slot='{}'", v.replace('\'', "''")));
    }
    if let Some(v) = input.slot_order {
        parts.push(format!("slot_order={}", v));
    }
    if let Some(ref v) = input.direction_id {
        match v {
            serde_json::Value::Null => parts.push("direction_id=NULL".to_string()),
            serde_json::Value::Number(n) => parts.push(format!("direction_id={}", n)),
            _ => {}
        }
    }
    if let Some(ref v) = input.deadline {
        match v {
            serde_json::Value::Null => parts.push("deadline=NULL".to_string()),
            serde_json::Value::String(s) => {
                parts.push(format!("deadline='{}'", s.replace('\'', "''")));
            }
            _ => {}
        }
    }
    if let Some(ref v) = input.duration_plan {
        match v {
            serde_json::Value::Null => parts.push("duration_plan=NULL".to_string()),
            serde_json::Value::Number(n) => parts.push(format!("duration_plan={}", n)),
            _ => {}
        }
    }
    if let Some(ref v) = input.notes {
        match v {
            serde_json::Value::Null => parts.push("notes=NULL".to_string()),
            serde_json::Value::String(s) => {
                parts.push(format!("notes='{}'", s.replace('\'', "''")));
            }
            _ => {}
        }
    }

    let sql = format!("UPDATE tasks SET {} WHERE id={}", parts.join(", "), id);
    conn.execute(&sql, []).map_err(|e| e.to_string())?;

    fetch_task_by_id(&conn, id)
}

#[tauri::command]
pub fn delete_task(db: State<'_, Db>, id: i64) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE tasks SET deleted_at=datetime('now') WHERE id=?1",
        params![id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn get_trash(db: State<'_, Db>) -> Result<Vec<Task>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    query_tasks(&conn, "t.deleted_at IS NOT NULL", true)
}

#[tauri::command]
pub fn restore_task(db: State<'_, Db>, id: i64) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute("UPDATE tasks SET deleted_at=NULL WHERE id=?1", params![id])
        .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn take_now(db: State<'_, Db>, task_id: i64) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE tasks SET slot='next', slot_order=0, updated_at=datetime('now')
         WHERE slot='now' AND deleted_at IS NULL AND id != ?1",
        params![task_id],
    )
    .map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE tasks SET slot='now', updated_at=datetime('now') WHERE id=?1",
        params![task_id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn reorder_tasks(db: State<'_, Db>, slot: String, ordered_ids: Vec<i64>) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let _ = slot; // slot provided for context; ordering is by position in ordered_ids
    for (i, id) in ordered_ids.iter().enumerate() {
        conn.execute(
            "UPDATE tasks SET slot_order=?1, updated_at=datetime('now') WHERE id=?2",
            params![i as i64, id],
        )
        .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
pub fn reset_order(db: State<'_, Db>, slot: String) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE tasks SET slot_order=0 WHERE slot=?1 AND deleted_at IS NULL",
        params![slot],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn get_done_tasks(
    db: State<'_, Db>,
    direction_id: Option<i64>,
    search: Option<String>,
) -> Result<Vec<Task>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let mut condition = "t.status='done' AND t.deleted_at IS NULL".to_string();
    if let Some(did) = direction_id {
        condition.push_str(&format!(" AND t.direction_id={}", did));
    }
    if let Some(ref s) = search {
        condition.push_str(&format!(" AND t.title LIKE '%{}%'", s.replace('\'', "''")));
    }
    let sql = format!(
        "SELECT t.id, t.title, t.direction_id, t.priority, t.status, t.slot, t.slot_order,
                t.deadline, t.duration_plan, t.duration_fact, t.notes, t.created_at,
                t.updated_at, t.done_at, t.deleted_at, d.name
         FROM tasks t LEFT JOIN directions d ON t.direction_id=d.id
         WHERE {}
         ORDER BY t.done_at DESC",
        condition
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let tasks = stmt
        .query_map([], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                direction_id: row.get(2)?,
                priority: row.get(3)?,
                status: row.get(4)?,
                slot: row.get(5)?,
                slot_order: row.get(6)?,
                deadline: row.get(7)?,
                duration_plan: row.get(8)?,
                duration_fact: row.get(9)?,
                notes: row.get(10)?,
                created_at: row.get(11)?,
                updated_at: row.get(12)?,
                done_at: row.get(13)?,
                deleted_at: row.get(14)?,
                direction_name: row.get(15)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(tasks)
}

#[tauri::command]
pub fn cleanup_trash(db: State<'_, Db>) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    crate::db::cleanup_trash(&conn).map_err(|e| e.to_string())
}

// ─── Sessions ───────────────────────────────────────────────────────────────

#[tauri::command]
pub fn start_session(
    db: State<'_, Db>,
    task_id: i64,
    started_at: String,
) -> Result<WorkSession, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO work_sessions (task_id, started_at) VALUES (?1, ?2)",
        params![task_id, started_at],
    )
    .map_err(|e| e.to_string())?;
    let id = conn.last_insert_rowid();
    Ok(WorkSession {
        id,
        task_id,
        started_at,
        ended_at: None,
        duration_actual: None,
    })
}

#[tauri::command]
pub fn end_session(
    db: State<'_, Db>,
    id: i64,
    ended_at: String,
    duration_actual: i64,
) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE work_sessions SET ended_at=?1, duration_actual=?2 WHERE id=?3",
        params![ended_at, duration_actual, id],
    )
    .map_err(|e| e.to_string())?;
    conn.execute(
        "UPDATE tasks
         SET duration_fact = COALESCE(duration_fact, 0) + ?1 / 3600.0
         WHERE id = (SELECT task_id FROM work_sessions WHERE id=?2)",
        params![duration_actual, id],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub fn get_today_time(db: State<'_, Db>, task_id: i64) -> Result<i64, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let total: i64 = conn
        .query_row(
            "SELECT COALESCE(SUM(duration_actual), 0)
         FROM work_sessions
         WHERE task_id=?1 AND date(started_at)=date('now')",
            params![task_id],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?;
    Ok(total)
}

#[tauri::command]
pub fn get_session_stats(db: State<'_, Db>, period: String) -> Result<serde_json::Value, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let date_filter = match period.as_str() {
        "week" => "AND date(ws.started_at) >= date('now', '-7 days')",
        "month" => "AND date(ws.started_at) >= date('now', '-30 days')",
        _ => "",
    };
    let sql = format!(
        "SELECT d.name, date(ws.started_at) AS day, SUM(ws.duration_actual) AS total
         FROM work_sessions ws
         JOIN tasks t ON ws.task_id = t.id
         LEFT JOIN directions d ON t.direction_id = d.id
         WHERE ws.duration_actual IS NOT NULL {}
         GROUP BY d.name, day
         ORDER BY day",
        date_filter
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let rows: Vec<serde_json::Value> = stmt
        .query_map([], |row| {
            let dir: Option<String> = row.get(0)?;
            let day: String = row.get(1)?;
            let total: i64 = row.get(2)?;
            Ok(serde_json::json!({
                "direction": dir.unwrap_or_else(|| "Без направления".to_string()),
                "day": day,
                "total": total,
            }))
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(serde_json::Value::Array(rows))
}

// ─── Journal ────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_journal(db: State<'_, Db>) -> Result<Vec<JournalEntry>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare(
            "SELECT id, type, mood, goal, content, created_at
         FROM journal_entries
         ORDER BY created_at DESC",
        )
        .map_err(|e| e.to_string())?;
    let entries = stmt
        .query_map([], |row| {
            Ok(JournalEntry {
                id: row.get(0)?,
                entry_type: row.get(1)?,
                mood: row.get(2)?,
                goal: row.get(3)?,
                content: row.get(4)?,
                created_at: row.get(5)?,
            })
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(entries)
}

#[tauri::command]
pub fn create_journal_entry(
    db: State<'_, Db>,
    entry_type: String,
    mood: Option<i64>,
    goal: Option<String>,
    content: Option<String>,
) -> Result<JournalEntry, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO journal_entries (type, mood, goal, content) VALUES (?1, ?2, ?3, ?4)",
        params![entry_type, mood, goal, content],
    )
    .map_err(|e| e.to_string())?;
    let id = conn.last_insert_rowid();
    let entry = conn
        .query_row(
            "SELECT id, type, mood, goal, content, created_at FROM journal_entries WHERE id=?1",
            params![id],
            |row| {
                Ok(JournalEntry {
                    id: row.get(0)?,
                    entry_type: row.get(1)?,
                    mood: row.get(2)?,
                    goal: row.get(3)?,
                    content: row.get(4)?,
                    created_at: row.get(5)?,
                })
            },
        )
        .map_err(|e| e.to_string())?;
    Ok(entry)
}

#[tauri::command]
pub fn get_today_checkin(db: State<'_, Db>) -> Result<bool, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let count: i64 = conn
        .query_row(
            "SELECT COUNT(*) FROM journal_entries
         WHERE type='checkin' AND date(created_at)=date('now')",
            [],
            |row| row.get(0),
        )
        .map_err(|e| e.to_string())?;
    Ok(count > 0)
}

// ─── Settings ───────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_settings(db: State<'_, Db>) -> Result<HashMap<String, String>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let mut stmt = conn
        .prepare("SELECT key, value FROM settings")
        .map_err(|e| e.to_string())?;
    let map: HashMap<String, String> = stmt
        .query_map([], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();
    Ok(map)
}

#[tauri::command]
pub fn update_setting(db: State<'_, Db>, key: String, value: String) -> Result<(), String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?1, ?2)
         ON CONFLICT(key) DO UPDATE SET value=?2",
        params![key, value],
    )
    .map_err(|e| e.to_string())?;
    Ok(())
}

// ─── Recommendation ─────────────────────────────────────────────────────────

#[derive(Serialize)]
pub struct Recommendation {
    pub task: Task,
    pub reason: String,
}

#[tauri::command]
pub fn get_recommendation(
    db: State<'_, Db>,
    skip_id: Option<i64>,
) -> Result<Option<Recommendation>, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;
    let skip_clause = skip_id
        .map(|sid| format!("AND t.id != {}", sid))
        .unwrap_or_default();

    let base = format!(
        "SELECT t.id, t.title, t.direction_id, t.priority, t.status, t.slot, t.slot_order,
                t.deadline, t.duration_plan, t.duration_fact, t.notes, t.created_at,
                t.updated_at, t.done_at, t.deleted_at, d.name
         FROM tasks t LEFT JOIN directions d ON t.direction_id=d.id
         WHERE t.deleted_at IS NULL AND t.slot != 'now' AND t.status != 'done' {}",
        skip_clause
    );

    let fetch = |extra_where: &str, order: &str| -> Option<Task> {
        let sql = format!("{} AND ({}) ORDER BY {} LIMIT 1", base, extra_where, order);
        conn.query_row(&sql, [], |row| {
            Ok(Task {
                id: row.get(0)?,
                title: row.get(1)?,
                direction_id: row.get(2)?,
                priority: row.get(3)?,
                status: row.get(4)?,
                slot: row.get(5)?,
                slot_order: row.get(6)?,
                deadline: row.get(7)?,
                duration_plan: row.get(8)?,
                duration_fact: row.get(9)?,
                notes: row.get(10)?,
                created_at: row.get(11)?,
                updated_at: row.get(12)?,
                done_at: row.get(13)?,
                deleted_at: row.get(14)?,
                direction_name: row.get(15)?,
            })
        })
        .ok()
    };

    // Priority hierarchy: first matching rule wins
    let candidates: &[(&str, &str, &str)] = &[
        (
            "t.slot='next'",
            "t.slot_order, t.priority DESC",
            "следующая",
        ),
        (
            "t.deadline = date('now')",
            "t.priority DESC",
            "дедлайн сегодня",
        ),
        (
            "t.deadline = date('now', '+1 day')",
            "t.priority DESC",
            "дедлайн завтра",
        ),
        ("t.priority='high'", "t.updated_at", "самая приоритетная"),
        ("1=1", "t.updated_at", "давно без движения"),
    ];

    for &(cond, order, reason) in candidates {
        if let Some(task) = fetch(cond, order) {
            return Ok(Some(Recommendation {
                task,
                reason: reason.to_string(),
            }));
        }
    }
    Ok(None)
}

// ─── Stats ──────────────────────────────────────────────────────────────────

#[tauri::command]
pub fn get_stats(db: State<'_, Db>, period: String) -> Result<serde_json::Value, String> {
    let conn = db.lock().map_err(|e| e.to_string())?;

    let (date_filter, ws_filter, mood_filter) = match period.as_str() {
        "week" => (
            "AND date(t.done_at) >= date('now', '-7 days')",
            "AND date(ws.started_at) >= date('now', '-7 days')",
            "AND date(created_at) >= date('now', '-7 days')",
        ),
        "month" => (
            "AND date(t.done_at) >= date('now', '-30 days')",
            "AND date(ws.started_at) >= date('now', '-30 days')",
            "AND date(created_at) >= date('now', '-30 days')",
        ),
        _ => ("", "", ""),
    };

    // Tasks done by direction
    let sql = format!(
        "SELECT COALESCE(d.name, 'Без направления'), COUNT(*)
         FROM tasks t LEFT JOIN directions d ON t.direction_id=d.id
         WHERE t.status='done' AND t.deleted_at IS NULL {}
         GROUP BY d.name",
        date_filter
    );
    let mut stmt = conn.prepare(&sql).map_err(|e| e.to_string())?;
    let tasks_done: Vec<serde_json::Value> = stmt
        .query_map([], |row| {
            Ok(serde_json::json!({
                "direction": row.get::<_, String>(0)?,
                "count": row.get::<_, i64>(1)?,
            }))
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Time worked by day and direction
    let sql2 = format!(
        "SELECT date(ws.started_at), COALESCE(d.name, 'Без направления'), SUM(ws.duration_actual)
         FROM work_sessions ws
         JOIN tasks t ON ws.task_id = t.id
         LEFT JOIN directions d ON t.direction_id = d.id
         WHERE ws.duration_actual IS NOT NULL {}
         GROUP BY date(ws.started_at), d.name
         ORDER BY date(ws.started_at)",
        ws_filter
    );
    let mut stmt2 = conn.prepare(&sql2).map_err(|e| e.to_string())?;
    let time_worked: Vec<serde_json::Value> = stmt2
        .query_map([], |row| {
            Ok(serde_json::json!({
                "day":       row.get::<_, String>(0)?,
                "direction": row.get::<_, String>(1)?,
                "seconds":   row.get::<_, i64>(2)?,
            }))
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Mood by day
    let sql3 = format!(
        "SELECT date(created_at), mood
         FROM journal_entries
         WHERE type='checkin' {}
         ORDER BY created_at",
        mood_filter
    );
    let mut stmt3 = conn.prepare(&sql3).map_err(|e| e.to_string())?;
    let mood_by_day: Vec<serde_json::Value> = stmt3
        .query_map([], |row| {
            Ok(serde_json::json!({
                "day":  row.get::<_, String>(0)?,
                "mood": row.get::<_, i64>(1)?,
            }))
        })
        .map_err(|e| e.to_string())?
        .filter_map(|r| r.ok())
        .collect();

    // Journal aggregate stats
    let total_entries: i64 = conn
        .query_row(
            &format!(
                "SELECT COUNT(*) FROM journal_entries WHERE 1=1 {}",
                mood_filter
            ),
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    let checkin_days: i64 = conn
        .query_row(
            &format!(
            "SELECT COUNT(DISTINCT date(created_at)) FROM journal_entries WHERE type='checkin' {}",
            mood_filter
        ),
            [],
            |row| row.get(0),
        )
        .unwrap_or(0);

    Ok(serde_json::json!({
        "tasks_done":    tasks_done,
        "time_worked":   time_worked,
        "mood_by_day":   mood_by_day,
        "journal_stats": {
            "total_entries": total_entries,
            "checkin_days":  checkin_days,
        },
    }))
}
