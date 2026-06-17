"""Testes dos clubes autônomos de IA (Fase 4).

Estratégia: o `ClubManager` real nunca é invocado contra a API OpenAI —
ou se injeta um `FakeManager` no `World`, ou se faz mock de `ClubManager._run`
(mesmo padrão de `tests/test_agents.py`). As action tools são testadas
diretamente sobre o `World`, sem LLM. `test_club_manager_build_graph_nao_quebra`
constrói o grafo real (sem chamar a rede) para pegar bugs de assinatura da API
do langgraph/langchain entre versões.
"""

from __future__ import annotations

from collections import defaultdict
from unittest.mock import patch

import pytest

from footverse.agents.manager_tools import make_action_tools
from footverse.agents.tools import make_tools
from footverse.world import World

_CORES = ["#111111", "#eeeeee"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


class FakeManager:
    """Substitui o ClubManager real em testes — não chama LLM."""

    def __init__(self, resultado: str = "ok", excecao: Exception | None = None):
        self.calls: list[str] = []
        self._resultado = resultado
        self._excecao = excecao

    def decide(self, club_id: str) -> str:
        self.calls.append(club_id)
        if self._excecao is not None:
            raise self._excecao
        return self._resultado


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


# ── criação de clube de IA ──────────────────────────────────────────────────
def test_criar_clube_ia_seta_flags():
    world = World("AI_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES, personalidade="agressivo")
    assert club.gerenciado_por_ia is True
    assert club.ia_personalidade == "agressivo"
    assert club.user_id.startswith("ai_")


def test_criar_clube_ia_personalidade_padrao():
    world = World("AI_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)
    assert club.ia_personalidade == "equilibrado"


def test_criar_clube_ia_recebe_orcamento_inicial():
    world = World("AI_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)
    assert club.saldo_fvs == 50_000_000


def test_clube_humano_nao_eh_gerenciado_por_ia():
    world = World("AI_TEST")
    club = world.criar_clube("u1", "Humano FC", _CORES)
    assert club.gerenciado_por_ia is False
    assert club.ia_personalidade is None


def test_criar_clube_ia_persiste_em_sqlstore():
    from footverse.state.sqlstore import SqlStore
    world = World("AI_TEST", store=SqlStore("sqlite:///:memory:"))
    club = world.criar_clube_ia("Robot FC", _CORES, personalidade="conservador")
    recarregado = world.store.get_club(club.id)
    assert recarregado.gerenciado_por_ia is True
    assert recarregado.ia_personalidade == "conservador"


# ── run_ai_manager ───────────────────────────────────────────────────────────
def test_run_ai_manager_usa_manager_injetado():
    fake = FakeManager(resultado="comprei um GOL")
    world = World("AI_TEST", ai_manager=fake)
    club = world.criar_clube_ia("Robot FC", _CORES)
    resultado = world.run_ai_manager(club.id)
    assert resultado == "comprei um GOL"
    assert fake.calls == [club.id]


def test_run_ai_manager_retorna_none_se_decide_falha():
    fake = FakeManager(excecao=RuntimeError("API indisponível"))
    world = World("AI_TEST", ai_manager=fake)
    club = world.criar_clube_ia("Robot FC", _CORES)
    resultado = world.run_ai_manager(club.id)
    assert resultado is None


def test_run_ai_manager_sem_agents_retorna_none():
    world = World("AI_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)
    with patch.dict("sys.modules", {"footverse.agents.manager": None}):
        resultado = world.run_ai_manager(club.id)
    assert resultado is None


# ── integração com o tick ───────────────────────────────────────────────────
def test_tick_aciona_ai_manager_apenas_para_clubes_ia():
    fake = FakeManager()
    world = World("AI_TEST", ai_manager=fake)
    ai_club = world.criar_clube_ia("Robot FC", _CORES)
    human_club = world.criar_clube("u1", "Humano FC", _CORES)

    world.tick(now=1000.0)

    assert fake.calls == [ai_club.id]
    assert human_club.id not in fake.calls


def test_tick_continua_se_ai_manager_falha():
    fake = FakeManager(excecao=RuntimeError("boom"))
    world = World("AI_TEST", ai_manager=fake)
    ai_club = world.criar_clube_ia("Robot FC", _CORES)

    result = world.tick(now=1000.0)

    assert result.advanced is True
    assert len(result.eventos) == 1
    assert result.eventos[0].club_id == ai_club.id
    assert result.eventos[0].tipo == "RODADA"


def test_tick_ai_manager_pode_definir_escalacao_antes_da_pontuacao():
    """Um FakeManager que realmente compra e escala deve refletir no tick."""
    world = World("AI_TEST")
    ai_club = world.criar_clube_ia("Robot FC", _CORES)

    class EscalaManager:
        def decide(self, club_id: str) -> str:
            _montar_e_escalar(world, club_id)
            return "escalado"

    world._ai_manager = EscalaManager()
    result = world.tick(now=1000.0)

    assert result.eventos[0].club_id == ai_club.id
    season = world.store.get_season(ai_club.id)
    assert len(season.rodadas) == 1


# ── regressão: construção real do grafo (sem chamar o LLM) ──────────────────
def test_club_manager_build_graph_nao_quebra(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    from footverse.agents.manager import ClubManager
    world = World("AI_BUILD_GRAPH_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)
    manager = ClubManager(world)
    graph = manager._build_graph(club.id, "equilibrado")
    assert graph is not None


# ── action tools (sem LLM) ───────────────────────────────────────────────────
def _world_ia_com_clube() -> tuple[World, str]:
    world = World("AI_TOOLS_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)
    return world, club.id


def test_comprar_jogador_tool_sucesso():
    world, cid = _world_ia_com_clube()
    pid = world.mercado_disponivel()[0].player.id
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["comprar_jogador"].invoke({"player_id": pid})
    assert "Comprado" in resultado
    assert pid in world.store.elenco(cid)


def test_comprar_jogador_tool_erro_jogador_inexistente():
    world, cid = _world_ia_com_clube()
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["comprar_jogador"].invoke({"player_id": "fantasma"})
    assert "ERRO" in resultado


def test_vender_jogador_tool_sucesso():
    world, cid = _world_ia_com_clube()
    pid = world.mercado_disponivel()[0].player.id
    world.comprar(cid, pid)
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["vender_jogador"].invoke({"player_id": pid, "preco_fvs": 1_000_000})
    assert "listado" in resultado.lower()
    assert world.store.get_listing(pid) is not None


def test_vender_jogador_tool_erro_nao_possui():
    world, cid = _world_ia_com_clube()
    pid = world.mercado_disponivel()[0].player.id  # não comprado
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["vender_jogador"].invoke({"player_id": pid, "preco_fvs": 1_000_000})
    assert "ERRO" in resultado


def test_cancelar_venda_tool():
    world, cid = _world_ia_com_clube()
    pid = world.mercado_disponivel()[0].player.id
    world.comprar(cid, pid)
    world.listar_venda(cid, pid, 1_000_000)
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["cancelar_venda"].invoke({"player_id": pid})
    assert "cancelada" in resultado.lower()
    assert world.store.get_listing(pid) is None


def test_escalar_time_tool_sucesso():
    world, cid = _world_ia_com_clube()
    por_setor: dict = defaultdict(list)
    for mp in sorted(world.mercado_disponivel(), key=lambda m: m.valor_fvs):
        por_setor[mp.setor].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            world.comprar(cid, mp.player.id)
            titulares.append({"player_id": mp.player.id, "posicao": slot})

    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["escalar_time"].invoke({
        "formacao": "4-3-3", "titulares": titulares, "reservas": [],
    })
    assert "4-3-3" in resultado
    assert world.store.get_lineup(cid) is not None


def test_escalar_time_tool_erro_formacao_invalida():
    world, cid = _world_ia_com_clube()
    tools = {t.name: t for t in make_action_tools(world, cid)}
    resultado = tools["escalar_time"].invoke({
        "formacao": "9-0-1", "titulares": [], "reservas": [],
    })
    assert "ERRO" in resultado


def test_action_tools_nao_aparecem_nas_tools_assistivas():
    """As tools do advisor (somente leitura) não incluem ações de escrita."""
    world, cid = _world_ia_com_clube()
    nomes_leitura = {t.name for t in make_tools(world, cid)}
    nomes_acao = {t.name for t in make_action_tools(world, cid)}
    assert nomes_leitura.isdisjoint(nomes_acao)


# ── standings exibem o flag de IA ───────────────────────────────────────────
def test_standings_mostra_gerenciado_por_ia():
    world = World("AI_TEST")
    ai_club = world.criar_clube_ia("Robot FC", _CORES)
    human_club = world.criar_clube("u1", "Humano FC", _CORES)

    rows = world.standings(human_club.divisao)
    by_id = {r["club_id"]: r for r in rows}
    assert by_id[ai_club.id]["gerenciado_por_ia"] is True
    assert by_id[human_club.id]["gerenciado_por_ia"] is False


# ── API admin ────────────────────────────────────────────────────────────────
@pytest.fixture
def client_factory():
    def _make(ai_manager=None):
        from fastapi.testclient import TestClient
        from footverse.api.app import create_app
        world = World("AI_API_TEST", ai_manager=ai_manager)
        return TestClient(create_app(world)), world
    return _make


def test_admin_criar_clube_ia_endpoint(client_factory):
    client, _ = client_factory()
    r = client.post("/admin/ai-clubs", json={
        "nome": "Robot United", "cores": _CORES, "personalidade": "agressivo",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["gerenciado_por_ia"] is True
    assert body["ia_personalidade"] == "agressivo"


def test_admin_run_ai_now_com_manager_injetado(client_factory):
    fake = FakeManager(resultado="Comprei 2 jogadores e escalei o time.")
    client, world = client_factory(ai_manager=fake)
    club = world.criar_clube_ia("Robot FC", _CORES)

    r = client.post(f"/admin/clubs/{club.id}/run-ai")
    assert r.status_code == 200
    body = r.json()
    assert body["club_id"] == club.id
    assert "escalei" in body["decisao"].lower()


def test_admin_run_ai_now_clube_inexistente_404(client_factory):
    client, _ = client_factory()
    r = client.post("/admin/clubs/inexistente/run-ai")
    assert r.status_code == 404


def test_admin_run_ai_now_sem_agents_503(client_factory):
    client, world = client_factory()
    club = world.criar_clube_ia("Robot FC", _CORES)
    with patch.dict("sys.modules", {"footverse.agents.manager": None}):
        r = client.post(f"/admin/clubs/{club.id}/run-ai")
    assert r.status_code == 503
