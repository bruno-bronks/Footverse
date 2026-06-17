"""Testes do MemoryStore e da tool buscar_historico.

Usa _SimpleHashEmbedding (sem download de modelo ONNX) para isolar os testes
do modelo all-MiniLM-L6-v2 cacheado em ~/.cache/chroma.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

pytest.importorskip("chromadb", reason="chromadb não instalado")

from footverse import config
from footverse.agents.memory import MemoryStore, _SimpleHashEmbedding
from footverse.agents.tools import make_tools
from footverse.world import World

_CORES = ["#000000", "#FFFFFF"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"],
    "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"],
    "ATA": ["EXT", "EXT", "ATA"],
}


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


def _mem(world: World, club_id: str) -> MemoryStore:
    """MemoryStore efêmero com hash embedding (sem ONNX)."""
    return MemoryStore(
        world.store, club_id,
        persist_dir=None,
        _embedding_fn=_SimpleHashEmbedding(),
    )


# ── build ─────────────────────────────────────────────────────────────────────

def test_build_sem_elenco():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Mem", _CORES)
    mem = _mem(world, club.id)
    n = mem.build()
    assert n >= 3   # perfil + temporada + historico + financas (min 4, sem elenco)


def test_build_com_elenco():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Elenco", _CORES)
    _montar_e_escalar(world, club.id)
    mem = _mem(world, club.id)
    n = mem.build()
    assert n == 5   # perfil + temporada + historico + elenco + financas


def test_build_idempotente():
    """Chamar build duas vezes não duplica documentos."""
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Idem", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    n1 = mem._col.count()
    mem.build()
    n2 = mem._col.count()
    assert n1 == n2


# ── conteúdo dos documentos ───────────────────────────────────────────────────

def test_perfil_contem_nome_e_divisao():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "Bravos FC", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    resultado = mem.search("nome do clube divisão")
    assert "Bravos FC" in resultado
    assert "SERIE_D" in resultado


def test_financas_contem_saldo():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Rico", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    resultado = mem.search("finanças saldo orçamento")
    assert "FV$" in resultado
    assert "50" in resultado   # 50M iniciais


def test_elenco_contem_posicoes():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Plantel", _CORES)
    _montar_e_escalar(world, club.id)
    mem = _mem(world, club.id)
    mem.build()
    resultado = mem.search("jogadores elenco posição")
    assert "GOL" in resultado or "DEF" in resultado or "MEI" in resultado or "ATA" in resultado


def test_historico_sem_temporadas_encerradas():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Novo", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    # Verify the history document was indexed with the expected content.
    # Hash embedding does not guarantee semantic ranking, so query by metadata.
    docs = mem._col.get(where={"tipo": "historico"})["documents"]
    assert docs
    assert "nenhuma temporada encerrada" in docs[0].lower()


def test_historico_apos_encerrar_temporada():
    """Após encerrar uma temporada, o histórico aparece no ledger."""
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Hist", _CORES)
    _montar_e_escalar(world, club.id)
    for r in range(1, config.RODADAS_POR_TEMPORADA + 1):
        world.pontuar(club.id, f"rod_{r}")
    world.encerrar(club.id)

    mem = _mem(world, club.id)
    mem.build()
    resultado = mem.search("resultado temporada encerrada prêmio")
    # deve conter referência à temporada e ao prêmio
    assert "temporada_1" in resultado.lower() or "FV$" in resultado


# ── search ────────────────────────────────────────────────────────────────────

def test_search_sem_documentos():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Empty", _CORES)
    # MemoryStore sem build — coleção vazia
    mem = _mem(world, club.id)
    resultado = mem.search("qualquer coisa")
    assert "nenhum" in resultado.lower()


def test_search_retorna_string():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Str", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    resultado = mem.search("saldo finanças")
    assert isinstance(resultado, str)
    assert len(resultado) > 0


# ── integração com a tool buscar_historico ────────────────────────────────────

def test_tool_buscar_historico_presente_com_memory():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Tool", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    tools = {t.name: t for t in make_tools(world, club.id, memory=mem)}
    assert "buscar_historico" in tools


def test_tool_buscar_historico_ausente_sem_memory():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC NoMem", _CORES)
    tools = {t.name: t for t in make_tools(world, club.id, memory=None)}
    assert "buscar_historico" not in tools


def test_tool_buscar_historico_invocacao():
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Invoke", _CORES)
    mem = _mem(world, club.id)
    mem.build()
    tools = {t.name: t for t in make_tools(world, club.id, memory=mem)}
    resultado = tools["buscar_historico"].invoke({"consulta": "saldo finanças"})
    assert isinstance(resultado, str)
    assert len(resultado) > 0


# ── integração com Advisor ────────────────────────────────────────────────────

def test_advisor_usa_memory_com_hash_embedding():
    """Advisor._get_memory retorna MemoryStore quando chromadb está disponível."""
    from footverse.agents.advisor import Advisor

    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Adv", _CORES)

    advisor = Advisor(world, _memory_embedding_fn=_SimpleHashEmbedding())
    # _get_memory deve retornar um MemoryStore (chromadb instalado)
    mem = advisor._get_memory(club.id)
    assert mem is not None
    # e o índice deve ter documentos
    assert mem._col.count() > 0


# ── integração com ClubManager (Fase 4) ────────────────────────────────────

def test_club_manager_usa_memory_com_hash_embedding():
    """ClubManager._get_memory retorna MemoryStore quando chromadb está disponível."""
    from footverse.agents.manager import ClubManager

    world = World("MEM_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)

    manager = ClubManager(world, _memory_embedding_fn=_SimpleHashEmbedding())
    mem = manager._get_memory(club.id)
    assert mem is not None
    assert mem._col.count() > 0


def test_club_manager_build_graph_inclui_buscar_historico(monkeypatch):
    """O grafo do ClubManager (com memória) expõe a tool buscar_historico."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")
    from footverse.agents.manager import ClubManager

    world = World("MEM_TEST")
    club = world.criar_clube_ia("Robot FC", _CORES)

    manager = ClubManager(world, _memory_embedding_fn=_SimpleHashEmbedding())
    graph = manager._build_graph(club.id, "equilibrado")
    # o ToolNode do grafo deve conhecer a tool buscar_historico
    tool_node = graph.nodes["tools"].bound
    assert "buscar_historico" in tool_node.tools_by_name


def test_get_ledger_store_in_memory():
    """Store.get_ledger retorna os lançamentos do clube."""
    world = World("MEM_TEST")
    club = world.criar_clube("u", "FC Ledger", _CORES)
    entries = world.store.get_ledger(club.id)
    assert len(entries) == 1          # apenas o INITIAL_GRANT
    assert entries[0].tipo == "INITIAL_GRANT"
    assert entries[0].valor_fvs == config.ORCAMENTO_INICIAL_FVS


def test_get_ledger_sqlstore(tmp_path):
    """SqlStore.get_ledger retorna lançamentos persistidos."""
    from footverse.state.sqlstore import SqlStore
    store = SqlStore(f"sqlite:///{tmp_path / 'fv.db'}")
    from footverse.state.economy import criar_clube
    club = criar_clube(store, "u", "FC SQL", _CORES)
    entries = store.get_ledger(club.id)
    assert len(entries) == 1
    assert entries[0].tipo == "INITIAL_GRANT"
