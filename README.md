# Footverse

MMO persistente de futebol concebido como **sistema de IA + economia + agentes**.
Construído em etapas, com arquitetura de engenharia de IA moderna (agent graph, tool calling, memory/RAG, eval, observability).

> A espinha dorsal técnica reaproveita o esqueleto do projeto **Football AI Pro**
> (orchestrator + agentes, tool registry, RAG/memória, harness, fallback, isolamento por tenant).

## Status: Fase 1 — MVP "Cartola 2.0" (em definição)

Loop jogável da Fase 1: **criar clube → comprar jogadores → escalar → pontuar → subir de divisão.**

## Documentos
- [DESIGN_DOC.md](DESIGN_DOC.md) — visão, escopo da Fase 1, entidades, princípio de arquitetura (motor determinístico vs camada de IA), economia FV$, stack e riscos.

### Specs (Fase 1)
| Spec | Título |
|------|--------|
| [SPEC-001](specs/SPEC-001-criar-clube.md) | Criação de clube |
| [SPEC-002](specs/SPEC-002-comprar-jogador.md) | Compra de jogador |
| [SPEC-003](specs/SPEC-003-escalacao.md) | Escalação |
| [SPEC-004](specs/SPEC-004-pontuacao.md) | Pontuação da rodada |
| [SPEC-005](specs/SPEC-005-jogador-valor-pontuacao.md) | Jogador: atributos, valor de mercado e pontuação |
| [SPEC-006](specs/SPEC-006-temporada-progressao.md) | Temporada e progressão de divisão |

> **Specs da Fase 1 completas.** O loop `criar → comprar → escalar → pontuar → subir` está integralmente especificado.

### Decisões da revisão (jun/2026)
- **Régua "milhões baixa":** jogador de Série D ~1–5M, craque ~20M; **orçamento inicial = 50M**.
- **Sem elenco inicial:** clube monta o time no **mercado barato** (não há squad gerado).
- **6 formações + posição fina:** modelo de 8 posições com tabela de multiset por formação (resolve a ambiguidade 4-3-3 × 4-2-3-1) — ver SPEC-003.
- **Pontuação em inteiro (centésimos)** e **seed derivada server-side** — garantem reprodutibilidade real e anti-cheat (SPEC-004).
- **Liga-sombra de NPCs determinísticos:** progressão de divisão por classificação real contra placares semeados (não são clubes-IA); base que Fase 2/4 preenchem com humanos e IA — ver SPEC-006.

## Código (motor determinístico — em construção)

```
footverse/
├── config.py              constantes calibráveis de economia/simulação (SPEC-005/006)
├── engine/
│   ├── fixedmath.py       exp/ln congelados (determinismo cross-platform)
│   ├── rng.py             PCG32 semeado por SHA-256 (reprodutível)
│   ├── distributions.py   Poisson (Knuth) + Normal (inversa de Acklam)
│   ├── valuation.py       valor de mercado FV$ (SPEC-005 §3)
│   ├── scoring.py         pontuação por jogador/rodada (SPEC-005 §4-5)
│   ├── market_gen.py      geração do mercado barato de Série D (SPEC-005 §6)
│   └── league.py          liga-sombra de NPCs + classificação (SPEC-006)
├── domain/
│   ├── positions.py       8 posições, setores, tabela de formações (SPEC-003)
│   ├── player.py          atributos + OVR por posição (SPEC-005 §2)
│   └── lineup.py          validação de escalação (SPEC-003)
├── state/
│   ├── models.py          Clube + lançamento de ledger (SPEC-001/002/006)
│   ├── store.py           store in-memory; ledger é o único caminho do saldo
│   ├── economy.py         criar clube + comprar jogador (SPEC-001/002)
│   └── season.py          temporada, progressão de divisão, forma (SPEC-006)
├── world.py               facade do loop (costura motor + estado)
├── api/
│   ├── app.py             FastAPI: rotas do loop + erros de domínio → HTTP
│   └── schemas.py         contratos Pydantic de entrada/saída
└── state/
    ├── repository.py      interface de repositório (Protocol)
    └── sqlstore.py        repositório SQL durável (SQLite/Postgres)
```

**Como rodar os testes (Harness):**
```bash
python -m pytest        # 131 testes — motor, loop e API
```

**Como subir a API:**
```bash
pip install -e ".[api]"
uvicorn footverse.api.app:app --reload    # docs em http://localhost:8000/docs
```
Endpoints do loop: `POST /clubs` · `POST /clubs/{id}/transfers` ·
`PUT /clubs/{id}/lineup` · `POST /clubs/{id}/rounds/{rodada_id}` ·
`POST /clubs/{id}/season/close`. Erros de domínio mapeiam para os status HTTP
das specs (409/402/404/403/400).

**Persistência:** sem `DATABASE_URL` o estado é in-memory; com ela, durável via
SQLAlchemy (`SqlStore`) — o ledger vira tabela e continua sendo a fonte de
verdade do saldo. O mesmo código vale para SQLite e Postgres:
```bash
export DATABASE_URL="sqlite:///footverse.db"            # dev (persiste em disco)
export DATABASE_URL="postgresql+psycopg://user:pw@host/footverse"   # produção
```
O loop completo da Fase 1 (`criar → comprar → escalar → pontuar → subir`) está
implementado e coberto por um teste **end-to-end determinístico**
([test_loop_e2e.py](tests/test_loop_e2e.py)). O maior risco técnico das specs —
reprodutibilidade cross-platform — é garantido pelos transcendentais congelados
e pelo PRNG semeado por SHA-256.

## Decisão fundadora
**O motor determinístico (economia, simulação, regras) é autoritativo e nunca depende de LLM.**
A camada de IA (Scout/Coach/Finance) apenas lê o estado e produz conselho/narrativa. Se a IA cair, o jogo continua jogável. Isto antecipa a Fase 4 (clubes autônomos), onde os agentes *propõem ações ao motor*, que valida e executa.

## Roadmap macro
1. **Cartola 2.0** (atual) · 2. Football Manager Social · 3. MMO Persistente ·
4. **Clubes Autônomos por IA** (diferencial de mercado) · 5. Economia Global · 6. MetaHumans + Unreal
