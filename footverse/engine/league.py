"""Liga-sombra de NPCs e classificação — SPEC-006 §2-3 (parte pura).

NPCs **não são clubes-IA**: são apenas placares determinísticos por rodada,
calibrados à força da divisão, que servem de régua para o clube humano subir
ou descer. Tudo derivado de `SEASON_SECRET` + chaves estáveis.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from .. import config
from .distributions import normal
from .rng import Pcg32


@dataclass(frozen=True)
class StandingRow:
    club_id: str
    tipo: str                 # "HUMANO" | "NPC"
    pontos_centi: int
    melhor_rodada_centi: int  # desempate 2: maior pontuação numa única rodada


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def npc_round_score(
    season_secret: str, divisao: str, temporada: int, npc_id: str, rodada: int
) -> int:
    """Pontos (centésimos) de um NPC numa rodada — SPEC-006 §2.2."""
    rng = Pcg32.from_key(season_secret, divisao, temporada, npc_id, rodada)
    mu = config.MEDIA_PONTOS_NPC[divisao]
    x = _clamp(normal(mu, config.DESVIO_PONTOS_NPC, rng), 0.0, 200.0)
    return _round_half_up(100.0 * x)


def npc_standings(
    season_secret: str, divisao: str, temporada: int, n_npcs: int | None = None
) -> list[StandingRow]:
    """Linhas de classificação dos NPCs da divisão (total + melhor rodada)."""
    n = n_npcs if n_npcs is not None else config.CLUBES_POR_DIVISAO - 1
    rows: list[StandingRow] = []
    for i in range(n):
        npc_id = f"npc_{divisao}_{i}"
        scores = [
            npc_round_score(season_secret, divisao, temporada, npc_id, r)
            for r in range(1, config.RODADAS_POR_TEMPORADA + 1)
        ]
        rows.append(StandingRow(npc_id, "NPC", sum(scores), max(scores)))
    return rows


def _tiebreak_key(row: StandingRow, season_secret: str) -> tuple:
    # 1) pontos desc  2) melhor rodada desc  3) hash determinístico asc
    h = hashlib.sha256(f"{season_secret}|{row.club_id}".encode("utf-8")).hexdigest()
    return (-row.pontos_centi, -row.melhor_rodada_centi, h)


def classificar(rows: list[StandingRow], season_secret: str) -> list[StandingRow]:
    """Ordena a tabela com o desempate de 3 níveis (ordem total estrita)."""
    return sorted(rows, key=lambda r: _tiebreak_key(r, season_secret))
