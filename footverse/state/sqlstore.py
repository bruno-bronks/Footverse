"""Repositório SQL (SQLAlchemy Core) — durável, portátil SQLite ↔ Postgres.

Mesma interface do `Store` in-memory. O ledger é uma tabela e continua sendo a
fonte de verdade do saldo: `post_ledger` insere o lançamento e ajusta o saldo
do clube na mesma transação.

URL padrão: `sqlite:///footverse.db` (zero-config, persiste em disco). Em
produção, basta `DATABASE_URL=postgresql+psycopg://...` — o código não muda.
"""

from __future__ import annotations

import json
import os

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete as sql_delete,
    func,
    insert,
    select,
    update,
)

from ..domain.lineup import Lineup
from ..domain.player import Player
from ..engine.market_gen import MarketPlayer
from .models import Club, LedgerEntry, Listing
from .season import SeasonState


def _build_tables(md: MetaData) -> dict:
    return {
        "counters": Table(
            "counters", md,
            Column("name", String, primary_key=True),
            Column("value", Integer, nullable=False),
        ),
        "clubs": Table(
            "clubs", md,
            Column("id", String, primary_key=True),
            Column("user_id", String, index=True, nullable=False),
            Column("nome", String, nullable=False),
            Column("escudo", String, nullable=True),
            Column("cores", Text, nullable=False),            # json
            Column("divisao", String, nullable=False),
            Column("pontos_temporada_centi", Integer, nullable=False),
            Column("saldo_fvs", Integer, nullable=False),
            Column("criado_em", String, nullable=True),
            Column("gerenciado_por_ia", Integer, nullable=False, default=0),
            Column("ia_personalidade", String, nullable=True),
        ),
        "players": Table(
            "players", md,
            Column("id", String, primary_key=True),
            Column("posicao_natural", String, nullable=False),
            Column("atributos", Text, nullable=False),        # json
            Column("idade", Integer, nullable=False),
            Column("forma", Integer, nullable=False),
            Column("ovr", Integer, nullable=False),
            Column("valor_fvs", Integer, nullable=False),
            Column("setor", String, nullable=False),
            Column("club_id", String, index=True, nullable=True),
        ),
        "ledger": Table(
            "ledger", md,
            Column("id", String, primary_key=True),
            Column("club_id", String, index=True, nullable=False),
            Column("tipo", String, nullable=False),
            Column("valor_fvs", Integer, nullable=False),
            Column("ref", String, nullable=True),
            Column("criado_em", String, nullable=True),
        ),
        "seasons": Table(
            "seasons", md,
            Column("club_id", String, primary_key=True),
            Column("season_secret", String, nullable=False),
            Column("temporada", Integer, nullable=False),
            Column("divisao", String, nullable=False),
            Column("rodadas", Text, nullable=False),   # json: {rodada_id: pontos_centi}
            Column("status", String, nullable=False),
        ),
        "lineups": Table(
            "lineups", md,
            Column("club_id", String, primary_key=True),
            Column("formacao", String, nullable=False),
            Column("titulares", Text, nullable=False),  # json: [[pid, slot], ...]
            Column("reservas", Text, nullable=False),   # json: [pid, ...]
        ),
        "api_keys": Table(
            "api_keys", md,
            Column("key_hash", String, primary_key=True),
            Column("user_id", String, index=True, nullable=False),
            Column("criado_em", String, nullable=True),
        ),
        "listings": Table(
            "listings", md,
            Column("player_id", String, primary_key=True),
            Column("seller_club_id", String, index=True, nullable=False),
            Column("preco_fvs", Integer, nullable=False),
            Column("criado_em", String, nullable=True),
        ),
        "world_clock": Table(
            "world_clock", md,
            Column("singleton", String, primary_key=True),
            Column("last_tick_at", String, nullable=False),
        ),
    }


def _club_from_row(r) -> Club:
    return Club(
        id=r.id, user_id=r.user_id, nome=r.nome, escudo=r.escudo,
        cores=tuple(json.loads(r.cores)), divisao=r.divisao,
        pontos_temporada_centi=r.pontos_temporada_centi,
        saldo_fvs=r.saldo_fvs, criado_em=r.criado_em,
        gerenciado_por_ia=bool(r.gerenciado_por_ia), ia_personalidade=r.ia_personalidade,
    )


def _mp_from_row(r) -> MarketPlayer:
    player = Player(id=r.id, posicao_natural=r.posicao_natural,
                    atributos=json.loads(r.atributos), idade=r.idade, forma=r.forma)
    return MarketPlayer(player=player, ovr=r.ovr, valor_fvs=r.valor_fvs, setor=r.setor)


class SqlStore:
    def __init__(self, url: str | None = None) -> None:
        url = url or os.environ.get("DATABASE_URL", "sqlite:///footverse.db")
        self.engine = create_engine(url, future=True)
        self.md = MetaData()
        t = _build_tables(self.md)
        self.counters, self.clubs, self.players, self.ledger = (
            t["counters"], t["clubs"], t["players"], t["ledger"]
        )
        self.seasons, self.lineups, self.api_keys, self.listings, self.world_clock = (
            t["seasons"], t["lineups"], t["api_keys"], t["listings"], t["world_clock"]
        )
        self.md.create_all(self.engine)

    # ── ids ────────────────────────────────────────────────────────────────
    def _next(self, name: str) -> int:
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.counters.c.value).where(self.counters.c.name == name)
            ).first()
            if row is None:
                conn.execute(insert(self.counters).values(name=name, value=1))
                return 1
            v = row[0] + 1
            conn.execute(update(self.counters).where(
                self.counters.c.name == name).values(value=v))
            return v

    def next_club_id(self) -> str:
        return f"club_{self._next('club')}"

    def next_txn_id(self) -> str:
        return f"txn_{self._next('txn')}"

    # ── clubes ──────────────────────────────────────────────────────────────
    def add_club(self, club: Club) -> None:
        with self.engine.begin() as conn:
            conn.execute(insert(self.clubs).values(
                id=club.id, user_id=club.user_id, nome=club.nome, escudo=club.escudo,
                cores=json.dumps(list(club.cores)), divisao=club.divisao,
                pontos_temporada_centi=club.pontos_temporada_centi,
                saldo_fvs=club.saldo_fvs, criado_em=club.criado_em,
                gerenciado_por_ia=int(club.gerenciado_por_ia),
                ia_personalidade=club.ia_personalidade,
            ))

    def get_club(self, club_id: str) -> Club | None:
        with self.engine.connect() as conn:
            r = conn.execute(select(self.clubs).where(self.clubs.c.id == club_id)).first()
        return _club_from_row(r) if r else None

    def get_user_club(self, user_id: str) -> str | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.clubs.c.id).where(self.clubs.c.user_id == user_id)
            ).first()
        return r[0] if r else None

    def save_club(self, club: Club) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(self.clubs).where(self.clubs.c.id == club.id).values(
                nome=club.nome, escudo=club.escudo, divisao=club.divisao,
                pontos_temporada_centi=club.pontos_temporada_centi,
                saldo_fvs=club.saldo_fvs,
                gerenciado_por_ia=int(club.gerenciado_por_ia),
                ia_personalidade=club.ia_personalidade,
            ))

    # ── jogadores / mercado ────────────────────────────────────────────────
    def load_market(self, mercado: list[MarketPlayer]) -> None:
        rows = [{
            "id": mp.player.id, "posicao_natural": mp.player.posicao_natural,
            "atributos": json.dumps(mp.player.atributos), "idade": mp.player.idade,
            "forma": mp.player.forma, "ovr": mp.ovr, "valor_fvs": mp.valor_fvs,
            "setor": mp.setor, "club_id": None,
        } for mp in mercado]
        if rows:
            with self.engine.begin() as conn:
                conn.execute(insert(self.players), rows)

    def is_empty(self) -> bool:
        with self.engine.connect() as conn:
            n = conn.execute(select(func.count()).select_from(self.players)).scalar()
        return n == 0

    def get_player(self, player_id: str) -> MarketPlayer | None:
        with self.engine.connect() as conn:
            r = conn.execute(select(self.players).where(self.players.c.id == player_id)).first()
        return _mp_from_row(r) if r else None

    def update_player(self, mp: MarketPlayer) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(self.players).where(self.players.c.id == mp.player.id).values(
                atributos=json.dumps(mp.player.atributos), forma=mp.player.forma,
                ovr=mp.ovr, valor_fvs=mp.valor_fvs,
            ))

    def owner_of(self, player_id: str) -> str | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.players.c.club_id).where(self.players.c.id == player_id)
            ).first()
        return r[0] if r else None

    def set_owner(self, player_id: str, club_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(update(self.players).where(
                self.players.c.id == player_id).values(club_id=club_id))

    def elenco(self, club_id: str) -> list[str]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(self.players.c.id).where(self.players.c.club_id == club_id)
            ).all()
        return [r[0] for r in rows]

    def available_market(self) -> list[MarketPlayer]:
        with self.engine.connect() as conn:
            # NPC (unowned) + jogadores listados por humanos
            listed_ids = [r[0] for r in conn.execute(
                select(self.listings.c.player_id)
            ).all()]
            rows = conn.execute(
                select(self.players).where(
                    self.players.c.club_id.is_(None) |
                    self.players.c.id.in_(listed_ids)
                )
            ).all()
        return [_mp_from_row(r) for r in rows]

    # ── mercado P2P ───────────────────────────────────────────────────────────
    def list_player(self, listing: Listing) -> None:
        with self.engine.begin() as conn:
            self._upsert(conn, self.listings, "player_id", listing.player_id, {
                "player_id": listing.player_id,
                "seller_club_id": listing.seller_club_id,
                "preco_fvs": listing.preco_fvs,
                "criado_em": listing.criado_em,
            })

    def delist_player(self, player_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(sql_delete(self.listings).where(
                self.listings.c.player_id == player_id
            ))

    def get_listing(self, player_id: str) -> Listing | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.listings).where(self.listings.c.player_id == player_id)
            ).first()
        if r is None:
            return None
        return Listing(player_id=r.player_id, seller_club_id=r.seller_club_id,
                       preco_fvs=r.preco_fvs, criado_em=r.criado_em)

    # ── ledger ───────────────────────────────────────────────────────────────
    def post_ledger(
        self, club: Club, tipo: str, valor_fvs: int,
        ref: str | None = None, criado_em: str | None = None,
    ) -> LedgerEntry:
        txn_id = self.next_txn_id()
        with self.engine.begin() as conn:
            conn.execute(insert(self.ledger).values(
                id=txn_id, club_id=club.id, tipo=tipo,
                valor_fvs=valor_fvs, ref=ref, criado_em=criado_em,
            ))
            conn.execute(update(self.clubs).where(self.clubs.c.id == club.id).values(
                saldo_fvs=self.clubs.c.saldo_fvs + valor_fvs,
            ))
        club.saldo_fvs += valor_fvs   # mantém o objeto do chamador coerente
        return LedgerEntry(id=txn_id, club_id=club.id, tipo=tipo,
                           valor_fvs=valor_fvs, ref=ref, criado_em=criado_em)

    def ledger_balance(self, club_id: str) -> int:
        with self.engine.connect() as conn:
            s = conn.execute(
                select(func.coalesce(func.sum(self.ledger.c.valor_fvs), 0))
                .where(self.ledger.c.club_id == club_id)
            ).scalar()
        return int(s)

    def get_ledger(self, club_id: str) -> list[LedgerEntry]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(self.ledger).where(self.ledger.c.club_id == club_id)
            ).all()
        return [
            LedgerEntry(
                id=r.id, club_id=r.club_id, tipo=r.tipo,
                valor_fvs=r.valor_fvs, ref=r.ref, criado_em=r.criado_em,
            )
            for r in rows
        ]

    # ── temporada ─────────────────────────────────────────────────────────────
    def _upsert(self, conn, table, pk_col: str, pk_val: str, data: dict) -> None:
        exists = conn.execute(
            select(table.c[pk_col]).where(table.c[pk_col] == pk_val)
        ).first()
        if exists:
            conn.execute(
                update(table).where(table.c[pk_col] == pk_val)
                .values(**{k: v for k, v in data.items() if k != pk_col})
            )
        else:
            conn.execute(insert(table).values(**data))

    def save_season(self, season: SeasonState) -> None:
        data = {
            "club_id": season.club_id,
            "season_secret": season.season_secret,
            "temporada": season.temporada,
            "divisao": season.divisao,
            "rodadas": json.dumps(season.rodadas),
            "status": season.status,
        }
        with self.engine.begin() as conn:
            self._upsert(conn, self.seasons, "club_id", season.club_id, data)

    def get_season(self, club_id: str) -> SeasonState | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.seasons).where(self.seasons.c.club_id == club_id)
            ).first()
        if r is None:
            return None
        return SeasonState(
            season_secret=r.season_secret, temporada=r.temporada,
            divisao=r.divisao, club_id=r.club_id,
            rodadas=json.loads(r.rodadas), status=r.status,
        )

    # ── escalação ativa ───────────────────────────────────────────────────────
    def save_lineup(self, club_id: str, lineup: Lineup) -> None:
        data = {
            "club_id": club_id,
            "formacao": lineup.formacao,
            "titulares": json.dumps(list(lineup.titulares)),
            "reservas": json.dumps(list(lineup.reservas)),
        }
        with self.engine.begin() as conn:
            self._upsert(conn, self.lineups, "club_id", club_id, data)

    def get_lineup(self, club_id: str) -> Lineup | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.lineups).where(self.lineups.c.club_id == club_id)
            ).first()
        if r is None:
            return None
        return Lineup(
            formacao=r.formacao,
            titulares=tuple(tuple(t) for t in json.loads(r.titulares)),
            reservas=tuple(json.loads(r.reservas)),
        )

    def delete_lineup(self, club_id: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(sql_delete(self.lineups).where(self.lineups.c.club_id == club_id))

    # ── standings ─────────────────────────────────────────────────────────────
    def get_clubs_by_division(self, divisao: str, exclude_id: str = "") -> list[Club]:
        with self.engine.connect() as conn:
            q = select(self.clubs).where(self.clubs.c.divisao == divisao)
            if exclude_id:
                q = q.where(self.clubs.c.id != exclude_id)
            rows = conn.execute(q).all()
        return [_club_from_row(r) for r in rows]

    # ── autenticação ──────────────────────────────────────────────────────────
    def save_api_key(self, user_id: str, key_hash: str) -> None:
        with self.engine.begin() as conn:
            self._upsert(conn, self.api_keys, "key_hash", key_hash,
                         {"key_hash": key_hash, "user_id": user_id})

    def get_user_id_for_key(self, key_hash: str) -> str | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.api_keys.c.user_id)
                .where(self.api_keys.c.key_hash == key_hash)
            ).first()
        return r[0] if r else None

    # ── relógio de mundo ──────────────────────────────────────────────────────
    def get_last_tick_at(self) -> str | None:
        with self.engine.connect() as conn:
            r = conn.execute(
                select(self.world_clock.c.last_tick_at)
                .where(self.world_clock.c.singleton == "singleton")
            ).first()
        return r[0] if r else None

    def set_last_tick_at(self, epoch_str: str) -> None:
        with self.engine.begin() as conn:
            self._upsert(conn, self.world_clock, "singleton", "singleton",
                         {"singleton": "singleton", "last_tick_at": epoch_str})

    def all_active_club_ids(self) -> list[str]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(self.clubs.c.id)).all()
        return [r[0] for r in rows]
