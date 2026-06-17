# SPEC-001 — Criação de Clube

**Status:** Rascunho
**Camada:** Motor determinístico + Economia
**Depende de:** —

---

## Objetivo
Permitir que um usuário crie um clube, recebendo orçamento inicial em FV$ e ingressando na Série D.

## Input
```json
{
  "user_id": "user_abc",
  "nome": "Império FC",
  "escudo": "https://cdn.footverse/escudos/imperio.svg",
  "cores": ["#000000", "#D4AF37"]
}
```

## Output
```json
{
  "id": "club_123",
  "user_id": "user_abc",
  "nome": "Império FC",
  "escudo": "https://cdn.footverse/escudos/imperio.svg",
  "cores": ["#000000", "#D4AF37"],
  "orcamento_fvs": 50000000,
  "divisao": "Serie D",
  "pontos_temporada": 0,
  "criado_em": "2026-06-15T19:30:00Z"
}
```

## Regras de negócio
1. **Orçamento inicial fixo:** `ORCAMENTO_INICIAL_FVS = 50_000_000` (constante calibrável de economia). Calibrado para a **régua "milhões baixa"**: jogador de Série D vale ~1–5M (craque até ~20M), então 50M compra um elenco titular (11 × ~3M ≈ 33M) com folga para reservas.
2. **Sem elenco inicial:** o clube nasce com **0 jogadores**. Ele monta o time comprando no **mercado barato de Série D** (ver SPEC-002), que é populado por geração determinística (ver SPEC-005). O loop só fecha se o mercado tiver jogadores baratos suficientes — isto é uma **pré-condição de mundo**, não responsabilidade desta spec.
3. **Divisão inicial:** sempre `Serie D`. Representada por **enum sem acento** no código (`SERIE_D`); o rótulo com acento ("Série D") é só de UI.
4. **Pontuação inicial:** `0`.
5. **Nome do clube:** 3–40 caracteres. Como na Fase 1 vale **1 clube por usuário**, a unicidade de nome por usuário é automática (não é regra extra).
6. **Cores:** 1–3 cores em formato hex válido.
7. **Escudo:** URL opcional; se ausente, gera placeholder determinístico a partir do nome.
8. **Ledger:** a concessão do orçamento inicial é registrada como transação `INITIAL_GRANT` (faucet), nunca um update solto de saldo.

## Validações / Erros
| Condição | Erro |
|----------|------|
| Usuário já possui clube | `409 CLUB_ALREADY_EXISTS` |
| Nome fora de 3–40 chars | `400 INVALID_NAME` |
| Cor em formato inválido | `400 INVALID_COLOR` |
| >3 cores | `400 TOO_MANY_COLORS` |

## Invariantes (testáveis no Harness)
- Após criação: `orcamento_fvs == ORCAMENTO_INICIAL_FVS`.
- Existe exatamente 1 transação `INITIAL_GRANT` no ledger igual ao orçamento.
- `divisao == "Serie D"` e `pontos_temporada == 0`.

## Fora de escopo
- Múltiplos clubes por usuário, patrocínio inicial, escolha de estádio (Fase 2+).
