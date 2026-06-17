"""Valor de mercado em FV$ — SPEC-005 §3.

    valor_fvs = ROUND_100k( VALOR_REF × RATE^(OVR − OVR_REF) × fator_idade )
                com piso de PISO_VALOR

O expoente (OVR − OVR_REF) é inteiro, então RATE^k é calculado por
multiplicação repetida (exponenciação inteira) — nunca por `pow` de libm —
para garantir determinismo cross-platform.
"""

from __future__ import annotations

import math

from .. import config


def _int_pow(base: float, k: int) -> float:
    """base**k para k inteiro, via multiplicação repetida (sem libm pow)."""
    if k < 0:
        return 1.0 / _int_pow(base, -k)
    result = 1.0
    for _ in range(k):
        result *= base
    return result


def _round_to_step(value: float, step: int) -> int:
    """Arredonda para o múltiplo de `step` mais próximo (half-up)."""
    return int(math.floor(value / step + 0.5)) * step


def market_value(ovr: int, idade: int) -> int:
    """Valor de mercado em FV$ (inteiro), ancorado na régua 'milhões baixa'."""
    base = config.VALOR_REF * _int_pow(config.RATE, ovr - config.OVR_REF)
    bruto = base * config.fator_idade(idade)
    arredondado = _round_to_step(bruto, config.ROUND_STEP)
    return max(arredondado, config.PISO_VALOR)
