# Fase 6 — Plano de Integração com Unreal Engine + MetaHumans

**Status:** plano de arquitetura, não implementação. Nenhum código Unreal existe ou é criado por este documento.

## 0. Por que isto é um documento e não código

O Footverse hoje é um backend Python (FastAPI) + frontend Vite/React. A Fase 6 do
DESIGN_DOC ("MetaHumans + Unreal — camada visual 3D") pede um motor de jogo 3D
inteiramente separado: projeto Unreal Engine (C++/Blueprints), avatares gerados via
MetaHuman Creator (serviço cloud da Epic), pipeline de animação/render. Isso roda em
outro repositório, outra linguagem, outra toolchain — não há código C++/Unreal para
escrever *dentro* deste projeto. O que este projeto **pode** e **deve** fazer é expor uma
API estável e bem definida para que um cliente Unreal (futuro, separado) consuma.

Este documento descreve esse contrato.

## 1. Arquitetura proposta

```
┌────────────────────────┐        REST + SSE (HTTPS)        ┌───────────────────────────┐
│  Footverse API (este    │ ───────────────────────────────▶ │  Cliente Unreal Engine     │
│  repo: FastAPI/Python)  │ ◀─────────────────────────────── │  (repositório separado)    │
│                         │      ações via REST (Bearer)      │                            │
│  - Motor determinístico │                                   │  - Renderiza estádio,      │
│  - Economia (ledger)    │                                   │    avatares MetaHuman,     │
│  - World.tick()         │                                   │    animações de partida    │
│  - Agentes IA            │                                   │  - Envia ações do jogador  │
└────────────────────────┘                                   └───────────────────────────┘
```

O Footverse continua sendo a **única fonte de verdade** (princípio do DESIGN_DOC §4
se estende aqui: o motor determinístico nunca cede autoridade ao cliente 3D). O Unreal
é puramente uma camada de apresentação — ele lê estado e envia *intents* (comprar,
escalar, etc.) pelos mesmos endpoints que o frontend web já usa.

## 2. O que a API já expõe (suficiente para a maior parte da UI 3D)

Sem nenhuma mudança, um cliente Unreal já pode:

- Autenticar (`POST /auth/register`, Bearer token) — [auth.py](footverse/auth.py)
- Ler clube, elenco, escalação, temporada (`GET /clubs/{id}`, `/squad`, `/lineup`, `/season`)
- Ler mercado (NPC + P2P) e classificação (`GET /market`, `GET /divisions/{div}/standings`)
- Executar ações (`POST /clubs/{id}/transfers`, `PUT /clubs/{id}/lineup`, etc.)
- Assinar eventos ao vivo via SSE (`GET /clubs/{id}/events`) — rodada pontuada,
  temporada encerrada ([app.py](footverse/api/app.py))

Para um "lobby 3D" (escolher clube, ver elenco como avatares parados, ver tabela de
classificação, comprar jogadores num mercado navegável) isso já é suficiente.

## 3. A lacuna real: não há *timeline* de partida

`score_round()` em [scoring.py](footverse/engine/scoring.py:128-164) produz um
**box score agregado por jogador** (gols, assistências, defesas, nota) para a rodada
inteira — não uma sequência cronológica de eventos. Não existe "minuto 23, gol de X",
nem um adversário modelado como time real (a defesa rival é só um escalar de força,
`TeamDefense` em scoring.py:91-124).

Isso significa: **hoje não há dado suficiente para animar uma partida jogada minuto a
minuto**. Um visualizador 3D realista (jogadores correndo, bola, lances) precisa de uma
dessas duas mudanças, que ainda não foram implementadas:

| Opção | Descrição | Esforço |
|---|---|---|
| **A. Highlight reel sintético** | Pegar o box score existente (N gols, M defesas) e distribuir esses eventos em timestamps pseudoaleatórios determinísticos (mesma seed) dentro de 90min simulados. O Unreal anima só os eventos discretos (gol no minuto X), sem simular o jogo todo. | Baixo — só precisa de uma função nova que converte `RoundScore.breakdown` em `list[MatchEvent(minuto, tipo, player_id)]`, determinística por seed. |
| **B. Simulação minuto-a-minuto real** | Reescrever o motor para simular posse de bola, ataques, contra-ataques entre os dois times reais (não só um escalar de força do adversário). Mudança grande no `engine/scoring.py` e em todo o conceito de "rodada". | Alto — toca o núcleo determinístico testado nas specs 004/005; precisa de novas specs formais. |

**Recomendação**: se/quando a Fase 6 for de fato implementada, começar pela Opção A
(highlight reel). Ela não exige tocar no motor de pontuação validado — só adiciona uma
camada de apresentação determinística por cima do `RoundScore` já existente.

## 4. Endpoint novo recomendado (ainda não implementado)

```
GET /clubs/{club_id}/rounds/{rodada_id}/timeline
```
Retornaria a "Opção A" acima: uma lista ordenada de eventos com minuto sintético,
derivados deterministicamente do `RoundScore.breakdown` já persistido/calculável.
Não requer mudança no motor — é uma view nova sobre dado que já existe.

```json
{
  "rodada_id": "auto_T1_R5",
  "eventos": [
    {"minuto": 12, "tipo": "GOL", "player_id": "mkt_3", "slot": "ATA"},
    {"minuto": 34, "tipo": "DEFESA", "player_id": "mkt_1", "slot": "GOL"},
    {"minuto": 67, "tipo": "GOL_SOFRIDO", "player_id": "mkt_1", "slot": "GOL"}
  ]
}
```

## 5. Mapeamento de avatares MetaHuman

Jogadores no Footverse são gerados proceduralmente (`generate_market` em
[market_gen.py](footverse/engine/market_gen.py)) com atributos numéricos, sem identidade
visual. Não há "rosto" de jogador no modelo de dados hoje. Duas abordagens para o Unreal:

1. **Pool de MetaHumans genéricos**: gerar N avatares MetaHuman variados (Epic permite
   criar/exportar um conjunto fixo) e mapear `player_id → metahuman_id` de forma
   determinística (hash do `player_id` mod N) — nenhum dado novo precisa ser persistido
   no Footverse, o mapeamento é puramente client-side no Unreal.
2. **Campo opcional de aparência**: se o produto quiser avatares estáveis e
   "donos" (ex.: o craque do time tem sempre a mesma cara), adicionar um campo
   `aparencia_seed: str` ao `Player` (domain/player.py) — derivado deterministicamente
   do `player_id`, sem custo de armazenamento extra (não é um campo arbitrário, é
   calculável a qualquer momento a partir do ID já existente).

Recomendação: começar com (1) — zero mudança de schema, totalmente reversível.

## 6. Autenticação do cliente Unreal

Reaproveitar o esquema Bearer já implementado ([auth.py](footverse/auth.py),
SPEC implícita da Fase 2): o jogador registra-se uma vez (`POST /auth/register`),
o cliente Unreal guarda a API key localmente (equivalente ao `localStorage` do
frontend web, mas em `SaveGame` do Unreal) e manda `Authorization: Bearer <key>` nas
ações de escrita. Nenhuma mudança de backend necessária.

## 7. Eventos em tempo real

O endpoint SSE `GET /clubs/{id}/events` já publica `TickEvent` (rodada pontuada,
temporada encerrada) — ver [world.py](footverse/world.py) `TickEvent`/`TickResult` e
`_publish_tick_events` em [app.py](footverse/api/app.py). Um cliente Unreal pode
consumir o mesmo stream SSE (qualquer engine com HTTP client consegue ler
`text/event-stream`) para saber quando puxar a timeline da rodada nova e disparar a
animação. Não é necessário migrar para WebSocket — SSE já cobre o caso de uso
(servidor → cliente, unidirecional, eventos esparsos).

## 8. Roteiro sugerido dentro da Fase 6 (caso seja retomada)

1. **6.1 — Highlight reel**: endpoint `timeline` (seção 4) + testes de determinismo
   (mesma seed → mesma sequência de eventos). Trabalho 100% neste repositório.
2. **6.2 — Protótipo Unreal mínimo**: projeto Unreal separado, lobby simples (login,
   listar clube/elenco como UI 2D dentro do Unreal), sem avatares 3D ainda. Valida o
   contrato de API end-to-end.
3. **6.3 — Avatares MetaHuman genéricos**: pool fixo de avatares (seção 5, opção 1),
   jogadores parados em campo representando o XI.
4. **6.4 — Animação de eventos da timeline**: consumir `timeline` + SSE, animar gols/
   defesas nos minutos sintéticos.
5. **6.5+ — Simulação real (Opção B da seção 3)**: só se o produto validar que vale o
   custo de reescrever o motor de partida.

## 9. Não-metas explícitas

- Este documento **não** especifica engine version, plugins Unreal, ou pipeline de
  build/deploy do lado Unreal — isso pertence ao repositório separado, quando existir.
- Não há intenção de mover lógica de jogo (economia, pontuação, validação) para o
  cliente Unreal. O princípio do DESIGN_DOC §4 (motor determinístico autoritativo,
  server-side) vale também para a camada 3D: Unreal renderiza e envia intents, nunca
  decide resultado.
