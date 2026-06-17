"""Valor de mercado: ancoragem da régua e invariantes (SPEC-005 §9)."""

import pytest

from footverse import config
from footverse.engine.valuation import market_value


@pytest.mark.parametrize("ovr,idade,esperado", [
    (55, 26, 3_000_000),    # âncora central
    (75, 26, 20_200_000),   # craque (âncora de escala)
    (45, 22, 1_100_000),
    (35, 33, 300_000),
    (62, 30, 5_000_000),
])
def test_anchors(ovr, idade, esperado):
    assert market_value(ovr, idade) == esperado


def test_anchor_craque_in_band():
    assert 20_000_000 <= market_value(75, 26) <= 20_500_000


def test_floor_never_below_piso():
    for ovr in range(20, 100):
        for idade in (16, 20, 26, 30, 35, 40):
            assert market_value(ovr, idade) >= config.PISO_VALOR


def test_monotonic_in_ovr():
    for idade in (20, 26, 33):
        vals = [market_value(ovr, idade) for ovr in range(35, 81)]
        assert all(b >= a for a, b in zip(vals, vals[1:]))


def test_deterministic():
    assert market_value(60, 25) == market_value(60, 25)
