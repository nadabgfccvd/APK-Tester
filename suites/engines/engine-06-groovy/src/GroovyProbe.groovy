package dev.apktester.engine.engine06groovy.probe

/**
 * Probe Groovy do engine-06 (Tier A, A4): compilada pelo groovyc 3.0.21;
 * o runtime org.codehaus.groovy (jar pinado do distribuição Apache) entra
 * no MESMO DEX pelo d8 — página real do runtime no contrato de detecção.
 */
class GroovyProbe {
    static final String MARKER = 'org.codehaus.groovy'
    static final String ENGINE = 'engine-06-groovy'
    static final int SEED = 20261022

    /** usa metaobject protocol real ( ExpandoMetaClass / categories ) */
    String probe() {
        def list = [1, 2, 3, 4]
        def closure = { int x -> x * 31 + SEED % 7 }
        def total = list.collect(closure).sum()
        "groovy:${ENGINE}:${total}:${MARKER.length()}"
    }

    int checksum() {
        def result = probe()
        int h = SEED
        for (char c : result.chars) {
            h = 31 * h + c
        }
        h
    }
}
