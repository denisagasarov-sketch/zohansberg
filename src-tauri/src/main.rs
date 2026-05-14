// Prevents additional console window on Windows in release
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod db;

fn main() {
    let db = db::init().expect("failed to init database");
    db::cleanup_trash(&db).ok();

    tauri::Builder::default()
        .manage(std::sync::Mutex::new(db))
        .invoke_handler(tauri::generate_handler![
            // directions
            commands::get_directions,
            commands::get_all_directions,
            commands::create_direction,
            commands::update_direction,
            commands::archive_direction,
            // tasks
            commands::get_tasks,
            commands::create_task,
            commands::update_task,
            commands::delete_task,
            commands::get_trash,
            commands::restore_task,
            commands::take_now,
            commands::reorder_tasks,
            commands::reset_order,
            commands::get_done_tasks,
            commands::cleanup_trash,
            // sessions
            commands::start_session,
            commands::end_session,
            commands::get_today_time,
            commands::get_session_stats,
            // journal
            commands::get_journal,
            commands::create_journal_entry,
            commands::get_today_checkin,
            // settings
            commands::get_settings,
            commands::update_setting,
            // recommendation
            commands::get_recommendation,
            // stats
            commands::get_stats,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
