"""Validação de escalação — SPEC-003.

Recebe a formação, os 11 titulares (cada um com a posição/slot em que joga) e as
reservas, mais o elenco do clube (`squad`), e devolve uma `Lineup` validada ou
levanta `LineupError` com o código de erro da spec.

Regras (SPEC-003 §regras de negócio):
  1. exatamente 11 titulares
  2. exatamente 1 goleiro
  3. formação suportada + multiset de posições bate com ela
  4. posse: todos (titulares e reservas) pertencem ao clube
  5. sem jogador duplicado
  6. elegibilidade por setor: o jogador joga em slot do seu próprio setor
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .player import Player
from .positions import FORMACOES, SETOR, required_multiset

# códigos de erro (espelham a tabela de Validações/Erros da SPEC-003)
INVALID_LINEUP_SIZE = "INVALID_LINEUP_SIZE"
INVALID_GOALKEEPER_COUNT = "INVALID_GOALKEEPER_COUNT"
INVALID_FORMATION = "INVALID_FORMATION"
PLAYER_NOT_OWNED = "PLAYER_NOT_OWNED"
DUPLICATE_PLAYER = "DUPLICATE_PLAYER"
INVALID_POSITION = "INVALID_POSITION"
NO_VALID_LINEUP = "NO_VALID_LINEUP"   # SPEC-004: pontuar sem escalação ativa


class LineupError(Exception):
    """Erro de validação de escalação, com `code` da SPEC-003."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class Lineup:
    formacao: str
    titulares: tuple[tuple[str, str], ...]   # (player_id, slot)
    reservas: tuple[str, ...]


def validate_lineup(
    formacao: str,
    titulares: Sequence[tuple[str, str]],
    reservas: Sequence[str],
    squad: Mapping[str, Player],
) -> Lineup:
    titulares = list(titulares)
    reservas = list(reservas)

    # 1. tamanho do XI
    if len(titulares) != 11:
        raise LineupError(INVALID_LINEUP_SIZE, f"esperado 11 titulares, veio {len(titulares)}")

    # 2. formação suportada
    if formacao not in FORMACOES:
        raise LineupError(INVALID_FORMATION, f"formação não suportada: {formacao}")

    # 3. sem duplicatas (entre titulares e reservas)
    todos = [pid for pid, _ in titulares] + list(reservas)
    if len(set(todos)) != len(todos):
        raise LineupError(DUPLICATE_PLAYER, "jogador aparece mais de uma vez")

    # 4. posse: todos pertencem ao clube
    for pid in todos:
        if pid not in squad:
            raise LineupError(PLAYER_NOT_OWNED, f"jogador não pertence ao clube: {pid}")

    # 5. exatamente 1 goleiro (erro específico antes do multiset)
    n_gol = sum(1 for _, slot in titulares if slot == "GOL")
    if n_gol != 1:
        raise LineupError(INVALID_GOALKEEPER_COUNT, f"esperado 1 goleiro, veio {n_gol}")

    # 6. multiset de posições idêntico ao da formação
    if Counter(slot for _, slot in titulares) != required_multiset(formacao):
        raise LineupError(INVALID_FORMATION, "contagem de posições não bate com a formação")

    # 7. elegibilidade por setor
    for pid, slot in titulares:
        if SETOR[slot] != SETOR[squad[pid].posicao_natural]:
            raise LineupError(
                INVALID_POSITION,
                f"{pid} ({squad[pid].posicao_natural}) não pode jogar em {slot}",
            )

    return Lineup(formacao=formacao, titulares=tuple(titulares), reservas=tuple(reservas))
