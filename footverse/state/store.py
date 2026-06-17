"""Store in-memory — implementação de referência do repositório (Fase 1).

Centraliza clubes, catálogo de jogadores (mercado), posse e o ledger. O único
caminho para mover FV$ é `post_ledger`, que atualiza o saldo e registra o
lançamento de forma indivisível — garantindo a invariante de reconciliação
(saldo == Σ lançamentos do clube).

Expõe a mesma interface por métodos que o `SqlStore`, de modo que economia,
temporada e o facade `World` funcionem sobre qualquer repositório. Os dicts
internos permanecem públicos por conveniência de inspeção/testes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..engine.market_gen import MarketPlayer
from .models import Club, LedgerEntry, Listing

if TYPE_CHECKING:
    from ..domain.lineup import Lineup
    from .season import SeasonState


class Store:
    def __init__(self) -> None:
        self.clubs: dict[str, Club] = {}
        self.user_to_club: dict[str, str] = {}
        self.catalog: dict[str, MarketPlayer] = {}     # player_id -> ficha
        self.ownership: dict[str, str | None] = {}     # player_id -> club_id | None
        self.ledger: list[LedgerEntry] = []
        self._seasons: dict[str, SeasonState] = {}
        self._lineups: dict[str, Lineup] = {}
        self._api_keys: dict[str, str] = {}            # key_hash -> user_id
        self._listings: dict[str, Listing] = {}        # player_id -> Listing (P2P)
        self._world_clock: str | None = None            # epoch seconds (str) do último tick
        self._club_seq = 0
        self._txn_seq = 0

    # ── ids ────────────────────────────────────────────────────────────────
    def next_club_id(self) -> str:
        self._club_seq += 1
        return f"club_{self._club_seq}"

    def next_txn_id(self) -> str:
        self._txn_seq += 1
        return f"txn_{self._txn_seq}"

    # ── clubes ──────────────────────────────────────────────────────────────
    def add_club(self, club: Club) -> None:
        self.clubs[club.id] = club
        self.user_to_club[club.user_id] = club.id

    def get_club(self, club_id: str) -> Club | None:
        return self.clubs.get(club_id)

    def get_user_club(self, user_id: str) -> str | None:
        return self.user_to_club.get(user_id)

    def save_club(self, club: Club) -> None:
        pass  # objeto vivo: mutações já refletem

    # ── jogadores / mercado ────────────────────────────────────────────────
    def load_market(self, mercado: list[MarketPlayer]) -> None:
        for mp in mercado:
            self.catalog[mp.player.id] = mp
            self.ownership.setdefault(mp.player.id, None)

    def is_empty(self) -> bool:
        return not self.catalog

    def get_player(self, player_id: str) -> MarketPlayer | None:
        return self.catalog.get(player_id)

    def update_player(self, mp: MarketPlayer) -> None:
        self.catalog[mp.player.id] = mp

    def owner_of(self, player_id: str) -> str | None:
        return self.ownership.get(player_id)

    def set_owner(self, player_id: str, club_id: str) -> None:
        self.ownership[player_id] = club_id

    def elenco(self, club_id: str) -> list[str]:
        return [pid for pid, owner in self.ownership.items() if owner == club_id]

    def available_market(self) -> list[MarketPlayer]:
        return [mp for pid, mp in self.catalog.items()
                if self.ownership.get(pid) is None or pid in self._listings]

    # ── mercado P2P ────────────────────────────────────────────────────────
    def list_player(self, listing: Listing) -> None:
        self._listings[listing.player_id] = listing

    def delist_player(self, player_id: str) -> None:
        self._listings.pop(player_id, None)

    def get_listing(self, player_id: str) -> Listing | None:
        return self._listings.get(player_id)

    # ── ledger (único caminho para mexer no saldo) ─────────────────────────
    def post_ledger(
        self, club: Club, tipo: str, valor_fvs: int,
        ref: str | None = None, criado_em: str | None = None,
    ) -> LedgerEntry:
        entry = LedgerEntry(
            id=self.next_txn_id(), club_id=club.id, tipo=tipo,
            valor_fvs=valor_fvs, ref=ref, criado_em=criado_em,
        )
        self.ledger.append(entry)
        club.saldo_fvs += valor_fvs
        return entry

    def ledger_balance(self, club_id: str) -> int:
        return sum(e.valor_fvs for e in self.ledger if e.club_id == club_id)

    def get_ledger(self, club_id: str) -> list[LedgerEntry]:
        return [e for e in self.ledger if e.club_id == club_id]

    # ── temporada ──────────────────────────────────────────────────────────
    def save_season(self, season: SeasonState) -> None:
        self._seasons[season.club_id] = season

    def get_season(self, club_id: str) -> SeasonState | None:
        return self._seasons.get(club_id)

    # ── standings ──────────────────────────────────────────────────────────
    def get_clubs_by_division(self, divisao: str, exclude_id: str = "") -> list[Club]:
        return [c for c in self.clubs.values()
                if c.divisao == divisao and c.id != exclude_id]

    # ── autenticação ───────────────────────────────────────────────────────
    def save_api_key(self, user_id: str, key_hash: str) -> None:
        self._api_keys[key_hash] = user_id

    def get_user_id_for_key(self, key_hash: str) -> str | None:
        return self._api_keys.get(key_hash)

    # ── escalação ativa ────────────────────────────────────────────────────
    def save_lineup(self, club_id: str, lineup: Lineup) -> None:
        self._lineups[club_id] = lineup

    def get_lineup(self, club_id: str) -> Lineup | None:
        return self._lineups.get(club_id)

    def delete_lineup(self, club_id: str) -> None:
        self._lineups.pop(club_id, None)

    # ── relógio de mundo ───────────────────────────────────────────────────
    def get_last_tick_at(self) -> str | None:
        return self._world_clock

    def set_last_tick_at(self, epoch_str: str) -> None:
        self._world_clock = epoch_str

    def all_active_club_ids(self) -> list[str]:
        return [c.id for c in self.clubs.values()]
