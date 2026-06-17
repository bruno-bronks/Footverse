"""Pontuação por jogador e por rodada — SPEC-005 §4-5 / SPEC-004."""

from footverse.domain.player import ATRIBUTOS, Player
from footverse.engine.scoring import (
    TitularSlot,
    compute_nota,
    points_centi,
    score_round,
)


# ───────────────────────────── conversão pura (exemplos da spec) ────────────
def test_points_example_attacker():
    # ATA, nota 8.4, 1 gol, 1 assistência → 19.8 pts → 1980 centi
    assert points_centi("ATA", 8.4, gols=1, assistencias=1,
                        clean_sheet=False, defesas=0, gols_sofridos=0) == 1980


def test_points_example_goalkeeper():
    # GOL, nota 7.0, clean sheet, 4 defesas → 13.0 pts → 1300 centi
    assert points_centi("GOL", 7.0, gols=0, assistencias=0,
                        clean_sheet=True, defesas=4, gols_sofridos=0) == 1300


def test_clean_sheet_only_for_defensive_sectors():
    # mesmo com clean sheet, um ATA não ganha o bônus SG
    assert points_centi("ATA", 5.0, 0, 0, clean_sheet=True, defesas=0, gols_sofridos=0) == 0
    assert points_centi("ZAG", 5.0, 0, 0, clean_sheet=True, defesas=0, gols_sofridos=0) == 500


def test_goals_conceded_penalty_only_gol_zag():
    assert points_centi("ZAG", 5.0, 0, 0, clean_sheet=False, defesas=0, gols_sofridos=2) == -200
    assert points_centi("LAT", 5.0, 0, 0, clean_sheet=False, defesas=0, gols_sofridos=2) == 0


def test_compute_nota_bounds():
    assert compute_nota(50, 50, 0.0) == 5.0
    assert 0.0 <= compute_nota(35, 0, -1.0) <= 10.0
    assert 0.0 <= compute_nota(70, 100, 1.0) <= 10.0


# ───────────────────────────── rodada completa (4-3-3) ─────────────────────
def _mk(pid: str, **over: int) -> Player:
    attrs = {a: 55 for a in ATRIBUTOS}
    attrs.update(over)
    return Player(id=pid, posicao_natural="MEI", atributos=attrs, idade=25, forma=70)


def _xi_433() -> list[TitularSlot]:
    spec = [
        ("gk", "GOL"), ("z1", "ZAG"), ("z2", "ZAG"), ("l1", "LAT"), ("l2", "LAT"),
        ("v1", "VOL"), ("m1", "MEI"), ("m2", "MEI"), ("e1", "EXT"), ("e2", "EXT"),
        ("a1", "ATA"),
    ]
    return [TitularSlot(_mk(pid, GK=70, FIN=70, PAS=70), slot) for pid, slot in spec]


def test_round_is_reproducible():
    a = score_round(_xi_433(), "SERIE_D", "SECRET", "club_123", "rod_05")
    b = score_round(_xi_433(), "SERIE_D", "SECRET", "club_123", "rod_05")
    assert a == b


def test_club_total_equals_sum_of_breakdown():
    rs = score_round(_xi_433(), "SERIE_D", "SECRET", "club_123", "rod_05")
    assert rs.pontos_centi == sum(ps.pts_centi for ps in rs.breakdown)
    assert len(rs.breakdown) == 11


def test_event_caps_and_nota_range():
    rs = score_round(_xi_433(), "SERIE_D", "SECRET", "club_123", "rod_05")
    for ps in rs.breakdown:
        assert 0.0 <= ps.nota <= 10.0
        assert ps.gols <= 4
        assert ps.assistencias <= 3


def test_clean_sheet_consistent_across_team():
    rs = score_round(_xi_433(), "SERIE_D", "SECRET", "club_123", "rod_05")
    sofridos = {ps.gols_sofridos for ps in rs.breakdown}
    clean = {ps.clean_sheet for ps in rs.breakdown}
    assert len(sofridos) == 1            # evento de time: igual para todos
    assert len(clean) == 1
    assert next(iter(clean)) == (next(iter(sofridos)) == 0)


def test_different_seed_changes_result():
    a = score_round(_xi_433(), "SERIE_D", "SECRET_A", "club_123", "rod_05")
    b = score_round(_xi_433(), "SERIE_D", "SECRET_B", "club_123", "rod_05")
    assert a.pontos_centi != b.pontos_centi
