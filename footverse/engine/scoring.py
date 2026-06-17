"""Pontuação por jogador numa rodada — SPEC-005 §4 (consumido pela SPEC-004).

Pipeline determinístico: nota → eventos (Poisson semeado) → pontos. Toda a
aleatoriedade vem da seed derivada server-side; cada jogador e cada tipo de
evento usa um *stream* independente (`Pcg32.from_key(..., "<stream>")`).

A função de conversão `points_centi` é pura e reproduz os exemplos da spec
(ATA 1G+1A nota 8.4 → 1980; GOL clean sheet + 4 defesas nota 7.0 → 1300).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import config
from ..domain.player import Player, overall
from .distributions import poisson
from .rng import Pcg32

_DEF_SLOTS = frozenset({"GOL", "ZAG", "LAT", "VOL"})


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


@dataclass(frozen=True)
class TitularSlot:
    """Um titular e a posição (slot) em que está escalado (pode != natural)."""
    player: Player
    slot: str


@dataclass(frozen=True)
class PlayerScore:
    player_id: str
    slot: str
    pts_centi: int
    nota: float
    gols: int
    assistencias: int
    defesas: int
    gols_sofridos: int
    clean_sheet: bool


@dataclass(frozen=True)
class RoundScore:
    club_id: str
    rodada_id: str
    pontos_centi: int
    breakdown: tuple[PlayerScore, ...]


# ───────────────────────────── peças puras (testáveis isoladas) ─────────────
def compute_nota(ovr_slot: int, forma: int, eps: float) -> float:
    """Nota 0-10 (SPEC-005 §4.1). `eps` ∈ [-1, 1]."""
    fator_forma = 0.90 + 0.20 * (forma / 100.0)
    bruto = 5.0 + (ovr_slot - 50) / 12.0 + (fator_forma - 1.0) * 10.0 + eps * 1.5
    return _clamp(bruto, 0.0, 10.0)


def points_centi(
    slot: str,
    nota: float,
    gols: int,
    assistencias: int,
    clean_sheet: bool,
    defesas: int,
    gols_sofridos: int,
) -> int:
    """Converte nota + eventos em pontos (centésimos, half-up) — SPEC-005 §4.4."""
    pts = config.NOTA_SCALE * (nota - 5.0)
    pts += gols * config.PT_GOL
    pts += assistencias * config.PT_ASSIST
    if clean_sheet and slot in _DEF_SLOTS:
        pts += config.PT_SG
    if slot == "GOL":
        pts += defesas * config.PT_DD
    if slot in ("GOL", "ZAG"):
        pts -= gols_sofridos * config.PT_GS
    return _round_half_up(pts * 100.0)


# ───────────────────────────── defesa do time (nível de equipe) ────────────
@dataclass(frozen=True)
class TeamDefense:
    gols_sofridos: int
    clean_sheet: bool
    defesas_gk: int


def _team_defense(
    titulares: list[TitularSlot], divisao: str, base: tuple[object, ...]
) -> TeamDefense:
    valores: list[float] = []
    gk: Player | None = None
    for t in titulares:
        if t.slot in _DEF_SLOTS:
            valores.append(t.player.atributos["DEF"])
            valores.append(t.player.atributos["FIS"])
        if t.slot == "GOL":
            gk = t.player
    if gk is not None:
        valores.append(gk.atributos["GK"])
    forca_def = max(sum(valores) / len(valores), 1.0)

    rng_adv = Pcg32.from_key(*base, "adversario")
    fator = 1.0 + (-0.15 + 0.30 * rng_adv.random())
    forca_adv = config.FORCA_BASE_DIVISAO[divisao] * fator

    lam_gc = _clamp(config.BASE_GC * (forca_adv / forca_def), 0.0, 6.0)
    sofridos = poisson(lam_gc, Pcg32.from_key(*base, "gols_sofridos"))

    gk_attr = gk.atributos["GK"] if gk is not None else 0
    lam_def = _clamp(config.DEF_RATE * (forca_adv / 100.0) * (gk_attr / 100.0), 0.0, 8.0)
    defesas = poisson(lam_def, Pcg32.from_key(*base, "defesas"))

    return TeamDefense(sofridos, sofridos == 0, defesas)


# ───────────────────────────── orquestração da rodada ──────────────────────
def score_round(
    titulares: list[TitularSlot],
    divisao: str,
    season_secret: str,
    club_id: str,
    rodada_id: str,
) -> RoundScore:
    """Pontua uma rodada inteira (11 titulares). Determinística por seed."""
    base = (season_secret, club_id, rodada_id)
    defesa = _team_defense(titulares, divisao, base)

    breakdown: list[PlayerScore] = []
    for t in titulares:
        p, slot = t.player, t.slot
        ovr_slot = overall(p.atributos, slot)

        eps = -1.0 + 2.0 * Pcg32.from_key(*base, p.id, "nota").random()
        nota = compute_nota(ovr_slot, p.forma, eps)

        lam_gol = config.GOAL_RATE * config.PESO_ATAQUE[slot] * (p.atributos["FIN"] / 100.0) * (nota / 7.0)
        lam_ass = config.ASSIST_RATE * config.PESO_CRIACAO[slot] * (p.atributos["PAS"] / 100.0) * (nota / 7.0)
        gols = poisson(lam_gol, Pcg32.from_key(*base, p.id, "gol"), cap=4)
        assist = poisson(lam_ass, Pcg32.from_key(*base, p.id, "assist"), cap=3)

        pts = points_centi(
            slot, nota, gols, assist, defesa.clean_sheet,
            defesa.defesas_gk if slot == "GOL" else 0, defesa.gols_sofridos,
        )
        breakdown.append(PlayerScore(
            player_id=p.id, slot=slot, pts_centi=pts, nota=nota,
            gols=gols, assistencias=assist,
            defesas=defesa.defesas_gk if slot == "GOL" else 0,
            gols_sofridos=defesa.gols_sofridos, clean_sheet=defesa.clean_sheet,
        ))

    total = sum(ps.pts_centi for ps in breakdown)
    return RoundScore(club_id, rodada_id, total, tuple(breakdown))
