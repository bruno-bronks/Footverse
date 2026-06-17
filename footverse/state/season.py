"""Temporada e progressão de divisão — SPEC-006 (parte com estado/ledger).

Acumula a pontuação do humano por rodada, fecha a temporada contra a
liga-sombra (engine.league) e aplica promoção/rebaixamento + premiação
(faucet via ledger) de forma idempotente.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from .. import config
from ..engine.distributions import normal_clamped_int
from ..engine.league import StandingRow, classificar, npc_standings
from ..engine.rng import Pcg32
from .models import SEASON_REWARD
from .store import Store

# códigos de erro (SPEC-006 §6)
SEASON_NOT_FINISHED = "SEASON_NOT_FINISHED"
SEASON_ALREADY_CLOSED = "SEASON_ALREADY_CLOSED"
SEASON_FULL = "SEASON_FULL"
INVALID_DIVISION = "INVALID_DIVISION"


class SeasonError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass
class SeasonState:
    season_secret: str
    temporada: int
    divisao: str
    club_id: str
    rodadas: dict[str, int] = field(default_factory=dict)   # rodada_id -> pontos_centi
    status: str = "EM_ANDAMENTO"

    @property
    def rodada_atual(self) -> int:
        return len(self.rodadas)


@dataclass(frozen=True)
class SeasonResult:
    temporada: int
    divisao_anterior: str
    posicao_final: int
    resultado: str            # CAMPEAO | PROMOVIDO | PERMANECE | REBAIXADO
    divisao_nova: str
    premiacao_fvs: int
    status: str


def registrar_rodada(
    store: Store, season: SeasonState, rodada_id: str, pontos_centi: int
) -> None:
    """Registra a pontuação do humano numa rodada (vinda da SPEC-004).

    Idempotente por `rodada_id` (SPEC-004 §5-6): registrar a mesma rodada de
    novo é no-op — não acumula `pontos_temporada`.
    """
    if season.status == "ENCERRADA":
        raise SeasonError(SEASON_ALREADY_CLOSED)
    if rodada_id in season.rodadas:
        return  # idempotência: já aplicada
    if season.rodada_atual >= config.RODADAS_POR_TEMPORADA:
        raise SeasonError(SEASON_FULL, "temporada já tem todas as rodadas")
    season.rodadas[rodada_id] = pontos_centi
    club = store.get_club(season.club_id)
    club.pontos_temporada_centi += pontos_centi
    store.save_club(club)
    store.save_season(season)


def _progressao(divisao: str, pos: int) -> tuple[str, str]:
    """Resultado + divisão nova, dada a posição final (1-based)."""
    idx = config.DIVISOES.index(divisao)
    if pos <= config.N_PROMOVIDOS:
        if idx == 0:  # Série A: não há acima
            return ("CAMPEAO" if pos == 1 else "PERMANECE"), divisao
        return "PROMOVIDO", config.DIVISOES[idx - 1]
    if pos > config.CLUBES_POR_DIVISAO - config.N_REBAIXADOS:
        if idx == len(config.DIVISOES) - 1:  # Série D: não há abaixo
            return "PERMANECE", divisao
        return "REBAIXADO", config.DIVISOES[idx + 1]
    return "PERMANECE", divisao


def encerrar_temporada(store: Store, season: SeasonState) -> SeasonResult:
    """Fecha a temporada: classifica, promove/rebaixa, premia. Idempotente."""
    if season.status == "ENCERRADA":
        raise SeasonError(SEASON_ALREADY_CLOSED)
    if season.divisao not in config.DIVISOES:
        raise SeasonError(INVALID_DIVISION, season.divisao)
    if season.rodada_atual != config.RODADAS_POR_TEMPORADA:
        raise SeasonError(SEASON_NOT_FINISHED,
                          f"{season.rodada_atual}/{config.RODADAS_POR_TEMPORADA} rodadas")

    club = store.get_club(season.club_id)
    pontos = list(season.rodadas.values())
    humano = StandingRow(
        club_id=club.id, tipo="HUMANO",
        pontos_centi=sum(pontos),
        melhor_rodada_centi=max(pontos),
    )

    # Clubes reais na mesma divisão competem contra o humano (Fase 2).
    real_rows: list[StandingRow] = []
    for rc in store.get_clubs_by_division(season.divisao, exclude_id=club.id):
        rc_season = store.get_season(rc.id)
        rc_pontos = rc.pontos_temporada_centi
        rc_melhor = max(rc_season.rodadas.values()) if rc_season and rc_season.rodadas else 0
        real_rows.append(StandingRow(rc.id, "HUMANO", rc_pontos, rc_melhor))

    # NPCs preenchem as vagas restantes até CLUBES_POR_DIVISAO.
    n_npcs = max(0, config.CLUBES_POR_DIVISAO - 1 - len(real_rows))
    npcs = npc_standings(season.season_secret, season.divisao, season.temporada, n_npcs=n_npcs)
    tabela = classificar([humano, *real_rows, *npcs], season.season_secret)
    pos = next(i for i, row in enumerate(tabela, start=1) if row.club_id == club.id)

    resultado, divisao_nova = _progressao(season.divisao, pos)
    divisao_anterior = season.divisao
    club.divisao = divisao_nova
    premio = config.PREMIO_POR_RESULTADO[resultado]
    store.post_ledger(club, SEASON_REWARD, premio, ref=f"temporada_{season.temporada}")

    club.pontos_temporada_centi = 0
    store.save_club(club)
    season.status = "ENCERRADA"
    store.save_season(season)
    return SeasonResult(
        temporada=season.temporada, divisao_anterior=divisao_anterior,
        posicao_final=pos, resultado=resultado, divisao_nova=divisao_nova,
        premiacao_fvs=premio, status="ENCERRADA",
    )


def proxima_temporada(store: Store, season: SeasonState) -> SeasonState:
    """Cria o estado da próxima temporada na divisão (já atualizada) do clube."""
    if season.status != "ENCERRADA":
        raise SeasonError(SEASON_NOT_FINISHED, "encerre a temporada antes do rollover")
    return SeasonState(
        season_secret=season.season_secret,
        temporada=season.temporada + 1,
        divisao=store.get_club(season.club_id).divisao,
        club_id=season.club_id,
    )


def forma_para(season_secret: str, club_id: str, player_id: str, temporada: int) -> int:
    """Forma de um jogador no rollover — determinística (SPEC-006 §5)."""
    rng = Pcg32.from_key(season_secret, club_id, player_id, temporada)
    return normal_clamped_int(
        config.FORMA_MU, config.FORMA_SIGMA, config.FORMA_MIN, config.FORMA_MAX, rng
    )


def atualizar_forma_elenco(
    store: Store, season_secret: str, club_id: str, temporada: int
) -> None:
    """Aplica a nova forma a todos os jogadores do elenco (afeta só pontuação)."""
    for pid in store.elenco(club_id):
        mp = store.get_player(pid)
        nova = forma_para(season_secret, club_id, pid, temporada)
        novo_player = dataclasses.replace(mp.player, forma=nova)
        store.update_player(dataclasses.replace(mp, player=novo_player))
