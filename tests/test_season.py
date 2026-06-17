"""Temporada e progressão — SPEC-006 (liga-sombra, classificação, encerramento)."""

import pytest

from footverse import config
from footverse.engine.league import (
    StandingRow,
    classificar,
    npc_round_score,
    npc_standings,
)
from footverse.state.economy import criar_clube
from footverse.state.models import SEASON_REWARD
from footverse.state.season import (
    SEASON_ALREADY_CLOSED,
    SEASON_FULL,
    SEASON_NOT_FINISHED,
    SeasonError,
    SeasonState,
    atualizar_forma_elenco,
    encerrar_temporada,
    forma_para,
    proxima_temporada,
    registrar_rodada,
)
from footverse.state.store import Store

_CORES = ["#000000", "#D4AF37"]


def _club(divisao: str = "SERIE_D"):
    s = Store()
    c = criar_clube(s, "u", "Clube X", _CORES)
    c.divisao = divisao
    return s, c


def _season(store, club, divisao=None, secret="SEC"):
    return SeasonState(season_secret=secret, temporada=1,
                       divisao=divisao or club.divisao, club_id=club.id)


def _play(store, season, score):
    for i in range(config.RODADAS_POR_TEMPORADA):
        registrar_rodada(store, season, f"rod_{i}", score)


# ───────────────────────────── liga-sombra (pura) ──────────────────────────
def test_npc_round_score_reproducible_and_in_range():
    a = npc_round_score("SEC", "SERIE_D", 1, "npc_SERIE_D_0", 5)
    b = npc_round_score("SEC", "SERIE_D", 1, "npc_SERIE_D_0", 5)
    assert a == b
    assert 0 <= a <= 20000   # clamp 0..200 pts → centésimos


def test_npc_standings_count_and_reproducible():
    a = npc_standings("SEC", "SERIE_D", 1)
    b = npc_standings("SEC", "SERIE_D", 1)
    assert len(a) == config.CLUBES_POR_DIVISAO - 1
    assert a == b


def test_classificar_strict_total_order_on_ties():
    rows = [StandingRow(f"c{i}", "NPC", 1000, 100) for i in range(5)]  # tudo empatado
    ordem = classificar(rows, "SEC")
    ids = [r.club_id for r in ordem]
    assert len(set(ids)) == 5            # nenhuma linha perdida
    assert classificar(rows, "SEC") == ordem  # determinístico


def test_classificar_sorts_by_points_desc():
    rows = [StandingRow("a", "NPC", 100, 10), StandingRow("b", "NPC", 300, 10),
            StandingRow("c", "NPC", 200, 10)]
    assert [r.club_id for r in classificar(rows, "SEC")] == ["b", "c", "a"]


# ───────────────────────────── acúmulo de rodadas ──────────────────────────
def test_registrar_rodada_accumulates():
    store, club = _club()
    season = _season(store, club)
    registrar_rodada(store, season, "rod_1", 7000)
    registrar_rodada(store, season, "rod_2", 8000)
    assert club.pontos_temporada_centi == 15000
    assert season.rodada_atual == 2


def test_registrar_rodada_is_idempotent_by_id():
    # SPEC-004 §5-6: recalcular a mesma rodada não acumula
    store, club = _club()
    season = _season(store, club)
    registrar_rodada(store, season, "rod_1", 7000)
    registrar_rodada(store, season, "rod_1", 7000)   # mesma rodada de novo
    registrar_rodada(store, season, "rod_1", 9999)   # mesmo id, valor diferente
    assert club.pontos_temporada_centi == 7000
    assert season.rodada_atual == 1


def test_cannot_register_beyond_season_length():
    store, club = _club()
    season = _season(store, club)
    _play(store, season, 7000)
    with pytest.raises(SeasonError) as e:
        registrar_rodada(store, season, "rod_extra", 7000)
    assert e.value.code == SEASON_FULL


def test_cannot_close_before_finished():
    store, club = _club()
    season = _season(store, club)
    registrar_rodada(store, season, "rod_1", 7000)
    with pytest.raises(SeasonError) as e:
        encerrar_temporada(store, season)
    assert e.value.code == SEASON_NOT_FINISHED


# ───────────────────────────── progressão ──────────────────────────────────
def test_strong_team_promoted_from_serie_d():
    store, club = _club("SERIE_D")
    season = _season(store, club)
    _play(store, season, 9000)            # bem acima da média NPC de D (~6800)
    r = encerrar_temporada(store, season)
    assert r.resultado == "PROMOVIDO"
    assert r.divisao_nova == "SERIE_C"
    assert club.divisao == "SERIE_C"
    # promoção é monotônica (sobe exatamente um nível)
    assert config.DIVISOES.index("SERIE_C") == config.DIVISOES.index("SERIE_D") - 1


def test_reward_is_posted_to_ledger():
    store, club = _club("SERIE_D")
    season = _season(store, club)
    _play(store, season, 9000)
    r = encerrar_temporada(store, season)
    rewards = [e for e in store.ledger if e.tipo == SEASON_REWARD]
    assert len(rewards) == 1
    assert rewards[0].valor_fvs == r.premiacao_fvs
    assert club.saldo_fvs == store.ledger_balance(club.id)


def test_champion_in_serie_a_stays():
    store, club = _club("SERIE_A")
    season = _season(store, club, "SERIE_A")
    _play(store, season, 20000)           # pontuação máxima → 1º lugar
    r = encerrar_temporada(store, season)
    assert r.resultado == "CAMPEAO"
    assert r.divisao_nova == "SERIE_A"
    assert club.divisao == "SERIE_A"


def test_bottom_of_serie_d_is_not_relegated():
    store, club = _club("SERIE_D")
    season = _season(store, club)
    _play(store, season, 0)               # zera → última posição
    r = encerrar_temporada(store, season)
    assert r.posicao_final == config.CLUBES_POR_DIVISAO
    assert r.resultado == "PERMANECE"
    assert club.divisao == "SERIE_D"


# ───────────────────────────── idempotência ────────────────────────────────
def test_closing_twice_is_idempotent():
    store, club = _club("SERIE_D")
    season = _season(store, club)
    _play(store, season, 9000)
    encerrar_temporada(store, season)
    divisao_apos = club.divisao
    with pytest.raises(SeasonError) as e:
        encerrar_temporada(store, season)
    assert e.value.code == SEASON_ALREADY_CLOSED
    assert club.divisao == divisao_apos                                  # não move de novo
    assert len([x for x in store.ledger if x.tipo == SEASON_REWARD]) == 1  # não premia em dobro


# ───────────────────────────── rollover + forma ────────────────────────────
def test_proxima_temporada_uses_new_division():
    store, club = _club("SERIE_D")
    season = _season(store, club)
    _play(store, season, 9000)
    encerrar_temporada(store, season)     # → SERIE_C
    nova = proxima_temporada(store, season)
    assert nova.temporada == 2
    assert nova.divisao == "SERIE_C"
    assert nova.rodada_atual == 0


def test_forma_is_deterministic_and_in_range():
    a = forma_para("SEC", "club_1", "p1", 2)
    b = forma_para("SEC", "club_1", "p1", 2)
    assert a == b
    assert config.FORMA_MIN <= a <= config.FORMA_MAX


def test_atualizar_forma_elenco_applies_to_owned():
    from footverse.domain.player import ATRIBUTOS, Player
    from footverse.engine.market_gen import MarketPlayer

    store, club = _club()
    attrs = {x: 50 for x in ATRIBUTOS}
    mp = MarketPlayer(player=Player("p1", "ATA", attrs, 25, forma=70),
                      ovr=50, valor_fvs=1, setor="ATA")
    store.load_market([mp])
    store.ownership["p1"] = club.id
    atualizar_forma_elenco(store, "SEC", club.id, 2)
    assert store.catalog["p1"].player.forma == forma_para("SEC", club.id, "p1", 2)
