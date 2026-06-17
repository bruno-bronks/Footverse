"""Poisson e Normal: reprodutibilidade + propriedades estatísticas."""

import math

import pytest

from footverse.engine.distributions import inv_norm_cdf, normal, poisson
from footverse.engine.rng import Pcg32


def test_inv_norm_cdf_known_points():
    assert inv_norm_cdf(0.5) == pytest.approx(0.0, abs=1e-9)
    assert inv_norm_cdf(0.975) == pytest.approx(1.959963985, abs=1e-3)
    assert inv_norm_cdf(0.025) == pytest.approx(-1.959963985, abs=1e-3)


def test_poisson_reproducible():
    a = Pcg32.from_key("s")
    b = Pcg32.from_key("s")
    assert [poisson(2.0, a) for _ in range(50)] == [poisson(2.0, b) for _ in range(50)]


def test_poisson_mean_approx_lambda():
    rng = Pcg32.from_key("poisson-mean")
    n, lam = 40000, 2.0
    total = sum(poisson(lam, rng) for _ in range(n))
    assert total / n == pytest.approx(lam, abs=0.05)


def test_poisson_cap_respected():
    rng = Pcg32.from_key("cap")
    assert all(poisson(5.0, rng, cap=4) <= 4 for _ in range(2000))


def test_poisson_zero_lambda():
    rng = Pcg32.from_key("z")
    assert poisson(0.0, rng) == 0


def test_normal_reproducible():
    a = Pcg32.from_key("n")
    b = Pcg32.from_key("n")
    assert [normal(50, 7, a) for _ in range(50)] == [normal(50, 7, b) for _ in range(50)]


def test_normal_mean_and_std():
    rng = Pcg32.from_key("normal-stats")
    n, mu, sigma = 40000, 50.0, 7.0
    xs = [normal(mu, sigma, rng) for _ in range(n)]
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    assert mean == pytest.approx(mu, abs=0.2)
    assert math.sqrt(var) == pytest.approx(sigma, abs=0.2)
