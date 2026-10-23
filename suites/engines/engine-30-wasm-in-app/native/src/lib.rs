//! engine-30 (Tier A, A4): cdylib que LINKA o runtime wasmer real.
//! A âncora de tipos força o depend a ser compilado/linkado; o módulo
//! .wasm do APK é validável pelo próprio wasmer em runtime.

#[allow(unused)]
fn wasmer_anchor() -> i32 {
    // Type-level anchor: compila a stack wasmer (engine + singlepass).
    let _store: Option<wasmer::Store> = None;
    let _engine: Option<wasmer::Engine> = None;
    20261022
}

#[no_mangle]
pub extern "C" fn apktester_wasmer_probe() -> i32 {
    wasmer_anchor()
}
