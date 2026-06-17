"""API HTTP (FastAPI) — loop ponta a ponta + mapeamento de erros."""

from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

from footverse.api import create_app
from footverse.world import World

_CORES = ["#000000", "#D4AF37"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(World("TEST_S1")))


def _criar(client, user="user_1", nome="Império FC"):
    r = client.post("/clubs", json={"user_id": user, "nome": nome, "cores": _CORES})
    assert r.status_code == 201
    return r.json()["id"]


def _montar_xi(client, club_id):
    market = client.get("/market").json()
    por_setor = defaultdict(list)
    for mp in sorted(market, key=lambda m: m["valor_fvs"]):
        por_setor[mp["setor"]].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            assert client.post(f"/clubs/{club_id}/transfers",
                               json={"player_id": mp["player_id"]}).status_code == 201
            titulares.append({"player_id": mp["player_id"], "posicao": slot})
    return titulares


# ── leitura / criação ───────────────────────────────────────────────────────
def test_root(client):
    assert client.get("/").json()["app"] == "Footverse"


def test_criar_clube(client):
    r = client.post("/clubs", json={"user_id": "u", "nome": "Clube X", "cores": _CORES})
    assert r.status_code == 201
    body = r.json()
    assert body["divisao"] == "SERIE_D"
    assert body["saldo_fvs"] == 50_000_000


def test_market_not_empty(client):
    assert len(client.get("/market").json()) == 50


# ── erros mapeados a HTTP ────────────────────────────────────────────────────
def test_duplicate_user_409(client):
    _criar(client, "u")
    r = client.post("/clubs", json={"user_id": "u", "nome": "Outro", "cores": _CORES})
    assert r.status_code == 409
    assert r.json()["error"] == "CLUB_ALREADY_EXISTS"


def test_invalid_name_400(client):
    r = client.post("/clubs", json={"user_id": "u", "nome": "ab", "cores": _CORES})
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_NAME"


def test_club_not_found_404(client):
    assert client.get("/clubs/inexistente").status_code == 404


def test_player_not_available_409(client):
    cid = _criar(client)
    pid = client.get("/market").json()[0]["player_id"]
    client.post(f"/clubs/{cid}/transfers", json={"player_id": pid})
    r = client.post(f"/clubs/{cid}/transfers", json={"player_id": pid})
    assert r.status_code == 409
    assert r.json()["error"] == "PLAYER_NOT_AVAILABLE"


def test_player_not_found_404(client):
    cid = _criar(client)
    r = client.post(f"/clubs/{cid}/transfers", json={"player_id": "fantasma"})
    assert r.status_code == 404


def test_score_without_lineup_409(client):
    cid = _criar(client)
    r = client.post(f"/clubs/{cid}/rounds/rod_1")
    assert r.status_code == 409
    assert r.json()["error"] == "NO_VALID_LINEUP"


def test_bad_formation_400(client):
    cid = _criar(client)
    titulares = _montar_xi(client, cid)
    r = client.put(f"/clubs/{cid}/lineup",
                   json={"formacao": "9-0-1", "titulares": titulares, "reservas": []})
    assert r.status_code == 400
    assert r.json()["error"] == "INVALID_FORMATION"


# ── loop completo sobre HTTP ─────────────────────────────────────────────────
def test_full_loop_over_http(client):
    cid = _criar(client)
    titulares = _montar_xi(client, cid)

    r = client.put(f"/clubs/{cid}/lineup",
                   json={"formacao": "4-3-3", "titulares": titulares, "reservas": []})
    assert r.status_code == 200
    assert r.json() == {"club_id": cid, "formacao": "4-3-3", "valida": True, "titulares": 11}

    r = client.post(f"/clubs/{cid}/rounds/rod_1")
    assert r.status_code == 200
    assert len(r.json()["breakdown"]) == 11
    assert isinstance(r.json()["pontos"], float)


def test_score_is_idempotent_over_http(client):
    cid = _criar(client)
    titulares = _montar_xi(client, cid)
    client.put(f"/clubs/{cid}/lineup",
               json={"formacao": "4-3-3", "titulares": titulares, "reservas": []})
    p1 = client.post(f"/clubs/{cid}/rounds/rod_1").json()["pontos"]
    client.post(f"/clubs/{cid}/rounds/rod_1")   # mesma rodada de novo
    pontos_temporada = client.get(f"/clubs/{cid}").json()["pontos_temporada"]
    assert pontos_temporada == p1   # não acumulou em dobro


# ── novos endpoints ─────────────────────────────────────────────────────────
def test_get_squad(client):
    cid = _criar(client)
    titulares = _montar_xi(client, cid)
    r = client.get(f"/clubs/{cid}/squad")
    assert r.status_code == 200
    squad = r.json()
    assert len(squad) == 11
    fields = {"player_id", "posicao", "setor", "ovr", "forma", "idade", "valor_fvs"}
    assert fields <= squad[0].keys()


def test_get_season(client):
    cid = _criar(client)
    r = client.get(f"/clubs/{cid}/season")
    assert r.status_code == 200
    s = r.json()
    assert s["temporada"] == 1
    assert s["divisao"] == "SERIE_D"
    assert s["status"] == "EM_ANDAMENTO"
    assert s["rodadas_jogadas"] == 0
    assert s["rodadas_total"] == 38


def test_get_lineup(client):
    cid = _criar(client)
    titulares = _montar_xi(client, cid)

    # sem escalação → 404
    assert client.get(f"/clubs/{cid}/lineup").status_code == 404

    client.put(f"/clubs/{cid}/lineup",
               json={"formacao": "4-3-3", "titulares": titulares, "reservas": []})
    r = client.get(f"/clubs/{cid}/lineup")
    assert r.status_code == 200
    lineup = r.json()
    assert lineup["formacao"] == "4-3-3"
    assert len(lineup["titulares"]) == 11
    assert all("player_id" in t and "slot" in t for t in lineup["titulares"])


def test_market_refresh(client):
    before = len(client.get("/market").json())
    r = client.post("/market/refresh")
    assert r.status_code == 201
    body = r.json()
    assert body["added"] == 50
    after = len(client.get("/market").json())
    assert after == before + 50
