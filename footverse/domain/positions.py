"""Posições, setores e formações — SPEC-003.

8 posições finas agrupadas em 4 setores. As posições finas definem o formato
da formação (tabela de multiset); o setor define a elegibilidade do jogador.
"""

from __future__ import annotations

from collections import Counter

# 8 posições finas
POSICOES: tuple[str, ...] = ("GOL", "ZAG", "LAT", "VOL", "MEI", "MEIA", "EXT", "ATA")

# setor de cada posição
SETOR: dict[str, str] = {
    "GOL": "GOL",
    "ZAG": "DEF", "LAT": "DEF",
    "VOL": "MEI", "MEI": "MEI", "MEIA": "MEI",
    "EXT": "ATA", "ATA": "ATA",
}

# tabela de formações: multiset exato de posições dos 11 titulares (SPEC-003)
FORMACOES: dict[str, dict[str, int]] = {
    "4-3-3":   {"GOL": 1, "ZAG": 2, "LAT": 2, "VOL": 1, "MEI": 2, "MEIA": 0, "EXT": 2, "ATA": 1},
    "4-4-2":   {"GOL": 1, "ZAG": 2, "LAT": 2, "VOL": 2, "MEI": 2, "MEIA": 0, "EXT": 0, "ATA": 2},
    "3-5-2":   {"GOL": 1, "ZAG": 3, "LAT": 2, "VOL": 2, "MEI": 0, "MEIA": 1, "EXT": 0, "ATA": 2},
    "4-2-3-1": {"GOL": 1, "ZAG": 2, "LAT": 2, "VOL": 2, "MEI": 0, "MEIA": 3, "EXT": 0, "ATA": 1},
    "5-3-2":   {"GOL": 1, "ZAG": 3, "LAT": 2, "VOL": 1, "MEI": 2, "MEIA": 0, "EXT": 0, "ATA": 2},
    "3-4-3":   {"GOL": 1, "ZAG": 3, "LAT": 2, "VOL": 1, "MEI": 1, "MEIA": 0, "EXT": 2, "ATA": 1},
}


# posições finas de cada setor (para gerar mercado e validar elegibilidade)
POSICOES_POR_SETOR: dict[str, tuple[str, ...]] = {
    "GOL": ("GOL",),
    "DEF": ("ZAG", "LAT"),
    "MEI": ("VOL", "MEI", "MEIA"),
    "ATA": ("EXT", "ATA"),
}


def required_multiset(formacao: str) -> Counter:
    """Multiset de posições exigido pela formação (sem as posições de contagem 0)."""
    return Counter({p: n for p, n in FORMACOES[formacao].items() if n > 0})


def setor_counts(formacao: str) -> Counter:
    """Quantos titulares cada setor (GOL/DEF/MEI/ATA) exige na formação."""
    out: Counter = Counter()
    for pos, n in FORMACOES[formacao].items():
        if n > 0:
            out[SETOR[pos]] += n
    return out


def lineup_multiset(posicoes: list[str]) -> Counter:
    """Multiset de posições de uma escalação."""
    return Counter(posicoes)
