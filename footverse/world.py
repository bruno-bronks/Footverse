"""Facade do mundo de jogo (Fase 1) — costura motor + estado.

Reúne o `Store`, o mercado gerado, as escalações ativas e a temporada de cada
clube, expondo as cinco ações do loop com nomes de domínio. A API HTTP é uma
casca fina sobre isto; testes podem exercer o loop sem subir servidor.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from . import config
from .domain.lineup import NO_VALID_LINEUP, Lineup, LineupError, validate_lineup
from .engine.market_gen import generate_market
from .engine.scoring import RoundScore, TitularSlot, score_round
from .state.economy import (
    CLUB_NOT_FOUND,
    CompraResult,
    EconomyError,
    ListingResult,
    cancelar_listagem,
    comprar_jogador,
    criar_clube,
    listar_jogador,
)
from .state.models import Club
from .state.season import (
    SEASON_ALREADY_CLOSED,
    SeasonError,
    SeasonResult,
    SeasonState,
    atualizar_forma_elenco,
    encerrar_temporada,
    proxima_temporada,
    registrar_rodada,
)
from .state.store import Store

# duração de uma rodada em segundos reais (Fase 3 — relógio de mundo);
# configurável via env var para dev/demo (padrão: 1 dia real)
ROUND_DURATION_SECONDS = int(os.environ.get("ROUND_DURATION_SECONDS", "86400"))


@dataclass(frozen=True)
class TickEvent:
    club_id: str
    tipo: str                       # "RODADA" | "TEMPORADA_ENCERRADA"
    rodada_id: str | None = None
    pontos: float | None = None
    resultado: str | None = None    # preenchido em TEMPORADA_ENCERRADA


@dataclass(frozen=True)
class TickResult:
    advanced: bool
    eventos: list[TickEvent] = field(default_factory=list)
    next_tick_in: float = 0.0


class World:
    def __init__(self, season_secret: str = "FOOTVERSE_S1", store: Store | None = None,
                ai_manager=None) -> None:
        self.season_secret = season_secret
        self.store = store if store is not None else Store()
        if self.store.is_empty():          # mundo novo: popula o mercado uma vez
            self.store.load_market(generate_market(season_secret))
        self.lineups: dict[str, Lineup] = {}
        self.seasons: dict[str, SeasonState] = {}
        # Fase 4: gerente de IA dos clubes autônomos. None = lazy import real
        # (agents.manager.ClubManager); injetável para testes sem chamar LLM.
        self._ai_manager = ai_manager

    # ── ações do loop ──────────────────────────────────────────────────────
    def criar_clube(self, user_id: str, nome: str, cores: list[str],
                    escudo: str | None = None) -> Club:
        club = criar_clube(self.store, user_id, nome, cores, escudo)
        season = SeasonState(
            season_secret=self.season_secret, temporada=1,
            divisao=club.divisao, club_id=club.id,
        )
        self.seasons[club.id] = season
        self.store.save_season(season)
        return club

    def criar_clube_ia(self, nome: str, cores: list[str],
                       personalidade: str = "equilibrado",
                       escudo: str | None = None) -> Club:
        """Cria um clube autônomo (Fase 4): joga sozinho via `ClubManager`.

        Usa o mesmo caminho de criação dos clubes humanos (mesma economia,
        mesmo orçamento inicial) — só marca o clube como gerenciado por IA.
        """
        import uuid
        user_id = f"ai_{uuid.uuid4().hex[:10]}"
        club = self.criar_clube(user_id, nome, cores, escudo)
        club.gerenciado_por_ia = True
        club.ia_personalidade = personalidade
        self.store.save_club(club)
        return club

    def comprar(self, club_id: str, player_id: str) -> CompraResult:
        return comprar_jogador(self.store, club_id, player_id)

    def listar_venda(self, club_id: str, player_id: str, preco_fvs: int) -> ListingResult:
        return listar_jogador(self.store, club_id, player_id, preco_fvs)

    def cancelar_venda(self, club_id: str, player_id: str) -> None:
        cancelar_listagem(self.store, club_id, player_id)

    def escalar(self, club_id: str, formacao: str,
                titulares: list[tuple[str, str]], reservas: list[str]) -> Lineup:
        self._require_club(club_id)
        squad = self._squad(club_id)
        lineup = validate_lineup(formacao, titulares, reservas, squad)
        self.lineups[club_id] = lineup
        self.store.save_lineup(club_id, lineup)
        return lineup

    def pontuar(self, club_id: str, rodada_id: str) -> RoundScore:
        self._require_club(club_id)
        lineup = self.lineups.get(club_id) or self.store.get_lineup(club_id)
        if lineup is None:
            raise LineupError(NO_VALID_LINEUP, "clube sem escalação ativa")
        self.lineups[club_id] = lineup   # popula cache se veio do store
        squad = self._squad(club_id)
        slots = [TitularSlot(squad[pid], slot) for pid, slot in lineup.titulares]
        club = self._require_club(club_id)
        rs = score_round(slots, club.divisao, self.season_secret, club_id, rodada_id)
        registrar_rodada(self.store, self._get_season(club_id), rodada_id, rs.pontos_centi)
        return rs

    def encerrar(self, club_id: str) -> SeasonResult:
        self._require_club(club_id)
        season = self._get_season(club_id)
        resultado = encerrar_temporada(self.store, season)
        # rollover atômico (SPEC-006 §4.6-4.7): forma nova + próxima temporada
        nova = proxima_temporada(self.store, season)
        atualizar_forma_elenco(self.store, self.season_secret, club_id, nova.temporada)
        self.seasons[club_id] = nova
        self.store.save_season(nova)
        self.lineups.pop(club_id, None)
        self.store.delete_lineup(club_id)
        # reabastece o mercado para a próxima temporada
        self.refresh_market(nova.temporada)
        return resultado

    def refresh_market(self, temporada: int) -> int:
        """Gera 50 novos jogadores para o mercado e os adiciona ao catálogo.

        Usa IDs únicos por temporada (`mkt_T{temporada}_*`) para não colidir
        com lotes anteriores. O mercado existente (não comprado) permanece.
        Retorna o número de jogadores adicionados.
        """
        novos = generate_market(
            f"{self.season_secret}_T{temporada}",
            id_prefix=f"mkt_T{temporada}",
        )
        self.store.load_market(novos)
        return len(novos)

    # ── clubes autônomos de IA (Fase 4) ─────────────────────────────────────
    def run_ai_manager(self, club_id: str) -> str | None:
        """Roda um ciclo de decisão do gerente de IA para `club_id`.

        Retorna o resumo textual das ações tomadas, ou `None` se a camada de
        agentes não estiver instalada ou a decisão falhar — nesses casos o
        clube simplesmente não age nesta rodada (DESIGN_DOC §4: "se a IA cair,
        o jogo continua").
        """
        if self._ai_manager is None:
            try:
                from .agents.manager import ClubManager
                self._ai_manager = ClubManager(self)
            except ImportError:
                return None
        try:
            return self._ai_manager.decide(club_id)
        except Exception:
            import logging
            logging.getLogger("footverse").exception(
                "erro no gerente de IA (club_id=%s)", club_id
            )
            return None

    # ── relógio de mundo (Fase 3) ───────────────────────────────────────────
    def tick(self, now: float | None = None) -> TickResult:
        """Avança o mundo em uma rodada, se `ROUND_DURATION_SECONDS` já passou.

        Pontua automaticamente todo clube com temporada ativa (usando a
        escalação salva, ou 0 pontos se não houver) e encerra temporadas que
        completarem RODADAS_POR_TEMPORADA. Idempotente dentro da janela: chamar
        de novo antes do intervalo configurado não tem efeito.
        """
        now = now if now is not None else time.time()
        last = self.store.get_last_tick_at()
        if last is not None and (now - float(last)) < ROUND_DURATION_SECONDS:
            return TickResult(advanced=False,
                              next_tick_in=ROUND_DURATION_SECONDS - (now - float(last)))

        eventos: list[TickEvent] = []
        for club_id in self.store.all_active_club_ids():
            stored_season = self.store.get_season(club_id)
            if stored_season is None or stored_season.status != "EM_ANDAMENTO":
                continue

            club = self.store.get_club(club_id)
            if club is not None and club.gerenciado_por_ia:
                self.run_ai_manager(club_id)   # pode comprar/vender/escalar antes da rodada

            season = self._get_season(club_id)
            rodada_idx = season.rodada_atual + 1
            rodada_id = f"auto_T{season.temporada}_R{rodada_idx}"

            lineup = self.lineups.get(club_id) or self.store.get_lineup(club_id)
            if lineup is not None:
                rs = self.pontuar(club_id, rodada_id)
                pontos = rs.pontos_centi / 100
            else:
                registrar_rodada(self.store, season, rodada_id, 0)
                pontos = 0.0
            eventos.append(TickEvent(club_id, "RODADA", rodada_id, pontos))

            if self._get_season(club_id).rodada_atual >= config.RODADAS_POR_TEMPORADA:
                resultado = self.encerrar(club_id)
                eventos.append(TickEvent(club_id, "TEMPORADA_ENCERRADA",
                                         resultado=resultado.resultado))

        self.store.set_last_tick_at(str(now))
        return TickResult(advanced=True, eventos=eventos, next_tick_in=float(ROUND_DURATION_SECONDS))

    def clock_status(self) -> dict:
        last = self.store.get_last_tick_at()
        if last is None:
            return {"last_tick_at": None, "next_tick_in": 0.0,
                    "round_duration_seconds": ROUND_DURATION_SECONDS}
        elapsed = time.time() - float(last)
        return {
            "last_tick_at": last,
            "next_tick_in": max(0.0, ROUND_DURATION_SECONDS - elapsed),
            "round_duration_seconds": ROUND_DURATION_SECONDS,
        }

    # ── leitura ────────────────────────────────────────────────────────────
    def club(self, club_id: str) -> Club:
        return self._require_club(club_id)

    def mercado_disponivel(self) -> list:
        return self.store.available_market()

    def standings(self, divisao: str) -> list[dict]:
        """Classificação ao vivo de todos os clubes da divisão."""
        clubs = self.store.get_clubs_by_division(divisao)
        rows = []
        for c in clubs:
            season = self.store.get_season(c.id)
            rows.append({
                "club_id": c.id,
                "nome": c.nome,
                "divisao": c.divisao,
                "pontos": c.pontos_temporada_centi / 100,
                "temporada": season.temporada if season else 1,
                "rodadas_jogadas": len(season.rodadas) if season else 0,
                "status": season.status if season else "EM_ANDAMENTO",
                "gerenciado_por_ia": c.gerenciado_por_ia,
            })
        rows.sort(key=lambda x: -x["pontos"])
        for i, row in enumerate(rows, start=1):
            row["posicao"] = i
        return rows

    # ── autenticação ───────────────────────────────────────────────────────
    def register_user(self, user_id: str) -> str:
        """Gera e persiste uma API key para o user_id. Retorna a chave raw."""
        from .auth import generate_key
        raw, key_hash = generate_key()
        self.store.save_api_key(user_id, key_hash)
        return raw

    def authenticate(self, raw_key: str) -> str | None:
        """Valida a chave e retorna o user_id, ou None se inválida."""
        from .auth import hash_key
        return self.store.get_user_id_for_key(hash_key(raw_key))

    # ── helpers ────────────────────────────────────────────────────────────
    def _get_season(self, club_id: str) -> SeasonState:
        if club_id not in self.seasons:
            s = self.store.get_season(club_id)
            if s is None:
                raise SeasonError(SEASON_ALREADY_CLOSED, f"sem temporada ativa para {club_id}")
            self.seasons[club_id] = s
        return self.seasons[club_id]

    def _require_club(self, club_id: str) -> Club:
        club = self.store.get_club(club_id)
        if club is None:
            raise EconomyError(CLUB_NOT_FOUND, club_id)
        return club

    def _squad(self, club_id: str) -> dict:
        return {pid: self.store.get_player(pid).player
                for pid in self.store.elenco(club_id)}


def build_world() -> World:
    """Constrói o mundo a partir do ambiente.

    `DATABASE_URL` definido → repositório SQL durável (SQLite/Postgres);
    ausente → in-memory. `FOOTVERSE_SEASON_SECRET` define a seed do mundo.
    """
    secret = os.environ.get("FOOTVERSE_SEASON_SECRET", "FOOTVERSE_S1")
    url = os.environ.get("DATABASE_URL")
    if url:
        from .state.sqlstore import SqlStore
        return World(secret, store=SqlStore(url))
    return World(secret)
