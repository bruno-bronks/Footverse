"""Validação de escalação — SPEC-003 (cada erro + casos felizes)."""

import pytest

from footverse.domain.lineup import (
    DUPLICATE_PLAYER,
    INVALID_FORMATION,
    INVALID_GOALKEEPER_COUNT,
    INVALID_LINEUP_SIZE,
    INVALID_POSITION,
    PLAYER_NOT_OWNED,
    LineupError,
    validate_lineup,
)
from footverse.domain.player import ATRIBUTOS, Player

# elenco com posições naturais que compõem um 4-3-3 + reservas
_NATURAL = {
    "gk": "GOL", "z1": "ZAG", "z2": "ZAG", "l1": "LAT", "l2": "LAT",
    "v1": "VOL", "m1": "MEI", "m2": "MEI", "e1": "EXT", "e2": "EXT", "a1": "ATA",
    "res_gk": "GOL", "res_z": "ZAG",
}

_TITULARES_433 = [
    ("gk", "GOL"), ("z1", "ZAG"), ("z2", "ZAG"), ("l1", "LAT"), ("l2", "LAT"),
    ("v1", "VOL"), ("m1", "MEI"), ("m2", "MEI"), ("e1", "EXT"), ("e2", "EXT"),
    ("a1", "ATA"),
]
_RESERVAS = ["res_gk", "res_z"]


def _squad(natural: dict[str, str] | None = None) -> dict[str, Player]:
    natural = natural or _NATURAL
    attrs = {a: 55 for a in ATRIBUTOS}
    return {
        pid: Player(id=pid, posicao_natural=pos, atributos=dict(attrs), idade=25)
        for pid, pos in natural.items()
    }


def _raises(code, **kw):
    formacao = kw.get("formacao", "4-3-3")
    titulares = kw.get("titulares", _TITULARES_433)
    reservas = kw.get("reservas", _RESERVAS)
    squad = kw.get("squad", _squad())
    with pytest.raises(LineupError) as exc:
        validate_lineup(formacao, titulares, reservas, squad)
    assert exc.value.code == code


def test_valid_lineup_passes():
    lu = validate_lineup("4-3-3", _TITULARES_433, _RESERVAS, _squad())
    assert lu.formacao == "4-3-3"
    assert len(lu.titulares) == 11
    assert lu.reservas == ("res_gk", "res_z")


def test_wrong_size():
    _raises(INVALID_LINEUP_SIZE, titulares=_TITULARES_433[:10])


def test_unsupported_formation():
    _raises(INVALID_FORMATION, formacao="4-5-1")


def test_duplicate_player():
    dup = _TITULARES_433[:-1] + [("m1", "ATA")]  # m1 repetido
    _raises(DUPLICATE_PLAYER, titulares=dup)


def test_player_not_owned():
    titulares = _TITULARES_433[:-1] + [("intruso", "ATA")]
    _raises(PLAYER_NOT_OWNED, titulares=titulares)


def test_no_goalkeeper_is_error():
    # caso explícito do roadmap: escalação sem goleiro → erro
    titulares = [("z2b", "ZAG")] + _TITULARES_433[1:]
    squad = _squad({**_NATURAL, "z2b": "ZAG"})
    _raises(INVALID_GOALKEEPER_COUNT, titulares=titulares, squad=squad)


def test_two_goalkeepers_is_error():
    titulares = [(pid, "GOL") if pid == "z1" else (pid, slot)
                 for pid, slot in _TITULARES_433]
    _raises(INVALID_GOALKEEPER_COUNT, titulares=titulares)


def test_multiset_mismatch_is_invalid_formation():
    # 3 ZAG + 1 LAT (mesmo setor DEF → posse/elegibilidade ok), mas não bate o 4-3-3
    titulares = [
        ("gk", "GOL"), ("z1", "ZAG"), ("z2", "ZAG"), ("l1", "ZAG"), ("l2", "LAT"),
        ("v1", "VOL"), ("m1", "MEI"), ("m2", "MEI"), ("e1", "EXT"), ("e2", "EXT"),
        ("a1", "ATA"),
    ]
    _raises(INVALID_FORMATION, titulares=titulares)


def test_position_incompatible_sector():
    # a1 é ATA natural, escalado num slot ZAG (setor DEF) → INVALID_POSITION
    titulares = [
        ("gk", "GOL"), ("a1", "ZAG"), ("z2", "ZAG"), ("l1", "LAT"), ("l2", "LAT"),
        ("v1", "VOL"), ("m1", "MEI"), ("m2", "MEI"), ("e1", "EXT"), ("e2", "EXT"),
        ("z1", "ATA"),
    ]
    # z1 (ZAG) no slot ATA também seria erro, mas a1 no ZAG dispara primeiro
    _raises(INVALID_POSITION, titulares=titulares)


def test_same_sector_cross_position_allowed():
    # VOL natural ocupando slot MEI (mesmo setor MEI) é permitido (SPEC-003 §6)
    squad = _squad({**_NATURAL, "m1": "VOL"})
    lu = validate_lineup("4-3-3", _TITULARES_433, _RESERVAS, squad)
    assert lu.formacao == "4-3-3"
