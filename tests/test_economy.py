"""Ledger e ações de clube — SPEC-001 / SPEC-002."""

import pytest

from footverse import config
from footverse.domain.player import ATRIBUTOS, Player
from footverse.engine.market_gen import MarketPlayer, generate_market
from footverse.state.economy import (
    CLUB_ALREADY_EXISTS,
    CLUB_NOT_FOUND,
    INSUFFICIENT_FUNDS,
    INVALID_COLOR,
    INVALID_NAME,
    PLAYER_NOT_AVAILABLE,
    PLAYER_NOT_FOUND,
    SQUAD_FULL,
    TOO_MANY_COLORS,
    EconomyError,
    comprar_jogador,
    criar_clube,
)
from footverse.state.models import INITIAL_GRANT
from footverse.state.store import Store

_CORES = ["#000000", "#D4AF37"]


def _mp(pid: str, valor: int, setor: str = "ATA", pos: str = "ATA") -> MarketPlayer:
    attrs = {a: 50 for a in ATRIBUTOS}
    p = Player(id=pid, posicao_natural=pos, atributos=attrs, idade=25)
    return MarketPlayer(player=p, ovr=50, valor_fvs=valor, setor=setor)


def _store_with(players: list[MarketPlayer]) -> Store:
    s = Store()
    s.load_market(players)
    return s


# ───────────────────────────── SPEC-001 ────────────────────────────────────
def test_criar_clube_grants_initial_budget():
    s = Store()
    club = criar_clube(s, "user_abc", "Império FC", _CORES)
    assert club.saldo_fvs == config.ORCAMENTO_INICIAL_FVS
    assert club.divisao == "SERIE_D"
    assert club.pontos_temporada_centi == 0


def test_initial_grant_is_single_ledger_entry():
    s = Store()
    club = criar_clube(s, "user_abc", "Império FC", _CORES)
    grants = [e for e in s.ledger if e.club_id == club.id and e.tipo == INITIAL_GRANT]
    assert len(grants) == 1
    assert grants[0].valor_fvs == config.ORCAMENTO_INICIAL_FVS


@pytest.mark.parametrize("nome", ["ab", "x" * 41])
def test_invalid_name(nome):
    with pytest.raises(EconomyError) as e:
        criar_clube(Store(), "u", nome, _CORES)
    assert e.value.code == INVALID_NAME


def test_too_many_colors():
    with pytest.raises(EconomyError) as e:
        criar_clube(Store(), "u", "Clube X", ["#fff", "#000", "#abc", "#123"])
    assert e.value.code == TOO_MANY_COLORS


@pytest.mark.parametrize("cores", [[], ["vermelho"], ["#xyz123"]])
def test_invalid_color(cores):
    with pytest.raises(EconomyError) as e:
        criar_clube(Store(), "u", "Clube X", cores)
    assert e.value.code == INVALID_COLOR


def test_one_club_per_user():
    s = Store()
    criar_clube(s, "user_abc", "Clube 1", _CORES)
    with pytest.raises(EconomyError) as e:
        criar_clube(s, "user_abc", "Clube 2", _CORES)
    assert e.value.code == CLUB_ALREADY_EXISTS


# ───────────────────────────── SPEC-002 ────────────────────────────────────
def test_compra_debita_saldo():
    s = _store_with([_mp("p1", 20_000_000)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    r = comprar_jogador(s, club.id, "p1")
    assert r.valor_fvs == 20_000_000
    assert r.saldo_anterior == config.ORCAMENTO_INICIAL_FVS
    assert r.saldo_final == config.ORCAMENTO_INICIAL_FVS - 20_000_000
    assert club.saldo_fvs == r.saldo_final
    assert s.ownership["p1"] == club.id
    assert "p1" not in [pid for pid, o in s.ownership.items() if o is None]


def test_roadmap_example_30M_minus_20M_equals_10M():
    # clube chega a 30M após uma compra, então compra um 20M → 10M (caso do roadmap)
    s = _store_with([_mp("p1", 20_000_000), _mp("p2", 20_000_000)])
    club = criar_clube(s, "u", "Clube X", _CORES)  # 50M
    comprar_jogador(s, club.id, "p1")               # → 30M
    r = comprar_jogador(s, club.id, "p2")           # saldo_anterior 30M
    assert r.saldo_anterior == 30_000_000
    assert r.saldo_final == 10_000_000


def test_saldo_final_invariant():
    s = _store_with([_mp("p1", 7_500_000)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    r = comprar_jogador(s, club.id, "p1")
    assert r.saldo_final == r.saldo_anterior - r.valor_fvs


def test_club_not_found():
    s = _store_with([_mp("p1", 1_000_000)])
    with pytest.raises(EconomyError) as e:
        comprar_jogador(s, "club_inexistente", "p1")
    assert e.value.code == CLUB_NOT_FOUND


def test_player_not_found():
    s = Store()
    club = criar_clube(s, "u", "Clube X", _CORES)
    with pytest.raises(EconomyError) as e:
        comprar_jogador(s, club.id, "fantasma")
    assert e.value.code == PLAYER_NOT_FOUND


def test_player_not_available_after_bought():
    s = _store_with([_mp("p1", 1_000_000)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    comprar_jogador(s, club.id, "p1")
    with pytest.raises(EconomyError) as e:
        comprar_jogador(s, club.id, "p1")
    assert e.value.code == PLAYER_NOT_AVAILABLE


def test_insufficient_funds():
    s = _store_with([_mp("p1", config.ORCAMENTO_INICIAL_FVS + 1)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    with pytest.raises(EconomyError) as e:
        comprar_jogador(s, club.id, "p1")
    assert e.value.code == INSUFFICIENT_FUNDS


def test_squad_full(monkeypatch):
    monkeypatch.setattr(config, "MAX_ELENCO", 2)
    s = _store_with([_mp(f"p{i}", 1_000_000) for i in range(3)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    comprar_jogador(s, club.id, "p0")
    comprar_jogador(s, club.id, "p1")
    with pytest.raises(EconomyError) as e:
        comprar_jogador(s, club.id, "p2")
    assert e.value.code == SQUAD_FULL


# ───────────────────────────── invariante de reconciliação ─────────────────
def test_ledger_reconciles_with_balance():
    s = _store_with([_mp("p1", 3_000_000), _mp("p2", 5_000_000)])
    club = criar_clube(s, "u", "Clube X", _CORES)
    comprar_jogador(s, club.id, "p1")
    comprar_jogador(s, club.id, "p2")
    assert club.saldo_fvs == s.ledger_balance(club.id)


def test_integration_with_generated_market():
    s = Store()
    s.load_market(generate_market("SEASON_SECRET"))
    club = criar_clube(s, "u", "Clube X", _CORES)
    barato = min(s.catalog.values(), key=lambda mp: mp.valor_fvs)
    comprar_jogador(s, club.id, barato.player.id)
    assert s.ownership[barato.player.id] == club.id
    assert club.saldo_fvs == s.ledger_balance(club.id)
