"""Transcendentais "congelados" — exp e ln com algoritmo próprio.

Por quê: `math.exp`/`math.log` chamam a libm do sistema operacional, que **não
é garantidamente correta no último ULP** e pode divergir entre plataformas. A
SPEC-005 §8 e a SPEC-006 §7 exigem reprodutibilidade cross-platform da
simulação, então usamos uma implementação fixada que depende apenas de
operações IEEE-754 básicas (+, -, *, /) mais `ldexp`/`frexp` (exatas) e
`sqrt` (correta por ULP pela própria IEEE-754).

Estas funções são validadas contra `math.exp`/`math.log` nos testes (mesma
resposta dentro de ~1e-12), mas é a versão congelada que entra na simulação.
"""

from __future__ import annotations

import math

LN2: float = 0.6931471805599453   # double mais próximo de ln(2)
_SQRT1_2: float = 0.7071067811865476


def frozen_exp(x: float) -> float:
    """exp(x) determinístico via redução de faixa + série de Taylor."""
    if x == 0.0:
        return 1.0
    # x = k*ln2 + r,  |r| <= ln2/2 ≈ 0.3466
    k = int(math.floor(x / LN2 + 0.5))
    r = x - k * LN2
    # exp(r) por Taylor (converge rápido com |r| pequeno)
    term = 1.0
    s = 1.0
    n = 1
    while n <= 18:
        term *= r / n
        s += term
        n += 1
    return math.ldexp(s, k)   # s * 2**k, exato


def frozen_ln(x: float) -> float:
    """ln(x) determinístico via redução em mantissa/expoente + série atanh."""
    if x <= 0.0:
        raise ValueError("frozen_ln requer x > 0")
    m, e = math.frexp(x)          # x = m * 2**e, m em [0.5, 1)
    if m < _SQRT1_2:              # traz m para [~0.707, ~1.414) → série rápida
        m *= 2.0
        e -= 1
    s = (m - 1.0) / (m + 1.0)
    s2 = s * s
    term = s
    acc = s
    n = 3
    while n <= 33:
        term *= s2
        acc += term / n
        n += 2
    return e * LN2 + 2.0 * acc
