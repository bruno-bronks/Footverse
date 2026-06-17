"""Modelos de estado — Clube e lançamento de ledger.

O saldo de um clube **nunca** é alterado fora de um lançamento de ledger
(SPEC-001 §8, SPEC-002 §5). `valor_fvs` é assinado: positivo para faucet
(entrada), negativo para sink (saída).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# tipos de transação (SPEC-001/002/006/P2P)
INITIAL_GRANT = "INITIAL_GRANT"       # faucet: orçamento inicial
TRANSFER_BUY = "TRANSFER_BUY"         # sink: compra de jogador do mercado NPC
TRANSFER_BUY_P2P = "TRANSFER_BUY_P2P" # sink: compra de jogador de outro humano
TRANSFER_SELL_P2P = "TRANSFER_SELL_P2P" # faucet: venda de jogador para humano
SEASON_REWARD = "SEASON_REWARD"       # faucet: premiação de fim de temporada

DIVISAO_INICIAL = "SERIE_D"


@dataclass
class Club:
    id: str
    user_id: str
    nome: str
    escudo: str | None
    cores: tuple[str, ...]
    divisao: str = DIVISAO_INICIAL
    pontos_temporada_centi: int = 0
    saldo_fvs: int = 0            # sempre = Σ lançamentos do clube (reconciliável)
    criado_em: str | None = None
    gerenciado_por_ia: bool = False   # Fase 4: clube autônomo (agente decide ações)
    ia_personalidade: str | None = None  # "agressivo" | "conservador" | "equilibrado"


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    club_id: str
    tipo: str
    valor_fvs: int               # assinado: + faucet, − sink
    ref: str | None = None       # ex.: player_id numa compra
    criado_em: str | None = None


@dataclass(frozen=True)
class ApiKey:
    user_id: str
    key_hash: str                # sha256 hex da chave raw (nunca armazena raw)
    criado_em: str | None = None


@dataclass(frozen=True)
class Listing:
    """Oferta de venda de jogador no mercado P2P."""
    player_id: str
    seller_club_id: str
    preco_fvs: int
    criado_em: str | None = None
