"""Geração de mercado — invariantes da SPEC-005 §6 / §9."""

from footverse import config
from footverse.domain.player import ATRIBUTOS, overall
from footverse.domain.positions import FORMACOES, POSICOES_POR_SETOR
from footverse.engine.market_gen import cheapest_xi_cost, generate_market


def test_market_is_reproducible():
    a = generate_market("SEASON_SECRET")
    b = generate_market("SEASON_SECRET")
    assert [m.player for m in a] == [m.player for m in b]
    assert [m.valor_fvs for m in a] == [m.valor_fvs for m in b]


def test_different_secret_changes_market():
    a = generate_market("SEASON_A")
    b = generate_market("SEASON_B")
    assert [m.valor_fvs for m in a] != [m.valor_fvs for m in b]


def test_composition_minimums_respected():
    mercado = generate_market("s")
    counts = {setor: 0 for setor in config.MIN_MERCADO_POR_SETOR}
    for mp in mercado:
        counts[mp.setor] += 1
    for setor, minimo in config.MIN_MERCADO_POR_SETOR.items():
        assert counts[setor] >= minimo


def test_attributes_and_age_in_range():
    for mp in generate_market("s"):
        for attr in ATRIBUTOS:
            assert 1 <= mp.player.atributos[attr] <= 99
        assert config.MERCADO_IDADE_MIN <= mp.player.idade <= config.MERCADO_IDADE_MAX
        assert config.MERCADO_OVR_MIN - 5 <= mp.ovr <= config.MERCADO_OVR_MAX + 5


def test_ovr_is_derived_truth():
    for mp in generate_market("s"):
        assert mp.ovr == overall(mp.player.atributos, mp.player.posicao_natural)


def test_value_never_below_floor():
    for mp in generate_market("s"):
        assert mp.valor_fvs >= config.PISO_VALOR


def test_position_belongs_to_its_sector():
    for mp in generate_market("s"):
        assert mp.player.posicao_natural in POSICOES_POR_SETOR[mp.setor]


def test_loop_viable_every_formation_within_budget():
    # invariante crítica do loop: todo mundo gerado permite montar um XI legal
    # com o orçamento inicial, em QUALQUER formação suportada.
    mercado = generate_market("s")
    for formacao in FORMACOES:
        custo = cheapest_xi_cost(mercado, formacao)
        assert custo is not None, formacao
        assert custo <= config.ORCAMENTO_INICIAL_FVS, (formacao, custo)


def test_ovr_distribution_tendency():
    mercado = generate_market("s")
    ovrs = [mp.ovr for mp in mercado]
    media = sum(ovrs) / len(ovrs)
    assert 42 <= media <= 56   # tendência ~50, aproximada (SPEC-005 §6.3)
