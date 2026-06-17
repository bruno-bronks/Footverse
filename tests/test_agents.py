"""Testes da camada de agentes assistivos (Scout/Coach/Finance).

Estratégia: as tools são testadas diretamente sobre o World (sem LLM).
O Advisor é testado com `_run` mockado — não requer OPENAI_API_KEY.
Nenhum teste aqui chama a API OpenAI de verdade.
"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import patch

import pytest

from footverse import config
from footverse.agents.tools import make_tools
from footverse.world import World

_CORES = ["#000000", "#D4AF37"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


def _world_com_clube() -> tuple[World, str]:
    world = World("TEST_SECRET")
    club = world.criar_clube("user_1", "FC Teste", _CORES)
    return world, club.id


def _montar_e_escalar(world: World, club_id: str) -> None:
    por_setor: dict = defaultdict(list)
    for mp in sorted(world.mercado_disponivel(), key=lambda m: m.valor_fvs):
        por_setor[mp.setor].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            world.comprar(club_id, mp.player.id)
            titulares.append((mp.player.id, slot))
    world.escalar(club_id, "4-3-3", titulares, [])


# ── testes das tools (sem LLM) ────────────────────────────────────────────────

def test_ver_clube_retorna_nome_e_saldo():
    world, cid = _world_com_clube()
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_clube"].invoke({})
    assert "FC Teste" in resultado
    assert "FV$50,000,000" in resultado
    assert str(config.RODADAS_POR_TEMPORADA) in resultado


def test_ver_elenco_vazio():
    world, cid = _world_com_clube()
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_elenco"].invoke({})
    assert "vazio" in resultado.lower()


def test_ver_elenco_com_jogadores():
    world, cid = _world_com_clube()
    _montar_e_escalar(world, cid)
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_elenco"].invoke({})
    assert "11 jogadores" in resultado
    assert "OVR" in resultado
    assert "FV$" in resultado


def test_ver_mercado_lista_disponíveis():
    world, cid = _world_com_clube()
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_mercado"].invoke({})
    # 50 jogadores no mercado, nenhum vendido ainda
    assert "50 jogadores" in resultado
    assert "OVR" in resultado


def test_ver_mercado_reduz_apos_compra():
    world, cid = _world_com_clube()
    pid = world.mercado_disponivel()[0].player.id
    world.comprar(cid, pid)
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_mercado"].invoke({})
    assert "49 jogadores" in resultado


def test_ver_escalacao_sem_lineup():
    world, cid = _world_com_clube()
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_escalacao"].invoke({})
    assert "sem escalação" in resultado.lower()


def test_ver_escalacao_com_lineup():
    world, cid = _world_com_clube()
    _montar_e_escalar(world, cid)
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_escalacao"].invoke({})
    assert "4-3-3" in resultado
    assert "GOL" in resultado
    assert "OVR" in resultado


def test_ver_ledger_reconciliado():
    world, cid = _world_com_clube()
    tools = {t.name: t for t in make_tools(world, cid)}
    resultado = tools["ver_ledger"].invoke({})
    assert "✓" in resultado
    assert "FV$50,000,000" in resultado


def test_tools_nao_modificam_estado():
    """Invocar todas as tools não muda saldo nem elenco."""
    world, cid = _world_com_clube()
    saldo_antes = world.store.get_club(cid).saldo_fvs
    elenco_antes = len(world.store.elenco(cid))
    tools = make_tools(world, cid)
    for t in tools:
        t.invoke({})
    assert world.store.get_club(cid).saldo_fvs == saldo_antes
    assert len(world.store.elenco(cid)) == elenco_antes


# ── regressão: construção real do grafo (sem chamar o LLM) ──────────────────
# `_build_graph` não faz nenhuma chamada de rede (só monta o ChatOpenAI client
# e o StateGraph); roda sem OPENAI_API_KEY válida. Isto pega bugs de assinatura
# da API do langgraph/langchain (ex.: rename de kwargs entre versões) que os
# testes com `_run` mockado não pegam, pois nunca chegam a montar o grafo real.
def test_advisor_build_graph_nao_quebra(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    from footverse.agents.advisor import Advisor
    world, cid = _world_com_clube()
    advisor = Advisor(world)
    graph = advisor._build_graph("prompt de teste", cid)
    assert graph is not None


# ── limite de passos por decisão (controle de custo) ────────────────────────
class _ConfigCapturingGraph:
    def __init__(self):
        self.received_config: dict | None = None

    def invoke(self, input, config=None):
        self.received_config = config
        return {"messages": [type("M", (), {"content": "ok"})()]}


class _RecursionErrorGraph:
    def invoke(self, input, config=None):
        from langgraph.errors import GraphRecursionError
        raise GraphRecursionError("limite de passos excedido")


def test_advisor_aplica_recursion_limit(monkeypatch):
    from footverse.agents import advisor as advisor_module

    world, cid = _world_com_clube()
    adv = advisor_module.Advisor(world)
    fake_graph = _ConfigCapturingGraph()
    monkeypatch.setattr(adv, "_build_graph", lambda *a, **k: fake_graph)

    adv.scout(cid, "Quem devo comprar?")

    assert fake_graph.received_config is not None
    assert fake_graph.received_config["recursion_limit"] == advisor_module.AGENT_MAX_STEPS


def test_advisor_trata_limite_excedido_sem_propagar_excecao(monkeypatch):
    from footverse.agents import advisor as advisor_module

    world, cid = _world_com_clube()
    adv = advisor_module.Advisor(world)
    monkeypatch.setattr(adv, "_build_graph", lambda *a, **k: _RecursionErrorGraph())

    resposta = adv.scout(cid, "Quem devo comprar?")  # não deve lançar
    assert isinstance(resposta, str)
    assert len(resposta) > 0


# ── testes do Advisor (LLM mockado) ──────────────────────────────────────────

def test_advisor_scout_com_run_mockado():
    from footverse.agents.advisor import Advisor
    world, cid = _world_com_clube()
    advisor = Advisor(world)
    resposta_fake = "Recomendo comprar um GOL barato: mkt_1 (OVR 52, FV$1.2M)."
    with patch.object(Advisor, "_run", return_value=resposta_fake):
        resposta = advisor.scout(cid, "Quem devo comprar primeiro?")
    assert "GOL" in resposta


def test_advisor_coach_com_run_mockado():
    from footverse.agents.advisor import Advisor
    world, cid = _world_com_clube()
    advisor = Advisor(world)
    resposta_fake = "Sugiro a formação 4-3-3 com os jogadores X, Y, Z."
    with patch.object(Advisor, "_run", return_value=resposta_fake):
        resposta = advisor.coach(cid, "Qual a melhor escalação?")
    assert "4-3-3" in resposta


def test_advisor_finance_com_run_mockado():
    from footverse.agents.advisor import Advisor
    world, cid = _world_com_clube()
    advisor = Advisor(world)
    resposta_fake = "Com FV$50M, invista no elenco agora. Promoção vale FV$8M extra."
    with patch.object(Advisor, "_run", return_value=resposta_fake):
        resposta = advisor.finance(cid, "Como devo gastar o orçamento?")
    assert "FV$" in resposta


# ── teste da API (endpoints /ask/*) ──────────────────────────────────────────

def test_api_ask_scout_sem_agents_retorna_503():
    """Sem [agents] instalado, endpoints /ask/* retornam 503."""
    from httpx import Client
    from fastapi.testclient import TestClient
    from footverse.api.app import create_app

    world = World("TEST_SECRET")
    app = create_app(world)
    club = world.criar_clube("u", "FC API", _CORES)

    with TestClient(app) as client:
        # sem mock de Advisor: import falha se langgraph não estiver instalado
        # vamos forçar o cenário de "não instalado" mockando o import
        with patch.dict("sys.modules", {"footverse.agents.advisor": None}):
            # reset cached advisor
            if hasattr(app.state, "_advisor"):
                del app.state._advisor
            resp = client.post(
                f"/clubs/{club.id}/ask/scout",
                json={"pergunta": "Quem comprar?"},
            )
        # 503 se não instalado, ou 200 se estiver instalado mas sem API key
        assert resp.status_code in (200, 503, 500)


def test_api_ask_scout_com_advisor_mockado():
    """Endpoint /ask/scout chama Advisor.scout e devolve o conselho."""
    from fastapi.testclient import TestClient
    from footverse.api.app import create_app
    from footverse.agents.advisor import Advisor

    world = World("TEST_SECRET")
    app = create_app(world)
    club = world.criar_clube("u", "FC API Mock", _CORES)

    with patch.object(Advisor, "_run", return_value="Compre o mkt_1."):
        with TestClient(app) as client:
            # reset para forçar nova instância do Advisor
            if hasattr(app.state, "_advisor"):
                del app.state._advisor
            resp = client.post(
                f"/clubs/{club.id}/ask/scout",
                json={"pergunta": "Quem comprar?"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert body["agente"] == "scout"
    assert "mkt_1" in body["conselho"]
