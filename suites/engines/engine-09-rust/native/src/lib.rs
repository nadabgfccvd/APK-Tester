//! engine-09 (Tier A, A4): cdylib Rust real via cargo-ndk.
//! Sem dependências externas (build offline); JNI exports com nomes reais.
//! O pânico compilado (black_box) garante a presença de `rust_begin_unwind`
//! (core) no ELF — âncora elf-strings do contrato.

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

/// caminho compilado mas nunca executado: força o runtime de pânico do
/// core/std a entrar no binário (rust_begin_unwind permanece no .symtab).
#[allow(dead_code, unreachable_code)]
fn panic_anchor() -> u32 {
    if black_box(false) {
        panic!("inacessível por construção — âncora do contrato");
    }
    0
}

#[no_mangle]
pub extern "C" fn Java_dev_apktester_engine_engine09rust_probe_probe(
    _env: *mut core::ffi::c_void,
    _thiz: *mut core::ffi::c_void,
) -> i32 {
    checksum_inner(20261022) as i32
}

#[no_mangle]
pub extern "C" fn apktester_rust_version() -> *const u8 {
    ENGINE.as_ptr()
}
