"""PRNG determinístico — PCG32 com algoritmo congelado.

Nunca usar o RNG default da linguagem (o `random` de Python e o `hash` de
strings são instáveis entre execuções/versões). Aqui o estado é puro inteiro
de 64 bits com operações exatas, e a semente vem de um SHA-256 do material de
chave (estável cross-platform), atendendo às SPEC-004/005/006.

Uso típico (os "streams" que as specs citam):

    rng = Pcg32.from_key(SEASON_SECRET, club_id, rodada_id, player_id, "gol")
    n = rng.next_u32()
    u = rng.random()        # [0, 1)
"""

from __future__ import annotations

import hashlib

_MULT = 6364136223846793005
_MASK64 = (1 << 64) - 1
_MASK32 = (1 << 32) - 1
_2POW32 = 4294967296.0
_SEP = "\x1f"   # separador improvável em ids


def _seed_from_key(parts: tuple[object, ...]) -> tuple[int, int]:
    key = _SEP.join(str(p) for p in parts)
    h = hashlib.sha256(key.encode("utf-8")).digest()
    initstate = int.from_bytes(h[0:8], "big")
    initseq = int.from_bytes(h[8:16], "big")
    return initstate, initseq


class Pcg32:
    """Gerador PCG32 (O'Neill). Determinístico e reprodutível."""

    __slots__ = ("state", "inc")

    def __init__(self, initstate: int, initseq: int) -> None:
        self.inc = ((initseq << 1) | 1) & _MASK64
        self.state = 0
        self._step()
        self.state = (self.state + (initstate & _MASK64)) & _MASK64
        self._step()

    @classmethod
    def from_key(cls, *parts: object) -> "Pcg32":
        """Cria um gerador a partir de um material de chave arbitrário."""
        initstate, initseq = _seed_from_key(parts)
        return cls(initstate, initseq)

    def _step(self) -> None:
        self.state = (self.state * _MULT + self.inc) & _MASK64

    def next_u32(self) -> int:
        old = self.state
        self._step()
        xorshifted = (((old >> 18) ^ old) >> 27) & _MASK32
        rot = old >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & _MASK32

    def random(self) -> float:
        """Float em [0, 1)."""
        return self.next_u32() / _2POW32

    def random_open(self) -> float:
        """Float em (0, 1) — nunca 0 nem 1 (para inversa da Normal)."""
        return (self.next_u32() + 0.5) / _2POW32
