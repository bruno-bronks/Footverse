# SPEC-003 — Escalação

**Status:** Rascunho
**Camada:** Motor determinístico + Validação de regras
**Depende de:** SPEC-001, SPEC-002 (clube com jogadores)

---

## Objetivo
Permitir que o clube defina uma escalação válida (formação + 11 titulares) que será usada para gerar a pontuação da rodada (SPEC-004).

## Input
```json
{
  "club_id": "club_123",
  "formacao": "4-3-3",
  "titulares": [
    {"player_id": "gk_01",  "posicao": "GOL"},
    {"player_id": "def_01", "posicao": "ZAG"},
    {"player_id": "def_02", "posicao": "ZAG"},
    {"player_id": "def_03", "posicao": "LAT"},
    {"player_id": "def_04", "posicao": "LAT"},
    {"player_id": "mid_01", "posicao": "VOL"},
    {"player_id": "mid_02", "posicao": "MEI"},
    {"player_id": "mid_03", "posicao": "MEI"},
    {"player_id": "fwd_01", "posicao": "EXT"},
    {"player_id": "fwd_02", "posicao": "EXT"},
    {"player_id": "fwd_03", "posicao": "ATA"}
  ],
  "reservas": ["res_01", "res_02"]
}
```

## Output
```json
{
  "club_id": "club_123",
  "formacao": "4-3-3",
  "valida": true,
  "titulares": 11,
  "atualizada_em": "2026-06-15T19:45:00Z"
}
```

## Modelo de posição (Fase 1 — posição fina)
Oito posições, agrupadas em quatro setores. As **posições finas** definem o formato da formação; o **setor** define a elegibilidade do jogador.

| Setor | Posições finas |
|-------|----------------|
| GOL | `GOL` |
| DEF | `ZAG` (zagueiro), `LAT` (lateral/ala) |
| MEI | `VOL` (volante), `MEI` (meia central), `MEIA` (meia ofensivo) |
| ATA | `EXT` (extremo/ponta), `ATA` (centroavante) |

## Tabela de formações suportadas
A escalação é válida se o **multiset de posições dos 11 titulares for exatamente igual** ao da formação. (O rótulo "X-Y-Z" é convenção: alas/wing-backs são modelados como `LAT`; o que o motor valida é o multiset abaixo — é o que torna a regra determinística e testável.)

| Formação | GOL | ZAG | LAT | VOL | MEI | MEIA | EXT | ATA |
|----------|:---:|:---:|:---:|:---:|:---:|:----:|:---:|:---:|
| 4-3-3    | 1 | 2 | 2 | 1 | 2 | 0 | 2 | 1 |
| 4-4-2    | 1 | 2 | 2 | 2 | 2 | 0 | 0 | 2 |
| 3-5-2    | 1 | 3 | 2 | 2 | 0 | 1 | 0 | 2 |
| 4-2-3-1  | 1 | 2 | 2 | 2 | 0 | 3 | 0 | 1 |
| 5-3-2    | 1 | 3 | 2 | 1 | 2 | 0 | 0 | 2 |
| 3-4-3    | 1 | 3 | 2 | 1 | 1 | 0 | 2 | 1 |

> Os seis multisets são **distintos entre si** (ex.: 4-3-3 vs 4-2-3-1 diferem em `VOL`/`MEI`/`MEIA`), o que resolve a ambiguidade que existia no modelo de setor grosseiro.

## Regras de negócio
1. **Exatamente 11 titulares.**
2. **Exatamente 1 goleiro (GOL).**
3. **Formação válida:** `formacao` pertence à tabela acima **e** o multiset de posições dos titulares é idêntico ao da formação.
4. **Posse:** todos os jogadores escalados (titulares e reservas) pertencem ao `club_id`.
5. **Sem duplicatas:** um jogador não pode aparecer duas vezes.
6. **Compatibilidade de posição (por setor):** cada jogador tem uma `posicao_natural`; na Fase 1 ele é elegível para qualquer posição fina **do mesmo setor** (ex.: um `VOL` natural pode ocupar slot `MEI`/`MEIA`). Refinamento por posição fina e penalidade de "fora de posição" → spec futura.
7. A escalação substitui a anterior do clube (uma escalação "ativa" por clube).

## Validações / Erros
| Condição | Erro |
|----------|------|
| ≠ 11 titulares | `400 INVALID_LINEUP_SIZE` |
| ≠ 1 goleiro | `400 INVALID_GOALKEEPER_COUNT` |
| Formação não suportada / contagem não bate | `400 INVALID_FORMATION` |
| Jogador não pertence ao clube | `403 PLAYER_NOT_OWNED` |
| Jogador duplicado | `400 DUPLICATE_PLAYER` |
| Posição incompatível | `400 INVALID_POSITION` |

## Invariantes (testáveis no Harness)
- Escalação sem goleiro → **erro** (caso explícito do roadmap).
- Toda escalação `valida == true` tem exatamente 11 titulares e 1 GOL.
- Nenhum `player_id` da escalação tem `clube_id != club_id`.

## Fora de escopo
- Esquemas táticos avançados, instruções de jogo, marcação individual (Fase 2+).
