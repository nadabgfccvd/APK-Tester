;; module.wat — engine-31-hybrid (TST-14, Tier A, A4): módulo WASM real
;; compartilhado do APK híbrido (mesmo pipeline do engine-30).
(module
  (memory (export "hybrid_mem") 1)
  (func (export "hybrid_add") (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add)
  (data (i32.const 0) "apktester-wasm/engine-31-hybrid")
)
