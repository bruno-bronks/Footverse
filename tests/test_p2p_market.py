"""Testes de mercado P2P — transferências entre clubes humanos.

Cobre: listar jogador à venda, cancelar listagem, comprar de humano (transferência
de FV$), erros de posse/saldo/estado, e invariante do ledger pós-P2P.
"""

import pytest
from fastapi.testclient import TestClient

from footverse.api import create_app
from footverse.world import World

_CORES = ["#1e40af", "#b91c1c"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(World("P2P_TEST")))


def _criar(client, user: str, nome: str) -> str:
    r = client.post("/clubs", json={"user_id": user, "nome": nome, "cores": _CORES})
    assert r.status_code == 201
    return r.json()["id"]


def _comprar_elenco(client, club_id: str, n: int = 11) -> list[str]:
    """Compra os n jogadores mais baratos do mercado NPC. Retorna player_ids."""
    market = client.get("/market").json()
    npc = [m for m in market if m["vendedor_club_id"] is None]
    baratos = sorted(npc, key=lambda m: m["valor_fvs"])[:n]
    ids = []
    for mp in baratos:
        r = client.post(f"/clubs/{club_id}/transfers", json={"player_id": mp["player_id"]})
        assert r.status_code == 201
        ids.append(mp["player_id"])
    return ids


# ── listar à venda ─────────────────────────────────────────────────────────
def test_listar_jogador_aparece_no_mercado(client):
    cid = _criar(client, "vendedor", "Clube Vendedor")
    pids = _comprar_elenco(client, cid, 1)

    r = client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 3_000_000})
    assert r.status_code == 201
    body = r.json()
    assert body["player_id"] == pids[0]
    assert body["preco_fvs"] == 3_000_000

    market = client.get("/market").json()
    listado = next((m for m in market if m["player_id"] == pids[0]), None)
    assert listado is not None
    assert listado["vendedor_club_id"] == cid


def test_get_listing_endpoint(client):
    cid = _criar(client, "v1", "V1 FC")
    pids = _comprar_elenco(client, cid, 1)
    client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 5_000_000})

    r = client.get(f"/clubs/{cid}/squad/{pids[0]}/list")
    assert r.status_code == 200
    assert r.json()["preco_fvs"] == 5_000_000


def test_cancelar_listagem(client):
    cid = _criar(client, "v2", "V2 FC")
    pids = _comprar_elenco(client, cid, 1)
    client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 2_000_000})

    r = client.delete(f"/clubs/{cid}/squad/{pids[0]}/list")
    assert r.status_code == 204

    market = client.get("/market").json()
    assert not any(m["player_id"] == pids[0] for m in market)


def test_listar_jogador_nao_proprio_403(client):
    cid1 = _criar(client, "a1", "A1 FC")
    cid2 = _criar(client, "b1", "B1 FC")
    pids = _comprar_elenco(client, cid1, 1)

    r = client.post(f"/clubs/{cid2}/squad/{pids[0]}/list", json={"preco_fvs": 1_000_000})
    assert r.status_code in (400, 403)


def test_listar_mesmo_jogador_duas_vezes_409(client):
    cid = _criar(client, "v3", "V3 FC")
    pids = _comprar_elenco(client, cid, 1)
    client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 1_000_000})
    r = client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 2_000_000})
    assert r.status_code == 409


# ── compra P2P ────────────────────────────────────────────────────────────
def test_compra_p2p_transfere_fvs(client):
    cid_v = _criar(client, "vend", "Vendedor FC")
    cid_c = _criar(client, "comp", "Comprador FC")
    pids = _comprar_elenco(client, cid_v, 1)

    preco = 10_000_000
    client.post(f"/clubs/{cid_v}/squad/{pids[0]}/list", json={"preco_fvs": preco})

    saldo_v_antes = client.get(f"/clubs/{cid_v}").json()["saldo_fvs"]
    saldo_c_antes = client.get(f"/clubs/{cid_c}").json()["saldo_fvs"]

    r = client.post(f"/clubs/{cid_c}/transfers", json={"player_id": pids[0]})
    assert r.status_code == 201
    body = r.json()
    assert body["tipo"] == "P2P"
    assert body["vendedor_club_id"] == cid_v

    saldo_v_depois = client.get(f"/clubs/{cid_v}").json()["saldo_fvs"]
    saldo_c_depois = client.get(f"/clubs/{cid_c}").json()["saldo_fvs"]

    assert saldo_v_depois == saldo_v_antes + preco
    assert saldo_c_depois == saldo_c_antes - preco


def test_compra_p2p_transfere_posse(client):
    cid_v = _criar(client, "vend2", "Vendedor2 FC")
    cid_c = _criar(client, "comp2", "Comprador2 FC")
    pids = _comprar_elenco(client, cid_v, 1)

    client.post(f"/clubs/{cid_v}/squad/{pids[0]}/list", json={"preco_fvs": 1_000_000})
    client.post(f"/clubs/{cid_c}/transfers", json={"player_id": pids[0]})

    squad_c = [p["player_id"] for p in client.get(f"/clubs/{cid_c}/squad").json()]
    squad_v = [p["player_id"] for p in client.get(f"/clubs/{cid_v}/squad").json()]

    assert pids[0] in squad_c
    assert pids[0] not in squad_v


def test_nao_pode_comprar_proprio_jogador(client):
    cid = _criar(client, "auto", "Auto FC")
    pids = _comprar_elenco(client, cid, 1)
    client.post(f"/clubs/{cid}/squad/{pids[0]}/list", json={"preco_fvs": 1_000_000})

    r = client.post(f"/clubs/{cid}/transfers", json={"player_id": pids[0]})
    assert r.status_code == 400


def test_compra_p2p_retira_do_mercado(client):
    cid_v = _criar(client, "v4", "V4 FC")
    cid_c = _criar(client, "c4", "C4 FC")
    pids = _comprar_elenco(client, cid_v, 1)
    client.post(f"/clubs/{cid_v}/squad/{pids[0]}/list", json={"preco_fvs": 1_000_000})
    client.post(f"/clubs/{cid_c}/transfers", json={"player_id": pids[0]})

    market = client.get("/market").json()
    assert not any(m["player_id"] == pids[0] for m in market)


def test_saldo_insuficiente_p2p_402(client):
    cid_v = _criar(client, "v5", "V5 FC")
    cid_c = _criar(client, "c5", "C5 FC")
    pids = _comprar_elenco(client, cid_v, 1)

    # esvazia quase todo o saldo do comprador comprando elenco caro
    _comprar_elenco(client, cid_c, 11)
    saldo = client.get(f"/clubs/{cid_c}").json()["saldo_fvs"]

    client.post(f"/clubs/{cid_v}/squad/{pids[0]}/list",
                json={"preco_fvs": saldo + 1_000_000})

    r = client.post(f"/clubs/{cid_c}/transfers", json={"player_id": pids[0]})
    assert r.status_code == 402


# ── invariante do ledger ───────────────────────────────────────────────────
def test_ledger_conserva_dinheiro_na_p2p(client):
    """FV$ totais do sistema não mudam numa transação P2P."""
    cid_v = _criar(client, "lv", "Ledger Vendedor")
    cid_c = _criar(client, "lc", "Ledger Comprador")

    # captura o preço NPC antes de comprar
    market = client.get("/market").json()
    npc_baratos = sorted([m for m in market if m["vendedor_club_id"] is None],
                         key=lambda m: m["valor_fvs"])
    preco_npc = npc_baratos[0]["valor_fvs"]
    pid = npc_baratos[0]["player_id"]

    # cid_v compra o jogador do mercado NPC (sink: FV$ sai de circulação)
    client.post(f"/clubs/{cid_v}/transfers", json={"player_id": pid})

    # total após compra NPC (a única saída de FV$ do sistema)
    saldo_base = (
        client.get(f"/clubs/{cid_v}").json()["saldo_fvs"] +
        client.get(f"/clubs/{cid_c}").json()["saldo_fvs"]
    )

    # P2P: cid_v lista o jogador, cid_c compra
    preco_p2p = 8_000_000
    client.post(f"/clubs/{cid_v}/squad/{pid}/list", json={"preco_fvs": preco_p2p})
    client.post(f"/clubs/{cid_c}/transfers", json={"player_id": pid})

    saldo_apos_p2p = (
        client.get(f"/clubs/{cid_v}").json()["saldo_fvs"] +
        client.get(f"/clubs/{cid_c}").json()["saldo_fvs"]
    )

    # P2P não cria nem destrói FV$ — total deve ser idêntico
    assert saldo_apos_p2p == saldo_base


def test_mercado_npc_nao_tem_vendedor(client):
    market = client.get("/market").json()
    assert all(m["vendedor_club_id"] is None for m in market)
