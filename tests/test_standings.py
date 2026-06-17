"""Testes de standings — SPEC-007.

Cobre: endpoint público de classificação, múltiplos clubes reais na mesma
divisão, e integração com o encerramento de temporada.
"""

from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from footverse.api import create_app
from footverse.world import World

_CORES = ["#FF0000", "#000000"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(World("STANDINGS_TEST")))


def _criar(client, user: str, nome: str) -> str:
    r = client.post("/clubs", json={"user_id": user, "nome": nome, "cores": _CORES})
    assert r.status_code == 201
    return r.json()["id"]


def _montar_xi(client, club_id: str) -> list[dict]:
    market = client.get("/market").json()
    por_setor = defaultdict(list)
    for mp in sorted(market, key=lambda m: m["valor_fvs"]):
        por_setor[mp["setor"]].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            client.post(f"/clubs/{club_id}/transfers", json={"player_id": mp["player_id"]})
            titulares.append({"player_id": mp["player_id"], "posicao": slot})
    return titulares


# ── standings básicos ──────────────────────────────────────────────────────
def test_standings_empty_division(client):
    r = client.get("/divisions/SERIE_A/standings")
    assert r.status_code == 200
    assert r.json() == []


def test_standings_single_club(client):
    _criar(client, "u1", "Clube Alpha")
    r = client.get("/divisions/SERIE_D/standings")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["posicao"] == 1
    assert rows[0]["nome"] == "Clube Alpha"
    assert rows[0]["pontos"] == 0.0


def test_standings_fields_present(client):
    _criar(client, "u1", "Alpha FC")
    row = client.get("/divisions/SERIE_D/standings").json()[0]
    expected = {"posicao", "club_id", "nome", "divisao", "pontos",
                "temporada", "rodadas_jogadas", "status"}
    assert expected <= row.keys()


def test_standings_ordered_by_points(client):
    cid1 = _criar(client, "u1", "Forte FC")
    cid2 = _criar(client, "u2", "Fraco FC")

    # cid1 marca uma rodada, cid2 fica com zero
    ti1 = _montar_xi(client, cid1)
    client.put(f"/clubs/{cid1}/lineup",
               json={"formacao": "4-3-3", "titulares": ti1, "reservas": []})
    client.post(f"/clubs/{cid1}/rounds/r1")

    rows = client.get("/divisions/SERIE_D/standings").json()
    assert rows[0]["club_id"] == cid1
    assert rows[1]["club_id"] == cid2
    assert rows[0]["pontos"] > rows[1]["pontos"]


def test_standings_two_clubs_same_division(client):
    _criar(client, "u1", "Time 1")
    _criar(client, "u2", "Time 2")
    rows = client.get("/divisions/SERIE_D/standings").json()
    assert len(rows) == 2
    positions = [r["posicao"] for r in rows]
    assert positions == [1, 2]


# ── standings com rodadas jogadas ──────────────────────────────────────────
def test_rodadas_jogadas_updated_in_standings(client):
    cid = _criar(client, "u1", "Ativo FC")
    ti = _montar_xi(client, cid)
    client.put(f"/clubs/{cid}/lineup",
               json={"formacao": "4-3-3", "titulares": ti, "reservas": []})
    client.post(f"/clubs/{cid}/rounds/r1")
    client.post(f"/clubs/{cid}/rounds/r2")

    rows = client.get("/divisions/SERIE_D/standings").json()
    assert rows[0]["rodadas_jogadas"] == 2


# ── clubes em divisões diferentes não aparecem juntos ────────────────────
def test_standings_isolates_by_division(client):
    _criar(client, "u1", "Divisao D")   # começa em SERIE_D
    rows_a = client.get("/divisions/SERIE_A/standings").json()
    rows_d = client.get("/divisions/SERIE_D/standings").json()
    assert len(rows_a) == 0
    assert len(rows_d) == 1
