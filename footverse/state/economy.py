"""Ações de clube — criar clube, comprar e vender jogadores (SPEC-001/002/P2P).

Toda movimentação de FV$ passa pelo ledger (`Store.post_ledger`), nunca por
update solto de saldo. As funções levantam `EconomyError` com o código exato
das tabelas de Validações/Erros das specs.

Mercado P2P (Fase 2):
- `listar_jogador`: club coloca jogador do elenco à venda com preço definido
- `cancelar_listagem`: retira da oferta
- `comprar_jogador`: auto-detecta NPC vs P2P pelo estado do jogador
  - NPC (unowned) → sink TRANSFER_BUY (FV$ sai de circulação)
  - P2P (listed) → TRANSFER_BUY_P2P no comprador + TRANSFER_SELL_P2P no vendedor
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config
from .models import (
    INITIAL_GRANT, TRANSFER_BUY, TRANSFER_BUY_P2P, TRANSFER_SELL_P2P,
    Club, Listing,
)
from .store import Store

# códigos de erro (SPEC-001/002)
CLUB_ALREADY_EXISTS = "CLUB_ALREADY_EXISTS"
INVALID_NAME = "INVALID_NAME"
INVALID_COLOR = "INVALID_COLOR"
TOO_MANY_COLORS = "TOO_MANY_COLORS"
CLUB_NOT_FOUND = "CLUB_NOT_FOUND"
PLAYER_NOT_FOUND = "PLAYER_NOT_FOUND"
PLAYER_NOT_AVAILABLE = "PLAYER_NOT_AVAILABLE"
PLAYER_NOT_OWNED = "PLAYER_NOT_OWNED"
PLAYER_ALREADY_LISTED = "PLAYER_ALREADY_LISTED"
PLAYER_NOT_LISTED = "PLAYER_NOT_LISTED"
INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
SQUAD_FULL = "SQUAD_FULL"
CANNOT_BUY_OWN_PLAYER = "CANNOT_BUY_OWN_PLAYER"

_HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class EconomyError(Exception):
    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class CompraResult:
    transacao_id: str
    club_id: str
    player_id: str
    valor_fvs: int
    saldo_anterior: int
    saldo_final: int
    tipo: str = "NPC"                    # "NPC" ou "P2P"
    vendedor_club_id: str | None = None  # preenchido em compras P2P


@dataclass(frozen=True)
class ListingResult:
    player_id: str
    seller_club_id: str
    preco_fvs: int


def criar_clube(
    store: Store, user_id: str, nome: str,
    cores: list[str], escudo: str | None = None, criado_em: str | None = None,
) -> Club:
    """Cria um clube e credita o orçamento inicial via faucet INITIAL_GRANT."""
    if not (3 <= len(nome) <= 40):
        raise EconomyError(INVALID_NAME, "nome deve ter 3–40 caracteres")
    if len(cores) > 3:
        raise EconomyError(TOO_MANY_COLORS, "máximo de 3 cores")
    if not cores or any(not _HEX.match(c) for c in cores):
        raise EconomyError(INVALID_COLOR, "cores devem ser hex válidas (#RGB ou #RRGGBB)")
    if store.get_user_club(user_id) is not None:
        raise EconomyError(CLUB_ALREADY_EXISTS, "usuário já possui clube")

    club_id = store.next_club_id()
    club = Club(
        id=club_id, user_id=user_id, nome=nome, escudo=escudo,
        cores=tuple(cores), criado_em=criado_em,
    )
    store.add_club(club)
    store.post_ledger(club, INITIAL_GRANT, config.ORCAMENTO_INICIAL_FVS,
                      ref="orcamento_inicial", criado_em=criado_em)
    return club


def comprar_jogador(
    store: Store, club_id: str, player_id: str, criado_em: str | None = None,
) -> CompraResult:
    """Compra um jogador — NPC (sink) ou P2P (transferência), auto-detectado."""
    club = store.get_club(club_id)
    if club is None:
        raise EconomyError(CLUB_NOT_FOUND, club_id)
    mp = store.get_player(player_id)
    if mp is None:
        raise EconomyError(PLAYER_NOT_FOUND, player_id)
    if len(store.elenco(club_id)) >= config.MAX_ELENCO:
        raise EconomyError(SQUAD_FULL, f"elenco cheio ({config.MAX_ELENCO})")

    listing = store.get_listing(player_id)
    owner = store.owner_of(player_id)

    if owner is not None and listing is None:
        raise EconomyError(PLAYER_NOT_AVAILABLE, player_id)
    if listing is not None and listing.seller_club_id == club_id:
        raise EconomyError(CANNOT_BUY_OWN_PLAYER, "não pode comprar seu próprio jogador")

    preco = listing.preco_fvs if listing else mp.valor_fvs
    saldo_anterior = club.saldo_fvs
    if saldo_anterior < preco:
        raise EconomyError(INSUFFICIENT_FUNDS, f"saldo {saldo_anterior} < preço {preco}")

    if listing:
        # P2P: FV$ vai do comprador para o vendedor
        seller = store.get_club(listing.seller_club_id)
        entry = store.post_ledger(club, TRANSFER_BUY_P2P, -preco,
                                  ref=player_id, criado_em=criado_em)
        store.post_ledger(seller, TRANSFER_SELL_P2P, +preco,
                          ref=player_id, criado_em=criado_em)
        store.delist_player(player_id)
        store.set_owner(player_id, club_id)
        return CompraResult(
            transacao_id=entry.id, club_id=club_id, player_id=player_id,
            valor_fvs=preco, saldo_anterior=saldo_anterior, saldo_final=club.saldo_fvs,
            tipo="P2P", vendedor_club_id=listing.seller_club_id,
        )

    # NPC: sink
    entry = store.post_ledger(club, TRANSFER_BUY, -preco,
                              ref=player_id, criado_em=criado_em)
    store.set_owner(player_id, club_id)
    return CompraResult(
        transacao_id=entry.id, club_id=club_id, player_id=player_id,
        valor_fvs=preco, saldo_anterior=saldo_anterior, saldo_final=club.saldo_fvs,
        tipo="NPC",
    )


def listar_jogador(
    store: Store, club_id: str, player_id: str, preco_fvs: int,
    criado_em: str | None = None,
) -> ListingResult:
    """Coloca um jogador do elenco à venda no mercado P2P."""
    if store.get_club(club_id) is None:
        raise EconomyError(CLUB_NOT_FOUND, club_id)
    if store.get_player(player_id) is None:
        raise EconomyError(PLAYER_NOT_FOUND, player_id)
    if store.owner_of(player_id) != club_id:
        raise EconomyError(PLAYER_NOT_OWNED, "jogador não pertence ao clube")
    if store.get_listing(player_id) is not None:
        raise EconomyError(PLAYER_ALREADY_LISTED, "jogador já está listado")
    if preco_fvs <= 0:
        raise EconomyError(INVALID_COLOR, "preço deve ser positivo")  # reutiliza HTTP 400

    listing = Listing(player_id=player_id, seller_club_id=club_id,
                      preco_fvs=preco_fvs, criado_em=criado_em)
    store.list_player(listing)
    return ListingResult(player_id=player_id, seller_club_id=club_id, preco_fvs=preco_fvs)


def cancelar_listagem(store: Store, club_id: str, player_id: str) -> None:
    """Retira um jogador da oferta P2P."""
    listing = store.get_listing(player_id)
    if listing is None:
        raise EconomyError(PLAYER_NOT_LISTED, "jogador não está listado")
    if listing.seller_club_id != club_id:
        raise EconomyError(PLAYER_NOT_OWNED, "listagem pertence a outro clube")
    store.delist_player(player_id)
