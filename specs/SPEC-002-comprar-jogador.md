# SPEC-002 — Compra de Jogador

**Status:** Rascunho
**Camada:** Motor determinístico + Economia + Mercado
**Depende de:** SPEC-001 (clube existe com saldo)

---

## Objetivo
Permitir que um clube compre um jogador disponível no mercado, debitando o valor de mercado do saldo em FV$ e transferindo a posse do jogador.

## Input
```json
{
  "club_id": "club_123",
  "player_id": "player_789"
}
```

## Output
```json
{
  "transacao_id": "txn_555",
  "club_id": "club_123",
  "player_id": "player_789",
  "valor_fvs": 20000000,
  "saldo_anterior": 30000000,
  "saldo_final": 10000000,
  "status": "OK"
}
```

## Regras de negócio
1. O jogador precisa estar **disponível no mercado** (`clube_id == null`).
2. **Preço = valor de mercado determinístico** do jogador (ver SPEC-005 — fórmula de valor). Na Fase 1, o preço é o `valor_mercado_fvs` corrente do jogador. Na régua "milhões baixa", o mercado de Série D é populado por jogadores de **~1–5M** (craques até ~20M), de modo que o orçamento de 50M (SPEC-001) compra um elenco titular inteiro.
3. **Saldo suficiente:** `orcamento_fvs >= valor_fvs`.
4. **Atomicidade:** debitar saldo, marcar `jogador.clube_id = club_id`, registrar transação no ledger — tudo numa única transação de banco. Falha em qualquer passo → rollback completo.
5. **Ledger:** registra transação `TRANSFER_BUY` (sink) com `valor_fvs`.
6. **Limite de elenco (Fase 1):** máximo de `MAX_ELENCO = 30` jogadores por clube.

## Exemplo numérico (caso do roadmap)
- Pedro = FV$ 20.000.000 *(craque — topo da régua de Série D; um titular comum custaria ~3M)*
- Saldo do clube = FV$ 30.000.000 *(clube que já gastou parte dos 50M iniciais)*
- **Resultado esperado:** `saldo_final = 10.000.000`

## Validações / Erros
| Condição | Erro |
|----------|------|
| Clube inexistente | `404 CLUB_NOT_FOUND` |
| Jogador inexistente | `404 PLAYER_NOT_FOUND` |
| Jogador já pertence a um clube | `409 PLAYER_NOT_AVAILABLE` |
| Saldo insuficiente | `402 INSUFFICIENT_FUNDS` |
| Elenco cheio (30) | `409 SQUAD_FULL` |

## Invariantes (testáveis no Harness)
- `saldo_final == saldo_anterior - valor_fvs`.
- Após compra: `jogador.clube_id == club_id` e jogador some do mercado.
- **Ledger reconcilia com saldo:** soma de todas as transações do clube == `orcamento_fvs` atual (esta é a invariante auditável central).
- **Compra do mercado-NPC é sink:** o `valor_fvs` **sai de circulação** (não vai para outro clube na Fase 1). Não confundir com "conservação": o que se conserva é a identidade global `FV$ em circulação = Σ faucets − Σ sinks`, e a compra é um sink. (Venda entre clubes — que de fato conserva FV$ — só existe na Fase 2.)

## Fora de escopo
- Negociação/leilão, parcelamento, cláusulas, venda entre clubes humanos (Fase 2), agente Market autônomo (Fase 4).
