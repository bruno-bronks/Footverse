# SPEC-004 — Pontuação da Rodada

**Status:** Rascunho
**Camada:** Motor determinístico + Simulação
**Depende de:** SPEC-003 (escalação válida)

---

## Objetivo
Calcular, de forma **determinística e reprodutível**, a pontuação de um clube em uma rodada, a partir do desempenho simulado dos jogadores escalados. É o coração da simulação da Fase 1.

## Input
```json
{
  "club_id": "club_123",
  "rodada_id": "rod_2026_05"
}
```

> **A seed NÃO vem do cliente.** Ela é derivada **server-side** a partir de um segredo de temporada: `seed = hash(SEASON_SECRET + club_id + rodada_id)`. Se o cliente pudesse enviar a seed, poderia re-rolar até obter o resultado que quer — o que destruiria o anti-cheat prometido no Design Doc §4.3.

## Output
```json
{
  "club_id": "club_123",
  "rodada_id": "rod_2026_05",
  "pontos": 78.5,
  "breakdown": [
    {"player_id": "fwd_01", "posicao": "ATA", "pontos": 19.8,
     "eventos": {"gols": 1, "assistencias": 1, "nota": 8.4}},
    {"player_id": "gk_01", "posicao": "GOL", "pontos": 13.0,
     "eventos": {"defesas": 4, "gols_sofridos": 0, "nota": 7.0}}
  ],
  "gerado_em": "2026-06-15T20:00:00Z"
}
```

## Regras de negócio
1. **Determinismo total:** dada a mesma seed (derivada server-side), a mesma escalação e os mesmos atributos de jogadores, o resultado é **idêntico**.
1b. **Aritmética sem float:** pontos são **inteiros em centésimos** (`pontos_centi`, ex.: `78.50` → `7850`); a exibição `78.5` é só de apresentação. Toda soma/arredondamento é feita em inteiro com regra de arredondamento fixa (ex.: half-up no último passo). Isso é o que torna a invariante "byte-a-byte idêntico" verdadeira na prática — somas de `float` dependem de ordem/plataforma e quebrariam a reprodutibilidade.
2. **Pontuação por jogador** = função determinística de:
   - atributos do jogador (ataque/defesa/etc. conforme posição),
   - forma atual,
   - ruído pseudoaleatório semeado (variabilidade da partida),
   - papel na formação.
   **Fórmula autoritativa → SPEC-005 §4** (esta spec só orquestra a chamada e a soma; os números do breakdown acima são ilustrativos e seguem a escala da SPEC-005).
3. **Pontuação do clube** = soma (ou média ponderada) das pontuações dos 11 titulares. Reservas não pontuam na Fase 1.
4. **Sem LLM no caminho:** a pontuação é 100% motor determinístico. O agente Coach pode *comentar* o resultado depois, mas não o altera.
5. **Idempotência:** recalcular a mesma rodada para o mesmo clube retorna o mesmo resultado (não acumula).
6. **Efeito colateral:** os pontos da rodada somam em `clube.pontos_temporada` (transação registrada, atualização idempotente por `rodada_id`).

## Progressão de divisão (gatilho)
- Ao fim da temporada (N rodadas), os clubes são ordenados por `pontos_temporada`.
- Os melhores **sobem** de divisão (Serie D→C→B→A), os piores **descem** (quando houver divisão abaixo).
- Regras de corte (nº de promovidos/rebaixados) → constante de configuração da temporada.
- *Fase 1:* progressão pode ser simplificada (ex.: atingir X pontos garante acesso), detalhada em spec de temporada.

## Validações / Erros
| Condição | Erro |
|----------|------|
| Clube sem escalação válida ativa | `409 NO_VALID_LINEUP` |
| Rodada inexistente | `404 ROUND_NOT_FOUND` |

## Invariantes (testáveis no Harness)
- **Reprodutibilidade:** mesma seed → resultado byte-a-byte idêntico (teste obrigatório).
- `pontos == soma(breakdown[*].pontos)` (consistência interna).
- Recalcular a rodada não altera `pontos_temporada` além da primeira aplicação (idempotência).

## Fora de escopo
- Simulação minuto a minuto, eventos de vídeo, lesões em partida (Fase 2+), confronto direto entre dois clubes humanos (Fase 2).
