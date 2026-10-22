# Política de Segurança

## Versão suportada

| Versão | Suportada |
|---|---|
| 0.x (última release) | sim |
| versões anteriores de 0.x | apenas a mais recente recebe correções |
| < 0.1.0 | não |

Durante o ciclo 0.x (fases A0–A8), a política é: a **última** tag publicada é
a única linha de suporte.

## Como reportar uma vulnerabilidade

Use um canal **privado** — nunca abra issue pública com detalhes de
vulnerabilidade:

1. **Preferencial:** GitHub Security Advisories — aba *Security* do
   repositório → *Report a vulnerability*. Isso cria um canal privado
   direto com os mantenedores.
2. **Alternativa:** contato privado com o owner (`nadabgfccvd`) — os detalhes
   ficarão sob sigilo até a correção.

Não publique exploits, PoCs ou forks públicos antes da correção e do anúncio
coordenado.

## Escopo — o que este repositório é (e o que não é)

- Os fixtures **NÃO são malware**. São estressores de parser (ZIP/AXML/ARSc/
  DEX/ELF) e de superfície de manifest, criados para validar o comportamento
  do RustyDroid e de ferramentas de análise em cenários de borda.
- Strings de permissão inventadas existem **apenas** em
  `suites/parser-torture/unknown-perms`, para testar a *classificação* de
  permissões desconhecidas — nunca para enganar usuários.
- Permissões `signature`/`@hide` declaradas no flagship testam classificação,
  não instalabilidade.
- **Fora de escopo:** instalar os fixtures em dispositivos pessoais ou de
  produção, distribuí-los em lojas de aplicativos ou usá-los contra sistemas
  de terceiros. Teste apenas em ambientes controlados.
- Vulnerabilidades do próprio runtime devem ser reportadas no repositório do
  [RustyDroid](https://github.com/nadabgfccvd/RustyDroid), seguindo a política
  de segurança dele.

## Disclosure responsável — SLA

| Etapa | Prazo alvo |
|---|---|
| Acuse de recibo do reporte | até 72 horas |
| Triagem e atribuição de severidade | até 7 dias |
| Correção ou mitigação (crítico/alto) | até 30 dias |
| Correção ou mitigação (médio/baixo) | até 90 dias |
| Disclosure coordenado | após a correção ser publicada; no máximo 90 dias após o acordo com o relator |

Crédito ao relator é dado voluntariamente, com consentimento prévio.

## Regras adicionais

- Não execute testes de intrusão na infraestrutura de CI/CD do projeto.
- Não abra issues públicas ou divulgue o problema antes da correção.
- Dúvidas sobre o escopo deste documento: use os canais do
  [SUPPORT.md](SUPPORT.md) **sem** incluir detalhes técnicos sensíveis.
