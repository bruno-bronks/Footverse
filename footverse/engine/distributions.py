"""Distribuições amostradas de forma determinística.

- Poisson via método de Knuth, usando `frozen_exp` (não a libm).
- Normal via inversa da CDF (algoritmo de Acklam), usando `frozen_ln` + `sqrt`
  (IEEE-754 correta por ULP). Evita Box-Muller (sin/cos) por determinismo.

Toda aleatoriedade vem de um `Pcg32` passado pelo chamador, então o resultado
é reprodutível a partir da seed. Ver SPEC-005 §8 / SPEC-006 §7.
"""

from __future__ import annotations

import math

from .fixedmath import frozen_exp, frozen_ln
from .rng import Pcg32

# coeficientes de Acklam para a inversa da CDF normal
_A = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
      1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
_B = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
      6.680131188771972e+01, -1.328068155288572e+01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
      -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
      3.754408661907416e+00)
_P_LOW = 0.02425
_P_HIGH = 1.0 - _P_LOW


def inv_norm_cdf(u: float) -> float:
    """Inversa da CDF da normal padrão para u em (0, 1)."""
    if u < _P_LOW:
        q = math.sqrt(-2.0 * frozen_ln(u))
        return (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
               ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)
    if u <= _P_HIGH:
        q = u - 0.5
        r = q * q
        return (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
               (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1.0)
    q = math.sqrt(-2.0 * frozen_ln(1.0 - u))
    return -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
            ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1.0)


def normal(mu: float, sigma: float, rng: Pcg32) -> float:
    """Amostra de Normal(mu, sigma) determinística."""
    return mu + sigma * inv_norm_cdf(rng.random_open())


def normal_clamped_int(mu: float, sigma: float, lo: int, hi: int, rng: Pcg32) -> int:
    """Normal arredondada (half-up) e travada em [lo, hi]."""
    x = normal(mu, sigma, rng)
    v = int(math.floor(x + 0.5))
    return max(lo, min(hi, v))


def poisson(lam: float, rng: Pcg32, cap: int | None = None) -> int:
    """Amostra de Poisson(lam) por Knuth. `cap` limita o retorno (tetos das specs)."""
    if lam <= 0.0:
        return 0
    target = frozen_exp(-lam)
    k = 0
    p = 1.0
    while True:
        k += 1
        p *= rng.random()
        if p <= target:
            result = k - 1
            return result if cap is None else min(result, cap)
