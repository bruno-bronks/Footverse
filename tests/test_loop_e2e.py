"""Loop completo da Fase 1, ponta a ponta: criar → comprar → escalar → pontuar → subir.

Costura todos os módulos do motor e prova duas coisas:
  - o loop fecha (um clube novo monta XI, pontua a temporada e progride);
  - é determinístico (mesma SEASON_SECRET ⇒ mesma temporada).
"""

from collections import defaultdict

from footverse import config
from footverse.domain.lineup import validate_lineup
from footverse.engine.market_gen import generate_market
from footverse.engine.scoring import TitularSlot, score_round
from footverse.state.economy import comprar_jogador, criar_clube
from footverse.state.season import (
    SeasonState,
    encerrar_temporada,
    registrar_rodada,
)
from footverse.state.store import Store

# 4-3-3 por setor: GOL1, DEF4 (ZAG,ZAG,LAT,LAT), MEI3 (VOL,MEI,MEI), ATA3 (EXT,EXT,ATA)
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"],
    "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"],
    "ATA": ["EXT", "EXT", "ATA"],
}


def _run_full_loop(secret: str) -> dict:
    store = Store()
    store.load_market(generate_market(secret))

    club = criar_clube(store, "user_1", "Império FC", ["#000000", "#D4AF37"])

    # compra o XI mais barato por setor (mercado barato → cabe nos 50M)
    por_setor: dict[str, list] = defaultdict(list)
    for mp in sorted(store.catalog.values(), key=lambda m: m.valor_fvs):
        por_setor[mp.setor].append(mp)

    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            comprar_jogador(store, club.id, mp.player.id)
            titulares.append((mp.player.id, slot))

    # escala (valida contra a SPEC-003)
    squad = {pid: store.catalog[pid].player for pid in store.elenco(club.id)}
    lineup = validate_lineup("4-3-3", titulares, [], squad)
    titular_slots = [TitularSlot(squad[pid], slot) for pid, slot in lineup.titulares]

    # pontua a temporada inteira
    season = SeasonState(season_secret=secret, temporada=1, divisao=club.divisao, club_id=club.id)
    for r in range(1, config.RODADAS_POR_TEMPORADA + 1):
        rodada_id = f"rod_{r}"
        rs = score_round(titular_slots, club.divisao, secret, club.id, rodada_id)
        registrar_rodada(store, season, rodada_id, rs.pontos_centi)

    resultado = encerrar_temporada(store, season)
    return {
        "elenco": len(store.elenco(club.id)),
        "formacao": lineup.formacao,
        "saldo": club.saldo_fvs,
        "ledger_balance": store.ledger_balance(club.id),
        "posicao": resultado.posicao_final,
        "resultado": resultado.resultado,
        "divisao_nova": resultado.divisao_nova,
        "pontos_pos_close": club.pontos_temporada_centi,
    }


def test_loop_closes_end_to_end():
    out = _run_full_loop("SEASON_SECRET")
    assert out["elenco"] == 11
    assert out["formacao"] == "4-3-3"
    assert out["saldo"] == out["ledger_balance"]      # reconciliação após compras + prêmio
    assert out["pontos_pos_close"] == 0               # reset no encerramento
    assert 1 <= out["posicao"] <= config.CLUBES_POR_DIVISAO
    assert out["resultado"] in {"CAMPEAO", "PROMOVIDO", "PERMANECE", "REBAIXADO"}


def test_loop_is_deterministic():
    assert _run_full_loop("SEASON_SECRET") == _run_full_loop("SEASON_SECRET")


def test_different_secret_changes_world():
    a = _run_full_loop("WORLD_A")
    b = _run_full_loop("WORLD_B")
    # mundos diferentes → ao menos um dos eixos (mercado/saldo/posição) difere
    assert (a["saldo"], a["posicao"]) != (b["saldo"], b["posicao"])
