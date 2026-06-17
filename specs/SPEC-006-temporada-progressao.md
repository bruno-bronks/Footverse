# SPEC-006 — Temporada e Progressão de Divisão

**Status:** Rascunho
**Camada:** Motor determinístico (estrutura de competição)
**Depende de:** SPEC-004 (pontuação da rodada), SPEC-005 (geração de mundo/mercado) · **Fecha o loop:** `criar → comprar → escalar → pontuar → **subir**`

---

## Objetivo
Definir a **temporada** (conjunto de rodadas) e a **progressão entre divisões** (Série D → C → B → A) de forma determinística. Resolve o bloqueador estrutural da Fase 1: como o jogo é **single-player** (sem humanos — Fase 2 — nem clubes-IA — Fase 4), o clube humano não teria contra quem se classificar. A solução é uma **liga-sombra de NPCs determinísticos**.

> **NPCs ≠ clubes-IA.** Eles **não têm agentes, elenco nem decisões** — são apenas **placares determinísticos** por rodada, calibrados à força da divisão. Servem de "régua" para o humano subir/descer. Na Fase 2/4 esses slots passam a ser ocupados por humanos e clubes-IA reais; a tabela e a regra de acesso continuam as mesmas.

---

## 1. Estrutura da temporada

| Constante | Valor (default, calibrável) | Significado |
|-----------|------------------------------|-------------|
| `DIVISOES` | `[SERIE_A, SERIE_B, SERIE_C, SERIE_D]` | da mais alta à mais baixa |
| `CLUBES_POR_DIVISAO` | 20 | 1 humano + 19 NPCs-sombra (na divisão do humano) |
| `RODADAS_POR_TEMPORADA` | 38 | corrida de pontos (sem confronto direto — Fase 1) |
| `N_PROMOVIDOS` | 4 | sobem ao fim da temporada (exceto Série A) |
| `N_REBAIXADOS` | 4 | descem ao fim da temporada (exceto Série D) |

> A temporada é uma **corrida de pontos de fantasy** (estilo Cartola), não uma tabela de vitórias/empates — coerente com a SPEC-004, que pontua desempenho, não resultado de partida. `pontos_temporada = Σ pontos das rodadas disputadas`.

---

## 2. Liga-sombra de NPCs

Só a divisão **onde o humano está** precisa de NPCs (as outras divisões são abstração até o humano chegar nelas).

1. **Geração determinística:** os 19 NPCs da divisão do humano são derivados de `rng(SEASON_SECRET, divisao, temporada, "npc", idx)`. Mesma seed ⇒ mesma liga. NPCs são **efêmeros por temporada/divisão** — regenerados a cada temporada; só o **clube humano persiste** e se move entre divisões.
2. **Pontuação do NPC por rodada:**
   ```
   pontos_npc_centi = round_half_up( 100 × clamp(
       Normal(μ = MEDIA_PONTOS_NPC[divisao], σ = DESVIO_PONTOS_NPC),
       0, 200 )  via rng(SEASON_SECRET, divisao, temporada, npc_id, rodada) )
   ```
3. **Calibração (a chave do "sentir progressão"):**

   | Divisão | `MEDIA_PONTOS_NPC` (pts/rodada) |
   |---------|:-------------------------------:|
   | SERIE_D | 68 |
   | SERIE_C | 72 |
   | SERIE_B | 76 |
   | SERIE_A | 80 |

   `DESVIO_PONTOS_NPC = 18`.

   Um XI competente pontua ~77/rodada (SPEC-005: 11 × ~7). Em Série D (média NPC 68) ele fica na parte de cima e **sobe**. A cada divisão a régua sobe (+4/divisão): o **mesmo elenco fica relativamente mais fraco** e o jogador precisa **reforçar o time para continuar subindo** — é o motor de engajamento do loop econômico.

---

## 3. Classificação e desempate

Ao fim das `RODADAS_POR_TEMPORADA`, os 20 clubes (humano + 19 NPCs) são ordenados:

1. `pontos_temporada` **desc**;
2. empate → **maior pontuação numa única rodada** desc;
3. empate → `hash(SEASON_SECRET + club_id)` **asc** (desempate determinístico final — nunca há empate real).

```json
{
  "divisao": "SERIE_D",
  "temporada": 1,
  "tabela": [
    {"pos": 1, "club_id": "npc_d_07", "tipo": "NPC",   "pontos_temporada": 2698.5},
    {"pos": 2, "club_id": "club_123", "tipo": "HUMANO", "pontos_temporada": 2671.0},
    {"pos": 3, "club_id": "npc_d_12", "tipo": "NPC",   "pontos_temporada": 2655.5}
  ]
}
```

---

## 4. Encerramento de temporada e progressão

Operação **`encerrar_temporada(divisao, temporada)`** — só roda quando `rodada_atual == RODADAS_POR_TEMPORADA`.

1. Monta a classificação (§3).
2. **Promoção:** as `N_PROMOVIDOS` primeiras posições sobem uma divisão. **Exceção Série A:** não há acima — a 1ª posição é **campeão** (faucet de premiação de título, ver SPEC economia).
3. **Rebaixamento:** as `N_REBAIXADOS` últimas descem uma divisão. **Exceção Série D:** não há abaixo — ninguém é rebaixado (apenas não sobe).
4. **Efeito no humano:** atualiza `clube.divisao` conforme sua posição final. (Os NPCs são descartados; não migram.)
5. **Premiação (faucets):** crédito por posição final e por acesso/título, registrado no **ledger** (nunca update solto de saldo). Valores → módulo de economia.
6. **Rollover:** `temporada += 1`; `pontos_temporada = 0`; `rodada_atual = 0`; nova liga-sombra (§2) é gerada para a divisão atual do humano.
7. **Refresh de mundo:** o mercado é **regenerado** para a nova temporada (SPEC-005 §6); a `forma` de cada jogador do elenco é atualizada (§5). Atributos, idade e OVR permanecem **estáticos na Fase 1** (evolução/envelhecimento = fora de escopo).
8. **Idempotência:** encerrar a mesma temporada duas vezes **não** promove/credita em dobro (guardado por `status = ENCERRADA`).

```json
{
  "temporada": 1,
  "divisao_anterior": "SERIE_D",
  "posicao_final": 2,
  "resultado": "PROMOVIDO",
  "divisao_nova": "SERIE_C",
  "premiacao_fvs": 8000000,
  "status": "ENCERRADA"
}
```

---

## 5. Atualização de forma (gancho de temporada)

A SPEC-005 §1 deixou a `forma` como dinâmica "só por gancho de temporada" — definido aqui:
```
forma_nova = round( clamp( Normal(μ=65, σ=12), 30, 95 )
                    via rng(SEASON_SECRET, club_id, player_id, temporada) )
```
Afeta apenas a **pontuação** (SPEC-005 §4.1); **não** afeta o `valor_fvs` (que depende só de OVR + idade). Determinística por temporada.

---

## 6. Validações / Erros

| Condição | Erro |
|----------|------|
| Encerrar temporada antes da última rodada | `409 SEASON_NOT_FINISHED` |
| Temporada já encerrada | `409 SEASON_ALREADY_CLOSED` |
| Divisão inválida | `400 INVALID_DIVISION` |

---

## 7. Determinismo
- Toda a liga-sombra, pontuação NPC, desempate e atualização de forma derivam de `SEASON_SECRET` + chaves estáveis (divisão, temporada, ids). **Mesma seed ⇒ mesma temporada inteira** reproduzível.
- A amostragem `Normal` usa a **mesma implementação congelada** exigida na SPEC-005 §8 (Ziggurat/inversa tabelada — nada de libm), pelo mesmo risco cross-platform.
- Pontos sempre em **inteiro (centésimos)**; nenhuma comparação de classificação usa `float`.

---

## 8. Invariantes (testáveis no Harness)
- **Reprodutibilidade da temporada:** mesma `SEASON_SECRET` + mesmas escalações do humano ⇒ tabela final idêntica.
- **Conservação de tamanho:** toda divisão (com humano) tem exatamente `CLUBES_POR_DIVISAO` clubes durante a temporada.
- **Bordas de progressão:** ninguém sobe da Série A; ninguém é rebaixado da Série D.
- **Sem empate real:** o desempate de 3 níveis (§3) produz ordem total estrita.
- **Idempotência de encerramento:** `encerrar_temporada` aplicado 2× não altera `divisao` nem credita prêmio em dobro.
- **Movimento monotônico do humano:** posição ≤ `N_PROMOVIDOS` ⇒ divisão sobe um nível (ou campeão na A); posição > `CLUBES_POR_DIVISAO − N_REBAIXADOS` ⇒ desce um nível (ou permanece na D).
- **Premiação rastreável:** todo crédito de fim de temporada existe como transação no ledger (casa com a invariante de economia da SPEC-002).

---

## 9. Fora de escopo
- Confronto direto / tabela de vitórias-empates-derrotas (Fase 2 — quando houver adversários reais por rodada).
- NPCs com elenco, decisões ou mercado próprios (isso é **clube-IA**, Fase 4).
- Copas, mata-mata, rebaixamento/acesso com playoff (Fase 2+).
- Envelhecimento de jogadores, evolução de atributos, aposentadoria (Fase 2+).
- Calendário com datas reais / tempo persistente contínuo (Fase 3).
