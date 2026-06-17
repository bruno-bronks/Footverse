"""Posições e formações — invariantes da SPEC-003."""

from footverse.domain.positions import (
    FORMACOES,
    POSICOES,
    SETOR,
    required_multiset,
)


def test_every_formation_has_11_players():
    for nome, counts in FORMACOES.items():
        assert sum(counts.values()) == 11, nome


def test_every_formation_has_exactly_one_goalkeeper():
    for nome, counts in FORMACOES.items():
        assert counts["GOL"] == 1, nome


def test_formations_use_known_positions():
    for counts in FORMACOES.values():
        assert set(counts) == set(POSICOES)


def test_formation_multisets_are_distinct():
    multisets = [tuple(sorted(required_multiset(f).items())) for f in FORMACOES]
    assert len(multisets) == len(set(multisets))  # nenhuma ambiguidade


def test_every_position_has_a_sector():
    for p in POSICOES:
        assert SETOR[p] in {"GOL", "DEF", "MEI", "ATA"}
