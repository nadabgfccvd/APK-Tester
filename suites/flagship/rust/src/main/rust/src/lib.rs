//! R2.2 (AUDIT_ROADMAP_V2) — probe Rust mínimo do flagship Behemoth.
//!
//! UMA função JNI (soma i32, provável e sem estado), mesma semântica do
//! probe C do `:native`. Sem crate `jni`: a assinatura JNI é exportada à
//! mão (sem dependências — o Cargo.lock fecha vazio e o ELF fica auditável).
//! A detecção não valida payload nem autoriza execução (ADR 0003).

use std::os::raw::{c_int, c_void};

/// Soma inteira via JNI — a única função do probe (espelho do `:native`).
#[no_mangle]
pub extern "system" fn Java_dev_apktester_behemoth_rustprobe_RustProbe_nativeSum(
    _env: *mut c_void,
    _class: *mut c_void,
    a: c_int,
    b: c_int,
) -> c_int {
    a.wrapping_add(b)
}
