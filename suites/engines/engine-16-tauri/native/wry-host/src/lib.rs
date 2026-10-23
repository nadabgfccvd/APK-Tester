//! engine-16 (Tier A, A4): cdylib que LINKA o crate wry real (mesmo nome
//! do artefato do contrato: libwry.so).

#[allow(unused)]
fn wry_anchor() -> i32 {
    // Type-level anchor: compila o backend android do wry.
    let _builder: Option<wry::WebViewBuilder> = None;
    let _webview: Option<wry::WebView> = None;
    20261022
}

#[no_mangle]
pub extern "C" fn apktester_wry_probe() -> i32 {
    wry_anchor()
}
