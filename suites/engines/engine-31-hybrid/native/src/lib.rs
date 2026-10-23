//! engine-31-hybrid (TST-14, Tier A, A4): cdylib Rust real, sem deps
//! externas. O APK híbrido carrega este .so + DEX Kotlin + bundle Hermes
//! + módulo WASM — os quatro marcadores num ÚNICO APK.

use std::hint::black_box;

const ENGINE: &str = "engine-31-hybrid";
const MARKER: &str = "apktester-rust-hybrid-tst14";

fn checksum_inner(seed: u32) -> u32 {
    let mut h = seed;
    for b in ENGINE.bytes().chain(MARKER.bytes()) {
        h = h.wrapping_mul(31).wrapping_add(b as u32);
    }
    h
}

/// âncora de pânico (mantém a machinery do core no ELF).
#[allow(dead_code, unreachable_code)]
fn panic_anchor() -> u32 {
    if black_box(false) {
        panic!("inacessível por construção — âncora TST-14");
    }
    0
}

#[no_mangle]
pub extern "C" fn Java_dev_apktester_engine_engine31hybrid_probe_probe(
    _env: *mut core::ffi::c_void,
    _thiz: *mut core::ffi::c_void,
) -> i32 {
    checksum_inner(20261022) as i32
}
