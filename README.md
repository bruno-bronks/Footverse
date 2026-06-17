# Footverse

MMO persistente de futebol concebido como **sistema de IA + economia + agentes**.
Construído em etapas, com arquitetura de engenharia de IA moderna (agent graph, tool calling, memory/RAG, eval, observability).

> A espinha dorsal técnica reaproveita o esqueleto do projeto **Football AI Pro**
> (orchestrator + agentes, tool registry, RAG/memória, harness, fallback, isolamento por tenant).

## Status: Fases 1-4 completas

Loop jogável: **criar clube → comprar jogadores → escalar → pontuar → encerrar temporada → subir/cair de divisão.**
Multiplayer assíncrono, relógio de mundo e clubes autônomos de IA já implementados.

| Fase | Nome | Status |
|------|------|--------|
| 1 | Cartola 2.0 (motor determinístico) | ✅ completa |
| 2 | Football Manager Social (auth, mercado P2P, standings) | ✅ completa |
| 3 | MMO Persistente (relógio de mundo, SSE) | ✅ completa |
| 4 | Clubes Autônomos por IA | ✅ completa |
| 5 | Economia Global | adiada — sem spec, sem sinal real de escala ainda |
| 6 | MetaHumans + Unreal | documentada, não implementada — ver [PHASE6_UNREAL_INTEGRATION.md](PHASE6_UNREAL_INTEGRATION.md) |

## Documentos
- [DESIGN_DOC.md](DESIGN_DOC.md) — visão, escopo da Fase 1, entidades, princípio de arquitetura (motor determinístico vs camada de IA), economia FV$, stack e riscos.
- [PHASE6_UNREAL_INTEGRATION.md](PHASE6_UNREAL_INTEGRATION.md) — plano de integração com um futuro cliente Unreal/MetaHumans (sem código Unreal neste repo).

### Specs (Fase 1)
| Spec | Título |
|------|--------|
| [SPEC-001](specs/SPEC-001-criar-clube.md) | Criação de clube |
| [SPEC-002](specs/SPEC-002-comprar-jogador.md) | Compra de jogador |
| [SPEC-003](specs/SPEC-003-escalacao.md) | Escalação |
| [SPEC-004](specs/SPEC-004-pontuacao.md) | Pontuação da rodada |
| [SPEC-005](specs/SPEC-005-jogador-valor-pontuacao.md) | Jogador: atributos, valor de mercado e pontuação |
| [SPEC-006](specs/SPEC-006-temporada-progressao.md) | Temporada e progressão de divisão |

### Decisões de design
- **Régua "milhões baixa":** jogador de Série D ~1–5M, craque ~20M; **orçamento inicial = 50M**.
- **Sem elenco inicial:** clube monta o time no **mercado barato** (não há squad gerado).
- **6 formações + posição fina:** modelo de 8 posições com tabela de multiset por formação — ver SPEC-003.
- **Pontuação em inteiro (centésimos)** e **seed derivada server-side** — garantem reprodutibilidade real e anti-cheat (SPEC-004).
- **Mercado P2P (Fase 2):** clubes humanos podem listar/vender jogadores entre si; FV$ é conservado na transação (não é sink, diferente da compra do mercado NPC).
- **Relógio de mundo (Fase 3):** rodadas avançam automaticamente em tempo real (`ROUND_DURATION_SECONDS`, padrão 1 dia), via loop de fundo no FastAPI; também acionável manualmente via `POST /admin/tick`.
- **Clubes de IA (Fase 4):** `ClubManager` toma ações reais (compra, venda, escalação) através das mesmas tools determinísticas que a API expõe a humanos — nunca escreve estado direto. Se a IA falhar, o clube só não age naquela rodada.

## Código

```
footverse/
├── config.py              constantes calibráveis de economia/simulação
├── auth.py                geração/validação de API key (SHA-256)
├── world.py               facade único: loop, mercado P2P, relógio de mundo, IA autônoma
├── engine/
│   ├── fixedmath.py       exp/ln congelados (determinismo cross-platform)
│   ├── rng.py             PCG32 semeado por SHA-256 (reprodutível)
│   ├── distributions.py   Poisson (Knuth) + Normal (inversa de Acklam)
│   ├── valuation.py       valor de mercado FV$
│   ├── scoring.py         pontuação por jogador/rodada
│   ├── market_gen.py      geração do mercado barato
│   └── league.py          liga-sombra de NPCs + classificação
├── domain/
│   ├── positions.py       8 posições, setores, tabela de formações
│   ├── player.py          atributos + OVR por posição
│   └── lineup.py          validação de escalação
├── state/
│   ├── models.py          Clube, ledger, Listing (P2P), ApiKey
│   ├── store.py           store in-memory; ledger é o único caminho do saldo
│   ├── sqlstore.py        repositório SQL durável (SQLite/Postgres)
│   ├── economy.py         criar clube, comprar/vender jogador (NPC + P2P)
│   └── season.py          temporada, progressão de divisão, forma
├── agents/
│   ├── tools.py           tools read-only (Advisor: Scout/Coach/Finance)
│   ├── manager_tools.py   tools de ação (ClubManager: compra/venda/escalação reais)
│   ├── advisor.py         agentes assistivos via LangGraph + OpenAI
│   ├── manager.py         ClubManager — clube autônomo de IA (Fase 4)
│   └── memory.py          Memory/RAG por clube via Chroma
├── api/
│   ├── app.py             FastAPI: loop + auth + P2P + relógio + admin + SSE
│   └── schemas.py         contratos Pydantic de entrada/saída
└── observability.py       JSON logging, RequestLogMiddleware, AgentLogger

frontend/                  Vite + React SPA (auth, mercado, escalação, classificação, SSE)
```

## Como rodar

**Testes:**
```bash
pip install -e ".[api,agents,dev]"
python -m pytest --ignore=tests/test_memory.py   # 232 testes — motor, loop, API, agentes
python -m pytest tests/test_memory.py             # separado: baixa modelo ONNX na 1ª vez
```

**API:**
```bash
uvicorn footverse.api.app:app --reload    # docs em http://localhost:8000/docs
```
⚠️ o target é `footverse.api.app:app` (módulo `app.py` dentro do pacote `api`), não
`footverse.api:app` — o `__init__.py` só exporta `create_app`, não uma instância `app`.

**Frontend:**
```bash
cd frontend && npm install && npm run dev   # http://localhost:5173, proxy pra API na 8000
```

**Docker:** `docker compose up` sobe a API (`Dockerfile` + `docker-compose.yml` na raiz).
Variáveis de ambiente documentadas em [.env.example](.env.example).

**Agentes de IA (opcional):** defina `OPENAI_API_KEY` para ativar Scout/Coach/Finance
(`POST /clubs/{id}/ask/*`) e clubes autônomos (`POST /admin/ai-clubs`,
`POST /admin/clubs/{id}/run-ai`). Sem a chave, tudo o resto funciona normalmente —
a regra fundadora abaixo garante que a IA é sempre opcional.

Ver [.claude/skills/run-footverse/SKILL.md](.claude/skills/run-footverse/SKILL.md)
para um guia detalhado de smoke test ponta a ponta, incluindo armadilhas reais já
descobertas (proxy do Vite, target do uvicorn, comportamento do mercado em memória).

## Decisão fundadora
**O motor determinístico (economia, simulação, regras) é autoritativo e nunca depende de LLM.**
A camada de IA — tanto os advisors assistivos (Scout/Coach/Finance, só texto) quanto o
`ClubManager` autônomo (Fase 4, ações reais) — sempre propõe ações através de tools que
chamam o `World`, que valida e executa. Se a IA cair, o jogo continua jogável: um clube
de IA sem resposta do LLM simplesmente não age naquela rodada.

## Roadmap macro
1. **Cartola 2.0** ✅ · 2. **Football Manager Social** ✅ · 3. **MMO Persistente** ✅ ·
4. **Clubes Autônomos por IA** ✅ (diferencial de mercado) · 5. Economia Global (adiada) · 6. MetaHumans + Unreal (documentada)
