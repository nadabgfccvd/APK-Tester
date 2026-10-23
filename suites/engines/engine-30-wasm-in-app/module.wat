;; module.wat — engine-30 (Tier A, A4): módulo WebAssembly REAL compilado
;; pelo wat2wasm (wabt 1.0.36). O host libwasmer.so (crate wasmer 7)
;; acompanha o APK como runtime embutido (contrato: assets/module.wasm +
;; lib/x86_64/libwasmer.so).
(module
  (memory (export "apktester_mem") 1)
  (func (export "apktester_add") (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)
  (func (export "apktester_checksum") (result i32)
    (i32.const 20261022))
  (data (i32.const 0) "apktester-wasm/engine-30")
)
