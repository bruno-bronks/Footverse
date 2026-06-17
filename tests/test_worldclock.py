"""Testes do relógio de mundo (Fase 3) — tick automático de rodadas.

Cobre: avanço de rodada com/sem escalação, idempotência dentro da janela
configurada, encerramento automático de temporada após 38 rodadas, e os
endpoints administrativos (/admin/tick, /admin/clock).
"""

from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from footverse.api import create_app
from footverse.world import ROUND_DURATION_SECONDS, World

_CORES = ["#0f172a", "#facc15"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


@pytest.fixture
def world() -> World:
    return World("CLOCK_TEST")


def _montar_xi(world: World, club_id: str) -> None:
    market = world.mercado_disponivel()
    por_setor = defaultdict(list)
    for mp in sorted(market, key=lambda m: m.valor_fvs):
        por_setor[mp.setor].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            world.comprar(club_id, mp.player.id)
            titulares.append((mp.player.id, slot))
    world.escalar(club_id, "4-3-3", titulares, [])


# ── tick básico ─────────────────────────────────────────────────────────────
def test_primeiro_tick_sempre_avanca(world):
    club = world.criar_clube("u1", "Clube A", _CORES)
    result = world.tick(now=1000.0)
    assert result.advanced is True
    assert len(result.eventos) == 1
    assert result.eventos[0].club_id == club.id
    assert result.eventos[0].tipo == "RODADA"


def test_tick_sem_escalacao_pontua_zero(world):
    world.criar_clube("u1", "Clube A", _CORES)
    result = world.tick(now=1000.0)
    assert result.eventos[0].pontos == 0.0


def test_tick_com_escalacao_pontua(world):
    club = world.criar_clube("u1", "Clube A", _CORES)
    _montar_xi(world, club.id)
    result = world.tick(now=1000.0)
    assert isinstance(result.eventos[0].pontos, float)

    season = world.store.get_season(club.id)
    assert len(season.rodadas) == 1


def test_tick_dentro_da_janela_eh_noop(world):
    world.criar_clube("u1", "Clube A", _CORES)
    r1 = world.tick(now=1000.0)
    assert r1.advanced is True

    r2 = world.tick(now=1000.0 + 10)  # bem antes de ROUND_DURATION_SECONDS
    assert r2.advanced is False
    assert r2.eventos == []
    assert r2.next_tick_in > 0


def test_tick_apos_intervalo_avanca_de_novo(world):
    club = world.criar_clube("u1", "Clube A", _CORES)
    world.tick(now=1000.0)
    r2 = world.tick(now=1000.0 + ROUND_DURATION_SECONDS + 1)
    assert r2.advanced is True

    season = world.store.get_season(club.id)
    assert len(season.rodadas) == 2


def test_tick_ignora_clube_sem_temporada_ativa(world):
    """Mundo sem clubes não quebra o tick."""
    result = world.tick(now=1000.0)
    assert result.advanced is True
    assert result.eventos == []


# ── encerramento automático de temporada ───────────────────────────────────
def test_tick_encerra_temporada_apos_38_rodadas(world):
    club = world.criar_clube("u1", "Clube A", _CORES)
    _montar_xi(world, club.id)

    now = 1000.0
    for i in range(38):
        result = world.tick(now=now)
        assert result.advanced is True
        now += ROUND_DURATION_SECONDS + 1

    tipos = [e.tipo for e in result.eventos]
    assert "TEMPORADA_ENCERRADA" in tipos

    nova_season = world.store.get_season(club.id)
    assert nova_season.temporada == 2
    assert nova_season.status == "EM_ANDAMENTO"
    assert len(nova_season.rodadas) == 0


# ── clock_status ────────────────────────────────────────────────────────────
def test_clock_status_antes_do_primeiro_tick(world):
    status = world.clock_status()
    assert status["last_tick_at"] is None
    assert status["round_duration_seconds"] == ROUND_DURATION_SECONDS


def test_clock_status_apos_tick(world):
    world.criar_clube("u1", "Clube A", _CORES)
    world.tick(now=1000.0)
    status = world.clock_status()
    assert status["last_tick_at"] == "1000.0"


# ── endpoints administrativos ───────────────────────────────────────────────
@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(World("CLOCK_API_TEST")))


def test_admin_clock_endpoint(client):
    r = client.get("/admin/clock")
    assert r.status_code == 200
    body = r.json()
    assert "round_duration_seconds" in body
    assert body["last_tick_at"] is None


def test_admin_tick_endpoint(client):
    client.post("/clubs", json={"user_id": "u1", "nome": "Clube X", "cores": _CORES})
    r = client.post("/admin/tick")
    assert r.status_code == 200
    body = r.json()
    assert body["advanced"] is True
    assert body["eventos"] == 1


def test_admin_tick_segunda_chamada_imediata_eh_noop(client):
    client.post("/clubs", json={"user_id": "u1", "nome": "Clube X", "cores": _CORES})
    client.post("/admin/tick")
    r = client.post("/admin/tick")
    body = r.json()
    assert body["advanced"] is False


def test_club_events_endpoint_404_se_clube_nao_existe(client):
    r = client.get("/clubs/inexistente/events")
    assert r.status_code == 404


# ── pub-sub de eventos (SSE) ─────────────────────────────────────────────────
def test_publish_tick_events_alcanca_assinante():
    """Verifica a lógica de publicação sem depender de streaming HTTP real
    (TestClient bloqueia em respostas SSE de longa duração)."""
    import asyncio

    from footverse.api.app import _publish_tick_events
    from footverse.world import TickEvent, TickResult

    class _FakeState:
        subscribers = {"club_1": [asyncio.Queue()]}

    state = _FakeState()
    result = TickResult(advanced=True, eventos=[
        TickEvent(club_id="club_1", tipo="RODADA", rodada_id="r1", pontos=10.0),
    ])
    _publish_tick_events(state, result)

    queue = state.subscribers["club_1"][0]
    assert not queue.empty()
    payload = queue.get_nowait()
    assert payload["club_id"] == "club_1"
    assert payload["tipo"] == "RODADA"
    assert payload["pontos"] == 10.0
