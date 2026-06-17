"""Tools read-only para os agentes assistivos do Footverse.

Cada função é uma LangChain Tool criada via closure sobre o `World` e o
`club_id` alvo. Nenhuma tool modifica estado: não há chamadas a `criar_clube`,
`comprar`, `escalar`, `pontuar` ou `encerrar`. Violação dessa regra quebraria
o princípio fundador do DESIGN_DOC §4.
"""

from __future__ import annotations

from langchain_core.tools import tool

from .. import config
from ..world import World


def make_tools(world: World, club_id: str, memory=None) -> list:
    """Retorna as tools read-only para o clube `club_id`.

    Se `memory` (MemoryStore) for fornecido, adiciona a tool `buscar_historico`
    com busca semântica sobre o histórico do clube.
    """
    """Retorna as tools read-only para o clube `club_id`."""

    @tool
    def ver_clube() -> str:
        """Retorna nome, divisão, saldo FV$ e estado da temporada atual do clube."""
        club = world.store.get_club(club_id)
        if club is None:
            return f"Clube {club_id} não encontrado."
        season = world.store.get_season(club_id)
        rodadas = len(season.rodadas) if season else 0
        pontos = (club.pontos_temporada_centi / 100) if season else 0
        return (
            f"Clube: {club.nome}\n"
            f"Divisão: {club.divisao}\n"
            f"Saldo: FV${club.saldo_fvs:,}\n"
            f"Temporada {season.temporada if season else '?'} | "
            f"Rodadas jogadas: {rodadas}/{config.RODADAS_POR_TEMPORADA} | "
            f"Pontos: {pontos:.1f}"
        )

    @tool
    def ver_elenco() -> str:
        """Lista os jogadores do elenco: posição natural, OVR, forma e valor de mercado em FV$."""
        pids = world.store.elenco(club_id)
        if not pids:
            return "Elenco vazio — o clube ainda não comprou nenhum jogador."
        linhas = [f"Elenco ({len(pids)} jogadores):"]
        for pid in pids:
            mp = world.store.get_player(pid)
            if mp is None:
                continue
            linhas.append(
                f"  {pid} | {mp.player.posicao_natural} | "
                f"OVR {mp.ovr} | forma {mp.player.forma} | "
                f"idade {mp.player.idade} | FV${mp.valor_fvs:,}"
            )
        return "\n".join(linhas)

    @tool
    def ver_mercado() -> str:
        """Lista os jogadores disponíveis no mercado: posição, OVR e preço em FV$.
        Os jogadores estão ordenados por setor (GOL→DEF→MEI→ATA) e OVR decrescente."""
        mercado = world.mercado_disponivel()
        if not mercado:
            return "Mercado vazio."
        ordem_setor = {"GOL": 0, "DEF": 1, "MEI": 2, "ATA": 3}
        ordenado = sorted(mercado, key=lambda m: (ordem_setor.get(m.setor, 9), -m.ovr))
        linhas = [f"Mercado ({len(ordenado)} jogadores disponíveis):"]
        for mp in ordenado:
            linhas.append(
                f"  {mp.player.id} | {mp.player.posicao_natural} ({mp.setor}) | "
                f"OVR {mp.ovr} | forma {mp.player.forma} | "
                f"idade {mp.player.idade} | FV${mp.valor_fvs:,}"
            )
        return "\n".join(linhas)

    @tool
    def ver_escalacao() -> str:
        """Retorna a escalação ativa do clube (formação, titulares e reservas)."""
        lineup = world.lineups.get(club_id) or world.store.get_lineup(club_id)
        if lineup is None:
            return "Sem escalação ativa. Use a rota PUT /clubs/{id}/lineup para escalar."
        linhas = [f"Formação: {lineup.formacao}", "Titulares:"]
        for pid, slot in lineup.titulares:
            mp = world.store.get_player(pid)
            if mp:
                linhas.append(
                    f"  {slot}: {pid} | {mp.player.posicao_natural} | "
                    f"OVR {mp.ovr} | forma {mp.player.forma}"
                )
            else:
                linhas.append(f"  {slot}: {pid}")
        if lineup.reservas:
            linhas.append("Reservas:")
            for pid in lineup.reservas:
                mp = world.store.get_player(pid)
                info = f" | {mp.player.posicao_natural} | OVR {mp.ovr}" if mp else ""
                linhas.append(f"  {pid}{info}")
        return "\n".join(linhas)

    @tool
    def ver_ledger() -> str:
        """Retorna o saldo atual reconciliado com o ledger do clube (últimas movimentações)."""
        club = world.store.get_club(club_id)
        if club is None:
            return f"Clube {club_id} não encontrado."
        saldo_ledger = world.store.ledger_balance(club_id)
        return (
            f"Saldo em banco: FV${club.saldo_fvs:,}\n"
            f"Σ Ledger:       FV${saldo_ledger:,}\n"
            f"Reconciliado:   {'✓' if club.saldo_fvs == saldo_ledger else '✗ DIVERGÊNCIA'}"
        )

    tools = [ver_clube, ver_elenco, ver_mercado, ver_escalacao, ver_ledger]

    if memory is not None:
        @tool
        def buscar_historico(consulta: str) -> str:
            """Busca no histórico do clube: temporadas passadas, transferências,
            finanças e composição do elenco ao longo do tempo.
            Use para responder perguntas sobre o passado do clube.

            Exemplos: 'resultado das últimas temporadas', 'histórico financeiro',
            'jogadores que já tivemos', 'quando fomos rebaixados'.
            """
            return memory.search(consulta)

        tools.append(buscar_historico)

    return tools
