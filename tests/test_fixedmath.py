"""Os transcendentais congelados batem com a libm (validação de correção)."""

import math

import pytest

from footverse.engine.fixedmath import frozen_exp, frozen_ln


@pytest.mark.parametrize("x", [-6.0, -2.5, -1.0, -0.3, 0.0, 0.3, 1.0, 2.5, 6.0, 12.0])
def test_frozen_exp_matches_libm(x):
    assert frozen_exp(x) == pytest.approx(math.exp(x), rel=1e-12)


@pytest.mark.parametrize("x", [1e-6, 0.02425, 0.1, 0.5, 1.0, 2.0, 7.0, 100.0, 1e6])
def test_frozen_ln_matches_libm(x):
    assert frozen_ln(x) == pytest.approx(math.log(x), rel=1e-12)


def test_frozen_ln_rejects_nonpositive():
    with pytest.raises(ValueError):
        frozen_ln(0.0)


def test_frozen_exp_is_deterministic():
    assert frozen_exp(-2.0) == frozen_exp(-2.0)
