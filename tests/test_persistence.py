"""Persistência SQL (SqlStore) — reconciliação, durabilidade e portabilidade.

Roda sobre SQLite em arquivo (mesmo código vale para Postgres via DATABASE_URL).
"""

from collections import defaultdict

from footverse import config
from footverse.engine.market_gen import generate_market
from footverse.state.economy import comprar_jogador, criar_clube
from footverse.state.sqlstore import SqlStore
from footverse.world import World

_CORES = ["#000000", "#D4AF37"]
_NEED = {"GOL": 1, "DEF": 4, "MEI": 3, "ATA": 3}
_SLOTS = {
    "GOL": ["GOL"], "DEF": ["ZAG", "ZAG", "LAT", "LAT"],
    "MEI": ["VOL", "MEI", "MEI"], "ATA": ["EXT", "EXT", "ATA"],
}


def _url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'footverse.db'}"


def _montar_e_escalar(world: World, club_id: str) -> None:
    por_setor = defaultdict(list)
    for mp in sorted(world.mercado_disponivel(), key=lambda m: m.valor_fvs):
        por_setor[mp.setor].append(mp)
    titulares = []
    for setor, n in _NEED.items():
        for mp, slot in zip(por_setor[setor][:n], _SLOTS[setor]):
            world.comprar(club_id, mp.player.id)
            titulares.append((mp.player.id, slot))
    world.escalar(club_id, "4-3-3", titulares, [])


# ── reconciliação em SQL ─────────────────────────────────────────────────────
def test_sqlstore_reconciles_ledger(tmp_path):
    store = SqlStore(_url(tmp_path))
    store.load_market([])  # mercado vazio basta para este teste
    club = criar_clube(store, "u", "Clube X", _CORES)
    assert store.get_club(club.id).saldo_fvs == config.ORCAMENTO_INICIAL_FVS
    assert store.ledger_balance(club.id) == config.ORCAMENTO_INICIAL_FVS


def test_sqlstore_buy_debits_and_reconciles(tmp_path):
    store = SqlStore(_url(tmp_path))
    store.load_market(generate_market("SEC"))
    club = criar_clube(store, "u", "Clube X", _CORES)
    barato = min(store.available_market(), key=lambda m: m.valor_fvs)
    r = comprar_jogador(store, club.id, barato.player.id)
    persisted = store.get_club(club.id)
    assert persisted.saldo_fvs == r.saldo_final
    assert store.ledger_balance(club.id) == persisted.saldo_fvs
    assert store.owner_of(barato.player.id) == club.id


# ── durabilidade através de reabertura ───────────────────────────────────────
def test_state_survives_reopen(tmp_path):
    url = _url(tmp_path)

    w1 = World("SEC", store=SqlStore(url))
    club = w1.criar_clube("u", "Império FC", _CORES)
    cid = club.id
    pid = w1.mercado_disponivel()[0].player.id
    w1.comprar(cid, pid)
    saldo = w1.store.get_club(cid).saldo_fvs

    # nova instância, mesmo banco: estado persiste, mercado não duplica
    w2 = World("SEC", store=SqlStore(url))
    persisted = w2.store.get_club(cid)
    assert persisted is not None
    assert persisted.saldo_fvs == saldo
    assert w2.store.ledger_balance(cid) == persisted.saldo_fvs
    assert w2.store.owner_of(pid) == cid
    assert len(w2.mercado_disponivel()) == 49   # 50 − 1 vendido, sem recarregar


# ── temporada (rodadas) persiste e é retomada após restart ───────────────────
def test_season_survives_reopen(tmp_path):
    url = _url(tmp_path)

    w1 = World("SEC", store=SqlStore(url))
    club = w1.criar_clube("u", "Império FC", _CORES)
    cid = club.id
    _montar_e_escalar(w1, cid)

    # pontua metade das rodadas e fecha o World
    half = config.RODADAS_POR_TEMPORADA // 2
    for r in range(1, half + 1):
        w1.pontuar(cid, f"rod_{r}")

    # reabre — season deve ser lazy-carregada com as rodadas já registradas
    w2 = World("SEC", store=SqlStore(url))
    season = w2.store.get_season(cid)
    assert season is not None
    assert len(season.rodadas) == half
    assert season.status == "EM_ANDAMENTO"

    # continua pontuando a partir de onde parou
    for r in range(half + 1, config.RODADAS_POR_TEMPORADA + 1):
        w2.pontuar(cid, f"rod_{r}")

    resultado = w2.encerrar(cid)
    assert resultado.temporada == 1
    # nova temporada foi persistida
    nova = w2.store.get_season(cid)
    assert nova.temporada == 2
    assert nova.status == "EM_ANDAMENTO"


# ── escalação persiste e é retomada após restart ──────────────────────────────
def test_lineup_survives_reopen(tmp_path):
    url = _url(tmp_path)

    w1 = World("SEC", store=SqlStore(url))
    club = w1.criar_clube("u", "Atlético DB", _CORES)
    cid = club.id
    _montar_e_escalar(w1, cid)

    # reabre sem pontuar — lineup deve ser lazy-carregada do banco
    w2 = World("SEC", store=SqlStore(url))
    lineup = w2.store.get_lineup(cid)
    assert lineup is not None
    assert lineup.formacao == "4-3-3"
    assert len(lineup.titulares) == 11

    # pontuar deve funcionar via lazy-load da lineup (pontos podem ser negativos)
    rs = w2.pontuar(cid, "rod_1")
    assert isinstance(rs.pontos_centi, int)


# ── divisão persiste após encerrar temporada ─────────────────────────────────
def test_division_persists_after_season(tmp_path):
    url = _url(tmp_path)

    w1 = World("SEC", store=SqlStore(url))
    club = w1.criar_clube("u", "Clube X", _CORES)
    cid = club.id
    _montar_e_escalar(w1, cid)
    for r in range(1, config.RODADAS_POR_TEMPORADA + 1):
        w1.pontuar(cid, f"rod_{r}")
    resultado = w1.encerrar(cid)

    # a divisão nova foi salva no banco (via save_club no encerramento)
    w2 = World("SEC", store=SqlStore(url))
    assert w2.store.get_club(cid).divisao == resultado.divisao_nova
    assert w2.store.ledger_balance(cid) == w2.store.get_club(cid).saldo_fvs
