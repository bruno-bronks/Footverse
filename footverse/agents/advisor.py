"""Agentes assistivos do Footverse — Scout, Coach e Finance.

Três LangGraph ReAct agents, cada um com um papel e um conjunto de tools
read-only. Implementam o "agent graph assistivo" do DESIGN_DOC §5.

Regra fundadora (DESIGN_DOC §4): nenhum agente chama ação que modifica estado
do World. Se a IA cair, o jogo continua — os agentes são advisors opcionais.

Variáveis de ambiente:
  OPENAI_API_KEY             — obrigatória para invocar o LLM
  FOOTVERSE_AGENT_MODEL      — nome do modelo OpenAI (padrão: gpt-4o-mini)
"""

from __future__ import annotations

import logging
import os
import time

from .tools import make_tools
from ..observability import AgentLogger
from ..world import World

logger = logging.getLogger("footverse.agents")

AGENT_MODEL: str = os.getenv("FOOTVERSE_AGENT_MODEL", "gpt-4o-mini")
MEMORY_DIR: str | None = os.getenv("FOOTVERSE_MEMORY_DIR")
AGENT_MAX_STEPS: int = int(os.getenv("FOOTVERSE_AGENT_MAX_STEPS", "20"))

# ── Prompts de sistema ────────────────────────────────────────────────────────

_SCOUT_PROMPT = """\
Você é o Scout do Footverse, especialista em mercado de transferências.
Seu papel: analisar o mercado disponível e o elenco atual e recomendar compras.

Diretrizes:
- Priorize lacunas de posição (setores sem cobertura suficiente).
- Considere o OVR, a forma, a idade e o preço em FV$.
- Leve em conta o saldo disponível do clube.
- Sugira no máximo 5 jogadores específicos (com ID e justificativa breve).
- Responda em português, de forma direta e objetiva.
- NUNCA execute ações — apenas aconselhe o técnico.\
"""

_COACH_PROMPT = """\
Você é o Coach do Footverse, especialista em tática e escalação.
Seu papel: analisar o elenco e sugerir a melhor escalação e formação.

Diretrizes:
- Verifique compatibilidade de setor: GOL→GOL, DEF→ZAG/LAT, MEI→VOL/MEI/MEIA, ATA→EXT/ATA.
- Priorize jogadores com maior OVR e melhor forma no slot correspondente.
- Sugira uma formação concreta das 6 suportadas: 4-3-3, 4-4-2, 3-5-2, 4-2-3-1, 5-3-2, 3-4-3.
- Se o elenco estiver incompleto, indique quais posições precisam de reforço.
- Responda em português, de forma direta.
- NUNCA execute ações — apenas aconselhe o técnico.\
"""

_FINANCE_PROMPT = """\
Você é o Diretor Financeiro do Footverse, especialista em gestão de orçamento.
Seu papel: analisar o saldo e as finanças do clube e dar orientações estratégicas.

Diretrizes:
- Avalie o saldo atual versus o custo de montar um elenco competitivo.
- Considere as premiações esperadas por divisão e posição na tabela.
- Sugira se o clube deve gastar agressivamente ou preservar caixa.
- Mencione o premio máximo disponível (ex: promoção = FV$8M, permanência = FV$3M).
- Responda em português, de forma direta e objetiva.
- NUNCA execute ações — apenas aconselhe o técnico.\
"""


# ── Advisor ───────────────────────────────────────────────────────────────────

class Advisor:
    """Fachada dos três agentes assistivos do Footverse.

    Cada método cria um grafo LangGraph ReAct sob demanda, invoca-o com a
    pergunta do usuário e devolve a resposta como string.

    O grafo é criado por invocação (não cacheado) para garantir que sempre
    usa o estado mais recente do World.
    """

    def __init__(
        self,
        world: World,
        model: str = AGENT_MODEL,
        memory_dir: str | None = MEMORY_DIR,
        _memory_embedding_fn=None,  # injeção para testes (evita download ONNX)
    ) -> None:
        self._world = world
        self._model_name = model
        self._memory_dir = memory_dir
        self._memory_embedding_fn = _memory_embedding_fn

    def _get_memory(self, club_id: str):
        """Retorna um MemoryStore pronto (index já construído) ou None."""
        try:
            from .memory import MemoryStore
            mem = MemoryStore(
                self._world.store, club_id,
                persist_dir=self._memory_dir,
                _embedding_fn=self._memory_embedding_fn,
            )
            mem.build()
            return mem
        except ImportError:
            return None

    def _build_graph(self, system_prompt: str, club_id: str):
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=self._model_name, temperature=0)
        memory = self._get_memory(club_id)
        tools = make_tools(self._world, club_id, memory=memory)
        return create_agent(llm, tools, system_prompt=system_prompt)

    def _run(self, system_prompt: str, club_id: str, pergunta: str, agente: str = "?") -> str:
        from langgraph.errors import GraphRecursionError

        graph = self._build_graph(system_prompt, club_id)
        callbacks = [AgentLogger(agente, club_id)] if AgentLogger is not None else []
        config: dict = {"recursion_limit": AGENT_MAX_STEPS}
        if callbacks:
            config["callbacks"] = callbacks
        t0 = time.perf_counter()
        try:
            result = graph.invoke({"messages": [("human", pergunta)]}, config=config)
        except GraphRecursionError:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            logger.warning(
                "agent_step_limit",
                extra={"agente": agente, "club_id": club_id, "ms": ms, "limit": AGENT_MAX_STEPS},
            )
            return "Não consegui concluir a análise dentro do limite de passos. Tente reformular a pergunta."
        ms = round((time.perf_counter() - t0) * 1000, 1)
        tools_called = callbacks[0].tools_called if callbacks else []
        logger.info(
            "agent_invocation",
            extra={
                "agente": agente,
                "club_id": club_id,
                "tools_called": tools_called,
                "ms": ms,
            },
        )
        return result["messages"][-1].content

    def scout(self, club_id: str, pergunta: str) -> str:
        """Scout: conselho de mercado e transferências."""
        return self._run(_SCOUT_PROMPT, club_id, pergunta, agente="scout")

    def coach(self, club_id: str, pergunta: str) -> str:
        """Coach: conselho tático e de escalação."""
        return self._run(_COACH_PROMPT, club_id, pergunta, agente="coach")

    def finance(self, club_id: str, pergunta: str) -> str:
        """Finance: conselho financeiro e de orçamento."""
        return self._run(_FINANCE_PROMPT, club_id, pergunta, agente="finance")
