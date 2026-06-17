# Footverse — Design Document

**Versão:** 0.1 (Fase 1 — MVP "Cartola 2.0")
**Data:** Junho 2026
**Status:** Em definição
**Autor:** Bruno + Engenharia de IA

---

## 0. O QUE É O FOOTVERSE

O Footverse é um **MMO persistente de futebol concebido como sistema de IA + economia + agentes** — não como um app de jogo tradicional. A tese central:

> Um jogo de gestão de futebol bem-feito é, no fundo, um **mundo simulado** com economia, decisões de agentes e narrativa emergente. A arquitetura certa para construí-lo é a de engenharia de IA moderna (agent graph, tool calling, memory/RAG, eval, observability), não a de um CRUD com regras.

A visão de longo prazo (6 fases) culmina em um mundo onde **milhões de clubes humanos convivem com milhares de clubes administrados por agentes de IA** — negociando jogadores, demitindo técnicos, revelando talentos e criando histórias próprias continuamente. Este documento cobre **apenas a Fase 1**.

### Roadmap macro
| Fase | Nome | Essência |
|------|------|----------|
| 1 | Cartola 2.0 | Gestão single-player com economia FV$ e progressão por divisões |
| 2 | Football Manager Social | Multiplayer assíncrono, ligas entre humanos |
| 3 | MMO Persistente | Mundo único e contínuo, tempo de jogo persistente |
| 4 | **Clubes Autônomos por IA** | Clubes-IA convivem e competem com humanos (o diferencial de mercado) |
| 5 | Economia Global | Mercado e moeda FV$ em escala global |
| 6 | MetaHumans + Unreal | Camada visual 3D |

---

## 1. PROBLEMA / OPORTUNIDADE

### 1.1 Contexto
Jogos de fantasy/manager (Cartola FC, Football Manager, Fantasy Premier) são, hoje, **conjuntos de regras estáticas**. As decisões "do jogo" (preço de jogador, mercado, adversários) são tabelas e heurísticas fixas. Não há mundo vivo: tudo gira em torno do humano, e o cenário é inerte entre as ações dele.

### 1.2 Oportunidade
A maturidade de LLMs baratos + tool-calling + execução durável (Temporal) torna possível, pela primeira vez, um **mundo que se move sozinho**: clubes que tomam decisões plausíveis, um mercado com liquidez real e narrativa que emerge da simulação. Isso praticamente não existe no mercado.

### 1.3 Por que começar pela Fase 1
A Fase 1 valida o **núcleo determinístico** (economia, simulação de partida, progressão) e a **camada de agentes assistivos** (Scout/Coach/Finance que ajudam o humano) — sem ainda assumir o risco da autonomia total (Fase 4). É o terreno onde se prova que economia e simulação fecham as contas.

---

## 2. ESCOPO DA FASE 1 (MVP — "Cartola 2.0")

### 2.1 O jogador consegue:
1. **Criar um clube** (nome, escudo, cores) → recebe orçamento inicial em FV$ e entra na Série D.
2. **Comprar jogadores** no mercado, respeitando saldo.
3. **Escalar o time** numa formação válida.
4. **Receber pontuação** após cada rodada, derivada do desempenho dos jogadores escalados.
5. **Subir de divisão** (Série D → C → B → A) conforme acumula pontos/temporadas.

### 2.2 Fora de escopo na Fase 1 (explicitamente adiado)
- Multiplayer / PvP (Fase 2)
- Clubes administrados por IA (Fase 4)
- Tempo persistente contínuo / mundo único (Fase 3)
- Patrocínio, torcida, infraestrutura, lesões/medical (Fase 2+)
- Renderização 3D (Fase 6)

> A camada **Medical** e **Market (autônomo)** e os agentes **Finance/Scout avançados** existem na visão, mas na Fase 1 entram apenas como assistentes opcionais — o núcleo jogável não depende deles.

---

## 3. ENTIDADES DO DOMÍNIO (Fase 1)

```
Clube ──< possui >── Jogador
  │                     │
  │                     └── atributos, posição, forma, valor de mercado
  ├── orçamento (FV$)
  ├── divisão (D, C, B, A)
  ├── pontuação acumulada (temporada)
  └── escalação (formação + 11 titulares)

Mercado ── lista de Jogadores disponíveis + preços
Temporada ── conjunto de Rodadas
Rodada ── gera pontuação por Jogador escalado
Economia ── moeda FV$ (faucets: premiação por rodada/divisão; sinks: compras)
```

### Entidades mínimas
| Entidade | Campos principais |
|----------|-------------------|
| Clube | id, nome, escudo, cores, orçamento_fvs, divisão, pontos_temporada |
| Jogador | id, nome, posição, atributos{}, forma, valor_mercado_fvs, clube_id\|null |
| Escalação | clube_id, formação, titulares[11], reservas[] |
| Rodada | id, temporada, número, status |
| PontuaçãoRodada | clube_id, rodada_id, pontos, breakdown_por_jogador[] |

---

## 4. PRINCÍPIO DE ARQUITETURA (decisão fundadora)

**Separação rígida entre o Motor Determinístico e a Camada de IA.** Esta é a decisão mais importante do projeto inteiro e precisa estar certa desde a Fase 1.

```
┌──────────────────────────────────────────────────┐
│  CAMADA DE IA (não-determinística, opcional)      │
│  Agentes Scout/Coach/Finance → conselho/narrativa │
│  NUNCA decide resultado, preço ou pontuação        │
└──────────────────────┬───────────────────────────┘
                       │ lê estado / sugere ações
┌──────────────────────▼───────────────────────────┐
│  MOTOR DETERMINÍSTICO (autoritativo, server-side) │
│  - Economia FV$ (saldo, faucets, sinks)            │
│  - Simulação de partida / pontuação da rodada      │
│  - Validação de escalação e regras                 │
│  - Progressão de divisão                           │
│  Determinístico, testável, auditável, reprodutível │
└──────────────────────┬───────────────────────────┘
                       │
        PostgreSQL (verdade)  ·  Redis (cache/sessão)
```

**Regras invioláveis:**
1. Todo número que afeta o jogo (saldo, pontos, resultado) vem do **motor determinístico**, nunca de um LLM.
2. O LLM só **lê** o estado e produz **texto/sugestão**. Se o LLM cair, o jogo continua jogável.
3. A simulação deve ser **reprodutível** a partir de uma seed → essencial para testes (Harness) e para auditoria/anti-cheat.

> Isto antecipa a Fase 4: quando clubes-IA agirem sozinhos, eles continuarão *propondo ações ao motor*, que valida e executa — nunca "inventando" resultados.

---

## 5. PIPELINE DE ENGENHARIA (a ordem de construção)

Seguindo o pipeline do projeto:

```
Design Doc (este)  →  Specs  →  Context Engineering  →  Prompt Templates
  →  Agent Graph  →  Tool Calling  →  Memory/RAG  →  Harness
  →  Evaluation  →  Observability  →  Feedback Loop  →  Continuous Improvement  →  Production
```

Na Fase 1, a prioridade prática é: **Specs → Motor determinístico + Tools → Harness (testes) → Agent graph assistivo → API → Frontend**. Observability e eval entram cedo mas leves.

### Specs da Fase 1
| Spec | Título | Camada |
|------|--------|--------|
| SPEC-001 | Criação de clube | Motor + economia |
| SPEC-002 | Compra de jogador | Motor + economia + mercado |
| SPEC-003 | Escalação | Motor + validação de regras |
| SPEC-004 | Pontuação da rodada | Motor + simulação |
| SPEC-005 | Jogador: atributos, valor de mercado e pontuação | Motor + modelagem (base de 002/004) |
| SPEC-006 | Temporada e progressão de divisão | Motor + competição (liga-sombra NPC) |

(Ver pasta `specs/`.)

---

## 6. STACK (Fase 1 — mínima; alvo de produção entre parênteses)

| Camada | Fase 1 | Produção (Fase 3+) |
|--------|--------|--------------------|
| Backend / API | FastAPI + Python 3.12 | + API Gateway |
| Motor determinístico | Engine própria (Python puro, sem LLM) | idem, possível extração p/ serviço |
| Agent layer | LangGraph | LangGraph |
| LLM | Claude (Opus/Sonnet) — assistivo | Claude / GPT / Nova |
| Banco | PostgreSQL | PostgreSQL |
| Cache | Redis | Redis |
| Vector DB / memória | Chroma (dev) | OpenSearch / Pinecone |
| Orquestração de tempo | — (Fase 1 é por requisição) | Temporal |
| Eventos | — | Kafka |
| Frontend | React | React + Next.js / Flutter (mobile) |
| Observability | Logging + métricas básicas | Langfuse + OpenTelemetry + Grafana + Phoenix |
| Infra | Docker Compose | Kubernetes / AWS |

> Reaproveitamento direto do esqueleto **Football AI Pro**: orchestrator, padrão de tool registry, RAG/memória, harness, fallback obrigatório, isolamento por tenant (lá `team_id`, aqui `club_id`/`user_id`).

---

## 7. ECONOMIA FV$ (princípios — detalhe vem em spec própria)

A economia é um problema de design, não de IA. Princípios da Fase 1:
- **Régua de valores ("milhões baixa"):** jogador de Série D vale ~**1–5M** (craque até ~**20M**). É a escala única que todas as specs usam — evita a incoerência de orçamento e preço viverem em ordens de grandeza diferentes.
- **Faucets (entrada de FV$):** premiação por rodada e por divisão; bônus de acesso/título.
- **Sinks (saída de FV$):** compra de jogadores no mercado-NPC (dinheiro **sai de circulação**); (futuro: salários, manutenção).
- **Orçamento inicial:** valor fixo por clube novo = **FV$ 50.000.000** (calibrável), dimensionado para comprar um elenco titular inteiro no mercado barato.
- **Sem elenco inicial:** clube novo nasce com 0 jogadores e monta o time **comprando no mercado barato de Série D** (modelo escolhido na revisão). Requer um mercado populado por geração determinística (SPEC-005).
- **Conservação correta:** `FV$ em circulação = Σ faucets − Σ sinks`. Comprar do mercado-NPC é **sink** (não é "conservação" — o dinheiro é retirado). A invariante auditável é o **ledger reconciliar com o saldo**, não dinheiro ser preservado na compra.
- **Anti-inflação:** preços de mercado derivados de atributos+forma por fórmula determinística; sem geração arbitrária de dinheiro.
- **Auditável:** todo movimento de FV$ é uma transação registrada (ledger), nunca um update solto de saldo.

---

## 8. MÉTRICAS DE SUCESSO (Fase 1)

| Métrica | Alvo MVP |
|---------|----------|
| Loop jogável completo (criar→comprar→escalar→pontuar→subir) | 100% funcional |
| Reprodutibilidade da simulação (mesma seed → mesmo resultado) | 100% |
| Cobertura de testes do motor determinístico | > 90% |
| Economia fecha (nenhum FV$ criado/destruído fora de faucet/sink) | invariante testada |
| Latência de uma ação (criar/comprar/escalar) | < 500ms (sem LLM no caminho crítico) |

---

## 9. RISCOS (Fase 1)

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Economia desbalanceada (inflação/quebra) | Alto | Ledger + invariantes testadas + fórmula determinística de preço |
| Acoplar LLM ao caminho crítico do jogo | Alto | Regra fundadora seção 4: LLM só assistivo |
| Simulação não-reprodutível | Médio | Seed explícita + testes de reprodutibilidade |
| Escopo da Fase 1 inflar p/ Fase 2+ | Médio | Lista "fora de escopo" (2.2) tratada como contrato |

---

## 10. PRÓXIMOS PASSOS

1. Revisar e fechar este Design Doc.
2. Detalhar SPEC-001 a SPEC-004 (já rascunhadas em `specs/`).
3. ~~Definir a fórmula determinística de **valor de mercado** e de **pontuação por jogador**~~ → **feito em SPEC-005** (inclui modelo de atributos e geração do mercado de Série D).
4. Montar o esqueleto de repositório (reaproveitando Football AI Pro) e o motor determinístico com Harness desde o dia 1.
