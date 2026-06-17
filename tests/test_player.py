"""Atributos e OVR — invariantes da SPEC-005 §2."""

import pytest

from footverse.domain.player import ATRIBUTOS, OVR_WEIGHTS, overall


def test_weight_rows_sum_to_one():
    for pos, w in OVR_WEIGHTS.items():
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-9), pos


def test_weights_cover_all_attributes():
    for w in OVR_WEIGHTS.values():
        assert set(w) == set(ATRIBUTOS)


def test_flat_attributes_give_same_ovr():
    # como os pesos somam 1, atributos uniformes em X resultam em OVR X
    for pos in OVR_WEIGHTS:
        attrs = {a: 55 for a in ATRIBUTOS}
        assert overall(attrs, pos) == 55


def test_ovr_is_derived_and_deterministic():
    attrs = {"PAC": 60, "FIN": 80, "PAS": 50, "DRI": 70, "DEF": 30, "FIS": 65, "GK": 10}
    assert overall(attrs, "ATA") == overall(attrs, "ATA")
