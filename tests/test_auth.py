"""Testes de autenticação — SPEC-008.

Cobre: registro, validação de chave, chave inválida, e verificação de posse
nos endpoints de escrita quando um token Bearer está presente.
"""

import pytest
from fastapi.testclient import TestClient

from footverse.api import create_app
from footverse.world import World

_CORES = ["#000000", "#FFFFFF"]


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(World("AUTH_TEST_S1")))


# ── registro ───────────────────────────────────────────────────────────────
def test_register_returns_api_key(client):
    r = client.post("/auth/register", json={"user_id": "alice"})
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == "alice"
    assert len(body["api_key"]) > 20


def test_register_second_user_gets_different_key(client):
    k1 = client.post("/auth/register", json={"user_id": "alice"}).json()["api_key"]
    k2 = client.post("/auth/register", json={"user_id": "bob"}).json()["api_key"]
    assert k1 != k2


# ── autenticação via Bearer ────────────────────────────────────────────────
def test_valid_key_accepted_on_write(client):
    raw = client.post("/auth/register", json={"user_id": "alice"}).json()["api_key"]
    r = client.post(
        "/clubs",
        json={"user_id": "alice", "nome": "Alice FC", "cores": _CORES},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 201
    assert r.json()["user_id"] == "alice"


def test_invalid_key_returns_401(client):
    r = client.post(
        "/clubs",
        json={"user_id": "u", "nome": "FC Fantasia", "cores": _CORES},
        headers={"Authorization": "Bearer chave_invalida_123"},
    )
    assert r.status_code == 401


def test_no_key_still_works_compat(client):
    """Sem token: retrocompatível com Fase 1 — usa user_id do body."""
    r = client.post("/clubs", json={"user_id": "legado", "nome": "Legado FC", "cores": _CORES})
    assert r.status_code == 201
    assert r.json()["user_id"] == "legado"


# ── verificação de posse ───────────────────────────────────────────────────
def test_owner_can_buy_player(client):
    raw = client.post("/auth/register", json={"user_id": "bob"}).json()["api_key"]
    cid = client.post(
        "/clubs",
        json={"user_id": "bob", "nome": "Bob FC", "cores": _CORES},
        headers={"Authorization": f"Bearer {raw}"},
    ).json()["id"]
    pid = client.get("/market").json()[0]["player_id"]
    r = client.post(
        f"/clubs/{cid}/transfers",
        json={"player_id": pid},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 201


def test_non_owner_cannot_buy_player(client):
    # alice cria o clube
    raw_a = client.post("/auth/register", json={"user_id": "alice"}).json()["api_key"]
    cid = client.post(
        "/clubs",
        json={"user_id": "alice", "nome": "Alice FC", "cores": _CORES},
        headers={"Authorization": f"Bearer {raw_a}"},
    ).json()["id"]
    # bob tenta comprar no clube da alice
    raw_b = client.post("/auth/register", json={"user_id": "bob"}).json()["api_key"]
    pid = client.get("/market").json()[0]["player_id"]
    r = client.post(
        f"/clubs/{cid}/transfers",
        json={"player_id": pid},
        headers={"Authorization": f"Bearer {raw_b}"},
    )
    assert r.status_code == 403


def test_owner_token_used_over_body_user_id(client):
    """Quando token presente, user_id do corpo é ignorado para posse."""
    raw_a = client.post("/auth/register", json={"user_id": "alice"}).json()["api_key"]
    # alice cria clube passando user_id="outro" no body — deve ser ignorado
    r = client.post(
        "/clubs",
        json={"user_id": "outro", "nome": "Alice Robs FC", "cores": _CORES},
        headers={"Authorization": f"Bearer {raw_a}"},
    )
    assert r.status_code == 201
    assert r.json()["user_id"] == "alice"
