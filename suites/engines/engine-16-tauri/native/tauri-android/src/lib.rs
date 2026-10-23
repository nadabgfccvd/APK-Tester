//! engine-16 (Tier A, A4): cdylib que LINKA o crate tauri v2 real.
//! A referência de tipos (Option<tauri::Wry>) força o depend a ser
//! compilado e linkado no cdylib sem exigir um app Tauri completo.

#[allow(unused)]
fn tauri_anchor() -> i32 {
    // Type-level anchor: compila a stack tauri + tauri-runtime-wry.
    let _runtime: Option<tauri::Wry> = None;
    let _app: Option<tauri::App<tauri::Wry>> = None;
    20261022
}

#[no_mangle]
pub extern "C" fn apktester_tauri_probe() -> i32 {
    tauri_anchor()
}
