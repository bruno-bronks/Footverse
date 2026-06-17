"""Jogador: atributos e Overall (OVR) por posição — SPEC-005 §1-2."""

from __future__ import annotations

import math
from dataclasses import dataclass

# ordem canônica dos atributos
ATRIBUTOS: tuple[str, ...] = ("PAC", "FIN", "PAS", "DRI", "DEF", "FIS", "GK")

# pesos de OVR por posição (cada linha soma 1.00) — SPEC-005 §2
OVR_WEIGHTS: dict[str, dict[str, float]] = {
    "GOL":  {"PAC": 0.05, "FIN": 0.00, "PAS": 0.10, "DRI": 0.00, "DEF": 0.00, "FIS": 0.15, "GK": 0.70},
    "ZAG":  {"PAC": 0.10, "FIN": 0.05, "PAS": 0.10, "DRI": 0.00, "DEF": 0.45, "FIS": 0.30, "GK": 0.00},
    "LAT":  {"PAC": 0.25, "FIN": 0.05, "PAS": 0.15, "DRI": 0.10, "DEF": 0.30, "FIS": 0.15, "GK": 0.00},
    "VOL":  {"PAC": 0.05, "FIN": 0.05, "PAS": 0.25, "DRI": 0.10, "DEF": 0.35, "FIS": 0.20, "GK": 0.00},
    "MEI":  {"PAC": 0.10, "FIN": 0.15, "PAS": 0.35, "DRI": 0.25, "DEF": 0.10, "FIS": 0.05, "GK": 0.00},
    "MEIA": {"PAC": 0.15, "FIN": 0.20, "PAS": 0.30, "DRI": 0.30, "DEF": 0.00, "FIS": 0.05, "GK": 0.00},
    "EXT":  {"PAC": 0.30, "FIN": 0.20, "PAS": 0.15, "DRI": 0.30, "DEF": 0.00, "FIS": 0.05, "GK": 0.00},
    "ATA":  {"PAC": 0.20, "FIN": 0.40, "PAS": 0.05, "DRI": 0.15, "DEF": 0.00, "FIS": 0.20, "GK": 0.00},
}


@dataclass(frozen=True)
class Player:
    id: str
    posicao_natural: str
    atributos: dict[str, int]   # chaves = ATRIBUTOS, valores 0-100
    idade: int
    forma: int = 70             # default do jogador novo (SPEC-005 §1)


def overall(atributos: dict[str, int], posicao: str) -> int:
    """OVR (0-100) derivado dos atributos com os pesos da `posicao` dada.

    O OVR é sempre verdade derivada — nunca um campo solto (SPEC-005 §6.3).
    """
    w = OVR_WEIGHTS[posicao]
    total = 0.0
    for attr in ATRIBUTOS:
        total += w[attr] * atributos[attr]
    return int(math.floor(total + 0.5))   # half-up determinístico
