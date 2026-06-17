"""Geração do mercado barato de Série D — SPEC-005 §6.

Pré-condição do loop: o clube nasce sem elenco (SPEC-001) e monta o time
comprando aqui. O mercado é determinístico por `SEASON_SECRET` (mesma seed ⇒
mesmo mercado) e tem composição mínima garantida por setor, de modo que o
orçamento inicial sempre monte um XI legal (SPEC-003).

Modelagem de atributos: gera-se um **OVR-alvo** ~ Normal(50,7) clampado, depois
cada atributo = alvo + viés_de_posição + ruído. O viés é derivado dos pesos de
OVR (atributos irrelevantes à posição ficam mais baixos, dando "forma" ao
jogador sem desancorar o OVR). O **OVR real é recalculado** dos atributos — é
sempre verdade derivada, nunca campo solto.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

from .. import config
from ..domain.player import ATRIBUTOS, OVR_WEIGHTS, Player, overall
from ..domain.positions import POSICOES_POR_SETOR, setor_counts
from .distributions import normal, normal_clamped_int
from .rng import Pcg32
from .valuation import market_value

_SETORES = ("GOL", "DEF", "MEI", "ATA")


@dataclass(frozen=True)
class MarketPlayer:
    player: Player
    ovr: int
    valor_fvs: int
    setor: str


def _bias(pos: str, attr: str) -> int:
    """Viés do atributo derivado do peso de OVR: irrelevantes ficam mais baixos."""
    w = OVR_WEIGHTS[pos][attr]
    if w >= 0.15:
        return 0
    if w > 0.0:
        return -8
    return -20


def _gen_player(
    season_secret: str, slot_idx: int, setor: str, id_prefix: str = "mkt"
) -> MarketPlayer:
    rng = Pcg32.from_key(season_secret, "market", slot_idx)

    posicoes = POSICOES_POR_SETOR[setor]
    pos = posicoes[rng.next_u32() % len(posicoes)]

    ovr_alvo = normal_clamped_int(
        config.MERCADO_OVR_MU, config.MERCADO_OVR_SIGMA,
        config.MERCADO_OVR_MIN, config.MERCADO_OVR_MAX, rng,
    )

    atributos: dict[str, int] = {}
    for attr in ATRIBUTOS:
        ruido = normal(0.0, config.MERCADO_ATTR_JITTER, rng)
        v = int(math.floor(ovr_alvo + _bias(pos, attr) + ruido + 0.5))
        atributos[attr] = max(1, min(99, v))

    idade = normal_clamped_int(
        config.MERCADO_IDADE_MU, config.MERCADO_IDADE_SIGMA,
        config.MERCADO_IDADE_MIN, config.MERCADO_IDADE_MAX, rng,
    )

    ovr = overall(atributos, pos)                 # verdade derivada
    valor = market_value(ovr, idade)
    player = Player(
        id=f"{id_prefix}_{slot_idx}", posicao_natural=pos,
        atributos=atributos, idade=idade, forma=70,
    )
    return MarketPlayer(player=player, ovr=ovr, valor_fvs=valor, setor=setor)


def generate_market(
    season_secret: str,
    composicao: dict[str, int] | None = None,
    id_prefix: str = "mkt",
) -> list[MarketPlayer]:
    """Gera o mercado de uma temporada. Determinístico por `season_secret`.

    `id_prefix` permite gerar lotes adicionais de jogadores sem colidir com
    IDs do mercado inicial (ex: `id_prefix="mkt_T2"` para a geração da T2).
    """
    composicao = composicao or config.MIN_MERCADO_POR_SETOR
    mercado: list[MarketPlayer] = []
    slot_idx = 0
    for setor in _SETORES:
        for _ in range(composicao[setor]):
            mercado.append(_gen_player(season_secret, slot_idx, setor, id_prefix))
            slot_idx += 1
    return mercado


def cheapest_xi_cost(mercado: list[MarketPlayer], formacao: str) -> int | None:
    """Custo do XI mais barato possível para a formação, ou None se inviável.

    Elegibilidade é por setor (SPEC-003 §6): qualquer jogador do setor pode
    ocupar um slot daquele setor; pega-se os mais baratos de cada setor.
    """
    por_setor: dict[str, list[int]] = defaultdict(list)
    for mp in mercado:
        por_setor[mp.setor].append(mp.valor_fvs)

    total = 0
    for setor, n in setor_counts(formacao).items():
        valores = sorted(por_setor.get(setor, []))
        if len(valores) < n:
            return None
        total += sum(valores[:n])
    return total
