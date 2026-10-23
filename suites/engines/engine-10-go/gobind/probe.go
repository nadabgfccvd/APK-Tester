// Package probe — engine-10 (Tier A, A4): pacote Go vinculada pelo
// gomobile bind (x/mobile pinado). O bind gera classes Java do bridge
// (go.Seq, go.Universe) + libgojni.so — os dois artefatos do contrato.
// O blank import de golang.org/x/mobile/bind é o padrão real dos apps
// gomobile: garante o require do módulo e o runtime do bridge no .so.
package probe

import _ "golang.org/x/mobile/bind"

// Probe devolve o checksum determinístico do engine (exposto ao Java pelo
// gomobile como `int Probe()`).
func Probe() int {
	const engine = "engine-10-go"
	const marker = "apktester-gomobile"
	h := 20261022
	for _, b := range []byte(engine) {
		h = 31*h + int(b)
	}
	for _, b := range []byte(marker) {
		h = 31*h + int(b)
	}
	return h
}
