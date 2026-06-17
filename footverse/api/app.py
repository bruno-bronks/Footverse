"""App FastAPI — expõe o loop da Fase 1/2 sobre o facade `World`.

Os erros de domínio (com `.code`) viram respostas HTTP com o status que as specs
já definiram (409/402/404/403/400), num único handler.

Fase 2: autenticação via Bearer token (API key). Endpoints de escrita verificam
posse do clube quando o token está presente; sem token, funcionam como Fase 1
(retrocompatível com testes legados).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .. import __version__
from ..domain.lineup import LineupError
from ..observability import RequestLogMiddleware, setup_logging
from ..state.economy import EconomyError
from ..state.season import SeasonError
from ..world import TickResult, World, build_world
from .schemas import (
    AiDecisionOut,
    AuthOut,
    ClubeOut,
    CompraIn,
    CompraOut,
    ConselhoOut,
    CriarClubeIAIn,
    CriarClubeIn,
    EscalacaoIn,
    EscalacaoOut,
    LineupOut,
    ListarVendaIn,
    ListingOut,
    MarketPlayerOut,
    NewsItemOut,
    PerguntaIn,
    RegisterIn,
    RoundOut,
    SeasonOut,
    SeasonStateOut,
    SquadPlayerOut,
    StandingEntryOut,
    TitularOut,
)

# código de erro de domínio -> status HTTP (SPEC-001..008)
STATUS: dict[str, int] = {
    # SPEC-001
    "CLUB_ALREADY_EXISTS": 409, "INVALID_NAME": 400,
    "INVALID_COLOR": 400, "TOO_MANY_COLORS": 400,
    # SPEC-002
    "CLUB_NOT_FOUND": 404, "PLAYER_NOT_FOUND": 404, "PLAYER_NOT_AVAILABLE": 409,
    "PLAYER_ALREADY_LISTED": 409, "CANNOT_BUY_OWN_PLAYER": 400,
    "PLAYER_NOT_LISTED": 404, "PLAYER_NOT_OWNED": 403,
    "INSUFFICIENT_FUNDS": 402, "SQUAD_FULL": 409,
    # SPEC-003 / SPEC-004
    "INVALID_LINEUP_SIZE": 400, "INVALID_GOALKEEPER_COUNT": 400, "INVALID_FORMATION": 400,
    "PLAYER_NOT_OWNED": 403, "DUPLICATE_PLAYER": 400, "INVALID_POSITION": 400,
    "NO_VALID_LINEUP": 409,
    # SPEC-006
    "SEASON_NOT_FINISHED": 409, "SEASON_ALREADY_CLOSED": 409,
    "SEASON_FULL": 409, "INVALID_DIVISION": 400,
}

_DomainError = (EconomyError, LineupError, SeasonError)
_bearer = HTTPBearer(auto_error=False)


def _publish_tick_events(app_state, result: TickResult) -> None:
    """Empurra os eventos de um tick para os assinantes SSE de cada clube."""
    for ev in result.eventos:
        payload = {
            "club_id": ev.club_id, "tipo": ev.tipo,
            "rodada_id": ev.rodada_id, "pontos": ev.pontos, "resultado": ev.resultado,
        }
        for q in app_state.subscribers.get(ev.club_id, []):
            q.put_nowait(payload)


def create_app(world: World | None = None) -> FastAPI:
    setup_logging()

    # relógio de mundo (Fase 3): tarefa de fundo que chama world.tick() em
    # intervalos curtos; o próprio tick() decide se ROUND_DURATION_SECONDS já
    # passou. Configurável via CLOCK_CHECK_INTERVAL_SECONDS (padrão 60s).
    _clock_check_interval = int(os.environ.get("CLOCK_CHECK_INTERVAL_SECONDS", "60"))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def _clock_loop() -> None:
            while True:
                await asyncio.sleep(_clock_check_interval)
                try:
                    # tick() pode bloquear por minutos (decisões de IA via
                    # LLM) — roda numa thread separada para não congelar o
                    # event loop e travar toda a API enquanto isso.
                    result = await asyncio.to_thread(app.state.world.tick)
                    _publish_tick_events(app.state, result)
                except Exception:
                    logging.getLogger("footverse").exception("erro no relógio de mundo")

        task = asyncio.create_task(_clock_loop())
        yield
        task.cancel()

    app = FastAPI(title="Footverse", version=__version__, lifespan=lifespan)
    app.add_middleware(RequestLogMiddleware)

    # CORS: permite origins configuradas via env (separadas por vírgula)
    # Em dev, usa wildcard; em produção, defina CORS_ORIGINS explicitamente.
    _origins_raw = os.environ.get("CORS_ORIGINS", "*")
    _origins = [o.strip() for o in _origins_raw.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=_origins_raw != "*",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.world = world or build_world()
    app.state.subscribers = {}   # club_id -> list[asyncio.Queue] (SSE)

    def _w(request: Request) -> World:
        return request.app.state.world

    async def _domain_handler(request: Request, exc: Exception) -> JSONResponse:
        code = getattr(exc, "code", "DOMAIN_ERROR")
        return JSONResponse(
            status_code=STATUS.get(code, 400),
            content={"error": code, "message": str(exc)},
        )

    for err in _DomainError:
        app.add_exception_handler(err, _domain_handler)

    # ── auth helpers ───────────────────────────────────────────────────────
    def get_optional_user(
        request: Request,
        creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> str | None:
        """Valida o Bearer token quando presente; retorna None se ausente."""
        if creds is None:
            return None
        user_id = _w(request).authenticate(creds.credentials)
        if user_id is None:
            raise HTTPException(status_code=401, detail="API key inválida")
        return user_id

    def _require_owner(w: World, club_id: str, user_id: str | None) -> None:
        """Quando autenticado, garante que o clube pertence ao usuário."""
        if user_id is None:
            return
        club = w.store.get_club(club_id)
        if club is None:
            raise HTTPException(status_code=404, detail="Clube não encontrado")
        if club.user_id != user_id:
            raise HTTPException(status_code=403, detail="Clube não pertence a você")

    # ── autenticação (SPEC-008) ────────────────────────────────────────────
    @app.post("/auth/register", response_model=AuthOut, status_code=201)
    def register(body: RegisterIn, request: Request) -> AuthOut:
        key = _w(request).register_user(body.user_id)
        return AuthOut(user_id=body.user_id, api_key=key)

    # ── leitura pública ────────────────────────────────────────────────────
    @app.get("/")
    def root() -> dict:
        return {"app": "Footverse", "version": __version__, "fase": 3}

    # ── relógio de mundo (Fase 3) ───────────────────────────────────────────
    @app.post("/admin/tick")
    async def admin_tick(request: Request) -> dict:
        """Força uma checagem do relógio — avança se o intervalo já passou.

        Roda em thread separada: pode levar minutos se houver clubes de IA
        decidindo, e isso não deve travar o resto da API nesse meio-tempo.
        """
        result = await asyncio.to_thread(_w(request).tick)
        _publish_tick_events(request.app.state, result)
        return {
            "advanced": result.advanced,
            "eventos": len(result.eventos),
            "next_tick_in": result.next_tick_in,
        }

    @app.get("/admin/clock")
    def clock_status(request: Request) -> dict:
        return _w(request).clock_status()

    # ── clubes autônomos de IA (Fase 4) ─────────────────────────────────────
    @app.post("/admin/ai-clubs", response_model=ClubeOut, status_code=201)
    def criar_clube_ia(body: CriarClubeIAIn, request: Request) -> ClubeOut:
        club = _w(request).criar_clube_ia(body.nome, body.cores, body.personalidade, body.escudo)
        return ClubeOut.of(club)

    @app.post("/admin/clubs/{club_id}/run-ai", response_model=AiDecisionOut)
    def run_ai_now(club_id: str, request: Request) -> AiDecisionOut:
        """Força uma decisão do gerente de IA agora, sem esperar o tick."""
        w = _w(request)
        w.club(club_id)  # 404 se não existir
        decisao = w.run_ai_manager(club_id)
        if decisao is None:
            raise HTTPException(
                status_code=503,
                detail="Camada de agentes não instalada ou decisão falhou.",
            )
        return AiDecisionOut(club_id=club_id, decisao=decisao)

    @app.get("/clubs/{club_id}/events")
    async def club_events(club_id: str, request: Request) -> StreamingResponse:
        """SSE: empurra eventos de rodada/temporada deste clube em tempo real."""
        _w(request).club(club_id)  # 404 se não existir
        queue: asyncio.Queue = asyncio.Queue()
        subs = request.app.state.subscribers.setdefault(club_id, [])
        subs.append(queue)

        async def gen():
            try:
                while True:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": heartbeat\n\n"
            finally:
                subs.remove(queue)

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/market", response_model=list[MarketPlayerOut])
    def market(request: Request) -> list[MarketPlayerOut]:
        w = _w(request)
        result = []
        for mp in w.mercado_disponivel():
            listing = w.store.get_listing(mp.player.id)
            result.append(MarketPlayerOut.of(
                mp,
                vendedor_club_id=listing.seller_club_id if listing else None,
            ))
        return result

    @app.post("/market/refresh", status_code=201)
    def market_refresh(request: Request) -> dict:
        w = _w(request)
        temporada = len(w.store.clubs) + 1
        added = w.refresh_market(temporada)
        return {"added": added, "total_available": len(w.mercado_disponivel())}

    @app.get("/divisions/{divisao}/standings", response_model=list[StandingEntryOut])
    def standings(divisao: str, request: Request) -> list[StandingEntryOut]:
        rows = _w(request).standings(divisao)
        return [StandingEntryOut(**row) for row in rows]

    @app.get("/news", response_model=list[NewsItemOut])
    def get_news(request: Request, club_id: str | None = None, limit: int = 20) -> list[NewsItemOut]:
        """Feed de notícias: decisões de IA, mudanças de personalidade,
        transferências P2P e encerramentos de temporada. Mais recente primeiro."""
        eventos = _w(request).news(club_id=club_id, limit=limit)
        return [
            NewsItemOut(ts=e.ts, club_id=e.club_id, tipo=e.tipo, texto=e.texto, resultado=e.resultado)
            for e in eventos
        ]

    @app.get("/clubs/{club_id}", response_model=ClubeOut)
    def get_club(club_id: str, request: Request) -> ClubeOut:
        return ClubeOut.of(_w(request).club(club_id))

    @app.get("/clubs/{club_id}/squad", response_model=list[SquadPlayerOut])
    def get_squad(club_id: str, request: Request) -> list[SquadPlayerOut]:
        w = _w(request)
        return [SquadPlayerOut.of(mp)
                for pid in w.store.elenco(club_id)
                if (mp := w.store.get_player(pid)) is not None]

    @app.get("/clubs/{club_id}/season", response_model=SeasonStateOut)
    def get_season(club_id: str, request: Request) -> SeasonStateOut:
        from .. import config as _cfg
        w = _w(request)
        season = w.store.get_season(club_id)
        if season is None:
            raise HTTPException(status_code=404, detail="Temporada não encontrada")
        club = w.club(club_id)
        return SeasonStateOut(
            temporada=season.temporada,
            divisao=season.divisao,
            status=season.status,
            rodadas_jogadas=len(season.rodadas),
            rodadas_total=_cfg.RODADAS_POR_TEMPORADA,
            pontos=club.pontos_temporada_centi / 100,
        )

    @app.get("/clubs/{club_id}/lineup", response_model=LineupOut)
    def get_lineup(club_id: str, request: Request) -> LineupOut:
        w = _w(request)
        lineup = w.lineups.get(club_id) or w.store.get_lineup(club_id)
        if lineup is None:
            raise HTTPException(status_code=404, detail="Sem escalação ativa")
        return LineupOut(
            formacao=lineup.formacao,
            titulares=[TitularOut(player_id=pid, slot=slot) for pid, slot in lineup.titulares],
            reservas=list(lineup.reservas),
        )

    # ── loop (escrita — verifica posse quando autenticado) ─────────────────
    @app.post("/clubs", response_model=ClubeOut, status_code=201)
    def criar_clube(
        body: CriarClubeIn, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> ClubeOut:
        user_id = current_user or body.user_id
        club = _w(request).criar_clube(user_id, body.nome, body.cores, body.escudo)
        return ClubeOut.of(club)

    # ── mercado P2P ─────────────────────────────────────────────────────────
    @app.post("/clubs/{club_id}/squad/{player_id}/list",
              response_model=ListingOut, status_code=201)
    def listar_venda(
        club_id: str, player_id: str, body: ListarVendaIn, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> ListingOut:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        r = w.listar_venda(club_id, player_id, body.preco_fvs)
        return ListingOut(player_id=r.player_id, seller_club_id=r.seller_club_id,
                          preco_fvs=r.preco_fvs)

    @app.delete("/clubs/{club_id}/squad/{player_id}/list")
    def cancelar_venda(
        club_id: str, player_id: str, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> Response:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        w.cancelar_venda(club_id, player_id)
        return Response(status_code=204)

    @app.get("/clubs/{club_id}/squad/{player_id}/list", response_model=ListingOut)
    def get_listing(club_id: str, player_id: str, request: Request) -> ListingOut:
        listing = _w(request).store.get_listing(player_id)
        if listing is None or listing.seller_club_id != club_id:
            raise HTTPException(status_code=404, detail="Listagem não encontrada")
        return ListingOut(player_id=listing.player_id,
                          seller_club_id=listing.seller_club_id,
                          preco_fvs=listing.preco_fvs)

    @app.post("/clubs/{club_id}/transfers", response_model=CompraOut, status_code=201)
    def comprar(
        club_id: str, body: CompraIn, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> CompraOut:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        return CompraOut.of(w.comprar(club_id, body.player_id))

    @app.put("/clubs/{club_id}/lineup", response_model=EscalacaoOut)
    def escalar(
        club_id: str, body: EscalacaoIn, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> EscalacaoOut:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        titulares = [(t.player_id, t.posicao) for t in body.titulares]
        lineup = w.escalar(club_id, body.formacao, titulares, body.reservas)
        return EscalacaoOut(club_id=club_id, formacao=lineup.formacao,
                            valida=True, titulares=len(lineup.titulares))

    @app.post("/clubs/{club_id}/rounds/{rodada_id}", response_model=RoundOut)
    def pontuar(
        club_id: str, rodada_id: str, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> RoundOut:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        return RoundOut.of(w.pontuar(club_id, rodada_id))

    @app.post("/clubs/{club_id}/season/close", response_model=SeasonOut)
    def encerrar(
        club_id: str, request: Request,
        current_user: str | None = Depends(get_optional_user),
    ) -> SeasonOut:
        w = _w(request)
        _require_owner(w, club_id, current_user)
        return SeasonOut.of(w.encerrar(club_id))

    # ── agentes assistivos (requerem [agents] instalado) ────────────────────
    def _advisor(request: Request):
        if not hasattr(request.app.state, "_advisor"):
            try:
                from ..agents.advisor import Advisor
                request.app.state._advisor = Advisor(_w(request))
            except ImportError:
                request.app.state._advisor = None
        adv = request.app.state._advisor
        if adv is None:
            raise HTTPException(
                status_code=503,
                detail="Camada de agentes não instalada. Execute: pip install '.[agents]'",
            )
        return adv

    @app.post("/clubs/{club_id}/ask/scout", response_model=ConselhoOut)
    def ask_scout(club_id: str, body: PerguntaIn, request: Request) -> ConselhoOut:
        conselho = _advisor(request).scout(club_id, body.pergunta)
        return ConselhoOut(agente="scout", club_id=club_id, conselho=conselho)

    @app.post("/clubs/{club_id}/ask/coach", response_model=ConselhoOut)
    def ask_coach(club_id: str, body: PerguntaIn, request: Request) -> ConselhoOut:
        conselho = _advisor(request).coach(club_id, body.pergunta)
        return ConselhoOut(agente="coach", club_id=club_id, conselho=conselho)

    @app.post("/clubs/{club_id}/ask/finance", response_model=ConselhoOut)
    def ask_finance(club_id: str, body: PerguntaIn, request: Request) -> ConselhoOut:
        conselho = _advisor(request).finance(club_id, body.pergunta)
        return ConselhoOut(agente="finance", club_id=club_id, conselho=conselho)

    # ── frontend estático (montado por último para não sombrear a API) ────────
    from pathlib import Path
    _dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if _dist.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(_dist), html=True), name="ui")

    return app


app = create_app()
