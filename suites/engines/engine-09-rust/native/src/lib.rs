//! engine-09 (Tier A, A4): cdylib Rust real via cargo-ndk.
//! Sem dependências externas (build offline); JNI exports com nomes reais.
//! A âncora de pânico com condição irreconhecível pelo otimizador mantém
//! `rust_begin_unwind` (core) vivo no objeto e no .symtab (strip=false) —
//! âncora elf-strings do contrato.

use std::hint::black_box;

const ENGINE: &str = "engine-09-rust";
const MARKER: &str = "apktester-rust-native";

fn checksum_inner(seed: u32) -> u32 {
    let mut h = seed;
    for b in ENGINE.bytes() {
        h = h.wrapping_mul(31).wrapping_add(b as u32);
    }
    for b in MARKER.bytes() {
        h = h.wrapping_mul(31).wrapping_add(b as u32);
    }
    h
}

#[no_mangle]
pub extern "C" fn Java_dev_apktester_engine_engine09rust_probe_probe(
    _env: *mut core::ffi::c_void,
    _thiz: *mut core::ffi::c_void,
) -> i32 {
    // Condição runtime (pid == 0 nunca acontece num processo real): o
    // compilador não consegue remover o ramo do pânico, então a machinery
    // rust_begin_unwind permanece linkada no cdylib.
    if black_box(std::process::id() == 0) {
        panic!("apktester: âncora de contrato inatingível por construção");
    }
    checksum_inner(20261022) as i32
}

#[no_mangle]
pub extern "C" fn apktester_rust_version() -> *const u8 {
    ENGINE.as_ptr()
}
