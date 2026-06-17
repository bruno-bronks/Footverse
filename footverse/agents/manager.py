"""Gerente de IA de clube (Fase 4) — clube autônomo joga sozinho.

Diferente do `Advisor` (assistivo, só aconselha), o `ClubManager` toma ações
reais a cada rodada: compra/vende jogadores e define escalação, sempre por
meio das tools de `manager_tools.py`, que delegam ao motor determinístico do
`World`. O agente NUNCA escreve estado diretamente — apenas chama tools que
chamam o motor, que valida e executa (DESIGN_DOC §4).

Se a chamada ao LLM falhar (rede, rate limit, ImportError de [agents] não
instalado), o clube simplesmente não age nesta rodada — mantém o que já tinha
(escalação/elenco anteriores) e é pontuado normalmente. O jogo nunca trava.

Variáveis de ambiente:
  OPENAI_API_KEY             — obrigatória para invocar o LLM
  FOOTVERSE_AGENT_MODEL      — nome do modelo OpenAI (padrão: gpt-4o-mini)
  FOOTVERSE_AGENT_MAX_STEPS  — teto de passos (model+tool) por decisão (padrão: 20)

Custo sem teto é um risco real, não hipotético: numa decisão observada em
teste manual, o agente chamou tools 78 vezes numa única rodada (`escalar_time`
sozinho 31 vezes, claramente tentando às cegas sem ajustar a causa do erro).
`FOOTVERSE_AGENT_MAX_STEPS` limita isso via `recursion_limit` do LangGraph —
ações já tomadas até o limite ser atingido permanecem (cada tool já mexeu no
motor de verdade); só a conversa com o LLM é interrompida.
"""

from __future__ import annotations

import logging
import os
import time

from .manager_tools import make_action_tools
from .tools import make_tools
from ..observability import AgentLogger
from ..world import World

logger = logging.getLogger("footverse.agents")

AGENT_MODEL: str = os.getenv("FOOTVERSE_AGENT_MODEL", "gpt-4o-mini")
MEMORY_DIR: str | None = os.getenv("FOOTVERSE_MEMORY_DIR")
AGENT_MAX_STEPS: int = int(os.getenv("FOOTVERSE_AGENT_MAX_STEPS", "20"))

_PERSONALIDADES: dict[str, str] = {
    "agressivo": (
        "Agressivo — prioriza comprar os jogadores de maior OVR disponíveis, "
        "gasta o caixa rapidamente para montar o melhor XI possível."
    ),
    "conservador": (
        "Conservador — preserva caixa, só compra o essencial para fechar o XI, "
        "prefere jogadores baratos e vende excedentes para acumular FV$."
    ),
    "equilibrado": (
        "Equilibrado — balanceia reforços com manutenção de caixa, compra "
        "conforme a necessidade real do elenco."
    ),
}

_MANAGER_PROMPT_TEMPLATE = """\
Você é o gerente autônomo de um clube de futebol no Footverse — um simulador \
de gestão com economia real (FV$) e mercado de jogadores. Diferente de um \
assistente, você TOMA AÇÕES REAIS: suas chamadas de tool (comprar_jogador, \
vender_jogador, escalar_time) são executadas de verdade pelo motor do jogo.

Personalidade: {personalidade}

Seu objetivo nesta rodada:
1. Se a tool buscar_historico estiver disponível, consulte-a primeiro (ex:
   "resultado das últimas temporadas", "padrão de compras e vendas") — use
   esse contexto para informar a decisão (ex: evite repetir um erro do
   passado, mantenha consistência com a estratégia que já vinha seguindo).
2. Verifique o elenco (ver_elenco) e a escalação ativa (ver_escalacao).
3. Se houver menos de 11 jogadores aptos a titular, ou lacunas de posição
   (faltam GOL, ZAG, LAT, VOL, MEI, EXT ou ATA suficientes), avalie o mercado
   (ver_mercado) e o saldo (ver_clube), e compre jogadores com comprar_jogador
   — sempre dentro do orçamento disponível.
4. Garanta que, ao final, exista uma escalação válida (11 titulares, 1 GOL,
   formação suportada) usando escalar_time — a rodada só pontua corretamente
   se houver uma escalação ativa.
5. Se tiver reservas excedentes e quiser caixa, considere vender_jogador por
   um preço próximo do valor de mercado dele.

Regras invioláveis:
- NUNCA tente gastar mais do que o saldo disponível (ver_clube mostra o saldo).
- SEMPRE termine com uma escalação válida, se o elenco permitir 11 titulares.
- Seja eficiente: poucas chamadas de tool, decisões diretas.
- Responda em português; ao final, resuma em 2-3 frases as ações tomadas.\
"""


class ClubManager:
    """Agente autônomo que decide e executa ações para um clube de IA.

    Uma instância é reutilizável entre clubes e rodadas — `decide()` constrói
    o grafo sob demanda para sempre refletir o estado mais recente do World.
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
        """Retorna um MemoryStore pronto (índice já construído) ou None."""
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

    def _build_graph(self, club_id: str, personalidade: str):
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=self._model_name, temperature=0.3)
        memory = self._get_memory(club_id)
        tools = make_tools(self._world, club_id, memory=memory) + make_action_tools(self._world, club_id)
        prompt = _MANAGER_PROMPT_TEMPLATE.format(
            personalidade=_PERSONALIDADES.get(personalidade, _PERSONALIDADES["equilibrado"])
        )
        return create_agent(llm, tools, system_prompt=prompt)

    def _run(self, club_id: str, personalidade: str) -> str:
        from langgraph.errors import GraphRecursionError

        graph = self._build_graph(club_id, personalidade)
        callbacks = [AgentLogger("manager", club_id)] if AgentLogger is not None else []
        config: dict = {"recursion_limit": AGENT_MAX_STEPS}
        if callbacks:
            config["callbacks"] = callbacks
        t0 = time.perf_counter()
        try:
            result = graph.invoke(
                {"messages": [("human", "É a sua vez de gerenciar o clube nesta rodada.")]},
                config=config,
            )
        except GraphRecursionError:
            ms = round((time.perf_counter() - t0) * 1000, 1)
            tools_called = callbacks[0].tools_called if callbacks else []
            logger.warning(
                "ai_manager_step_limit",
                extra={"club_id": club_id, "tools_called": tools_called, "ms": ms,
                      "limit": AGENT_MAX_STEPS},
            )
            return (
                f"Limite de {AGENT_MAX_STEPS} passos atingido nesta rodada — "
                "as ações já executadas até aqui foram mantidas."
            )
        ms = round((time.perf_counter() - t0) * 1000, 1)
        tools_called = callbacks[0].tools_called if callbacks else []
        logger.info(
            "ai_manager_decision",
            extra={"club_id": club_id, "tools_called": tools_called, "ms": ms},
        )
        return result["messages"][-1].content

    def decide(self, club_id: str) -> str:
        """Roda um ciclo de decisão completo para o clube (pode comprar/vender/escalar)."""
        club = self._world.store.get_club(club_id)
        personalidade = (club.ia_personalidade if club else None) or "equilibrado"
        return self._run(club_id, personalidade)
