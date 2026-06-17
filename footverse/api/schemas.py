"""Schemas Pydantic da API (entrada/saída) — Fase 1."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..engine.market_gen import MarketPlayer
from ..engine.scoring import RoundScore
from ..state.economy import CompraResult
from ..state.models import Club
from ..state.season import SeasonResult


# ── entrada ────────────────────────────────────────────────────────────────
class CriarClubeIn(BaseModel):
    user_id: str
    nome: str
    cores: list[str]
    escudo: str | None = None


class CompraIn(BaseModel):
    player_id: str


class TitularIn(BaseModel):
    player_id: str
    posicao: str


class EscalacaoIn(BaseModel):
    formacao: str
    titulares: list[TitularIn]
    reservas: list[str] = Field(default_factory=list)


# ── saída ──────────────────────────────────────────────────────────────────
class ClubeOut(BaseModel):
    id: str
    user_id: str
    nome: str
    escudo: str | None
    cores: list[str]
    divisao: str
    pontos_temporada: float
    saldo_fvs: int
    gerenciado_por_ia: bool = False
    ia_personalidade: str | None = None

    @classmethod
    def of(cls, c: Club) -> "ClubeOut":
        return cls(
            id=c.id, user_id=c.user_id, nome=c.nome, escudo=c.escudo,
            cores=list(c.cores), divisao=c.divisao,
            pontos_temporada=c.pontos_temporada_centi / 100, saldo_fvs=c.saldo_fvs,
            gerenciado_por_ia=c.gerenciado_por_ia, ia_personalidade=c.ia_personalidade,
        )


class CompraOut(BaseModel):
    transacao_id: str
    club_id: str
    player_id: str
    valor_fvs: int
    saldo_anterior: int
    saldo_final: int
    tipo: str = "NPC"
    vendedor_club_id: str | None = None

    @classmethod
    def of(cls, r: CompraResult) -> "CompraOut":
        return cls(**r.__dict__)


class MarketPlayerOut(BaseModel):
    player_id: str
    posicao: str
    setor: str
    ovr: int
    idade: int
    valor_fvs: int
    vendedor_club_id: str | None = None  # None = NPC; preenchido em ofertas P2P

    @classmethod
    def of(cls, mp: MarketPlayer, vendedor_club_id: str | None = None) -> "MarketPlayerOut":
        return cls(
            player_id=mp.player.id, posicao=mp.player.posicao_natural, setor=mp.setor,
            ovr=mp.ovr, idade=mp.player.idade, valor_fvs=mp.valor_fvs,
            vendedor_club_id=vendedor_club_id,
        )


class EscalacaoOut(BaseModel):
    club_id: str
    formacao: str
    valida: bool
    titulares: int


class PlayerScoreOut(BaseModel):
    player_id: str
    slot: str
    pontos: float
    nota: float
    gols: int
    assistencias: int
    defesas: int
    gols_sofridos: int
    clean_sheet: bool


class RoundOut(BaseModel):
    club_id: str
    rodada_id: str
    pontos: float
    breakdown: list[PlayerScoreOut]

    @classmethod
    def of(cls, rs: RoundScore) -> "RoundOut":
        return cls(
            club_id=rs.club_id, rodada_id=rs.rodada_id, pontos=rs.pontos_centi / 100,
            breakdown=[
                PlayerScoreOut(
                    player_id=p.player_id, slot=p.slot, pontos=p.pts_centi / 100,
                    nota=p.nota, gols=p.gols, assistencias=p.assistencias,
                    defesas=p.defesas, gols_sofridos=p.gols_sofridos,
                    clean_sheet=p.clean_sheet,
                ) for p in rs.breakdown
            ],
        )


class SeasonOut(BaseModel):
    temporada: int
    divisao_anterior: str
    posicao_final: int
    resultado: str
    divisao_nova: str
    premiacao_fvs: int
    status: str

    @classmethod
    def of(cls, r: SeasonResult) -> "SeasonOut":
        return cls(**r.__dict__)


class SquadPlayerOut(BaseModel):
    player_id: str
    posicao: str
    setor: str
    ovr: int
    forma: int
    idade: int
    valor_fvs: int

    @classmethod
    def of(cls, mp: MarketPlayer) -> "SquadPlayerOut":
        return cls(
            player_id=mp.player.id, posicao=mp.player.posicao_natural,
            setor=mp.setor, ovr=mp.ovr, forma=mp.player.forma,
            idade=mp.player.idade, valor_fvs=mp.valor_fvs,
        )


class SeasonStateOut(BaseModel):
    temporada: int
    divisao: str
    status: str
    rodadas_jogadas: int
    rodadas_total: int
    pontos: float


class TitularOut(BaseModel):
    player_id: str
    slot: str


class LineupOut(BaseModel):
    formacao: str
    titulares: list[TitularOut]
    reservas: list[str]


# ── mercado P2P ────────────────────────────────────────────────────────────
class ListarVendaIn(BaseModel):
    preco_fvs: int


class ListingOut(BaseModel):
    player_id: str
    seller_club_id: str
    preco_fvs: int


# ── standings ─────────────────────────────────────────────────────────────
class StandingEntryOut(BaseModel):
    posicao: int
    club_id: str
    nome: str
    divisao: str
    pontos: float
    temporada: int
    rodadas_jogadas: int
    status: str
    gerenciado_por_ia: bool = False


# ── clubes autônomos de IA (Fase 4) ──────────────────────────────────────────
class CriarClubeIAIn(BaseModel):
    nome: str
    cores: list[str]
    personalidade: str = "equilibrado"
    escudo: str | None = None


class AiDecisionOut(BaseModel):
    club_id: str
    decisao: str


# ── feed de notícias ──────────────────────────────────────────────────────
class NewsItemOut(BaseModel):
    ts: float
    club_id: str
    tipo: str
    texto: str | None = None
    resultado: str | None = None


# ── autenticação ───────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    user_id: str


class AuthOut(BaseModel):
    user_id: str
    api_key: str


# ── agentes assistivos ─────────────────────────────────────────────────────
class PerguntaIn(BaseModel):
    pergunta: str


class ConselhoOut(BaseModel):
    agente: str
    club_id: str
    conselho: str
