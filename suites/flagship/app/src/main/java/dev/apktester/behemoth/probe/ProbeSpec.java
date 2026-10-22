package dev.apktester.behemoth.probe;

/**
 * Especificacao imutavel de um probe do harness MaxProbe.
 *
 * Cada instante replica verbatim uma entrada de
 * contracts/flagship/api-probe-registry.json: o identificador estavel
 * (id), o modulo dono (module_id: CORE/UI/ST/NET/SYS/MEDIA/LANG), o dominio
 * do Apendice C (domain) e a descricao da API exercitada (api).
 */
public final class ProbeSpec {

    /** Identificador estavel do probe (ex.: "CORE-LC-001"). */
    public final String id;

    /** Modulo dono do probe (ex.: "CORE"). */
    public final String moduleId;

    /** Dominio do Apendice C coberto pelo probe (ex.: "lifecycle"). */
    public final String domain;

    /** Descricao da API exercitada, copiada do registry de contratos. */
    public final String api;

    public ProbeSpec(String id, String moduleId, String domain, String api) {
        this.id = id;
        this.moduleId = moduleId;
        this.domain = domain;
        this.api = api;
    }
}
