"""Tools de ação para o gerente de IA de clube (Fase 4).

Diferente de `tools.py` (somente leitura, usado pelos advisors assistivos),
estas tools EXECUTAM ações reais — mas sempre delegando ao `World`, que por
sua vez passa pelo motor determinístico (`comprar_jogador`, `validate_lineup`,
ledger). O agente nunca grava estado diretamente: ele só chama estas funções,
que chamam o `World`, que valida e executa (DESIGN_DOC §4).

Toda tool captura erros de domínio e os devolve como texto (em vez de deixar
a exceção propagar), para que o agente possa ler o motivo da falha e tentar
de novo com uma ação diferente — sem nunca travar o loop de decisão.
"""

from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel

from ..domain.lineup import LineupError
from ..state.economy import EconomyError
from ..world import World


class _TitularInput(BaseModel):
    player_id: str
    posicao: str


def make_action_tools(world: World, club_id: str) -> list:
    """Retorna as tools de ação (compra, venda, escalação) para `club_id`."""

    @tool
    def comprar_jogador(player_id: str) -> str:
        """Compra um jogador do mercado (NPC ou oferta P2P de outro clube).

        Debita o preço do saldo do clube via ledger. Falha se o saldo for
        insuficiente, o jogador não existir/estiver indisponível, ou o
        elenco já estiver no limite.
        """
        try:
            r = world.comprar(club_id, player_id)
            return f"Comprado {player_id} por FV${r.valor_fvs:,}. Saldo restante: FV${r.saldo_final:,}."
        except EconomyError as e:
            return f"ERRO ({e.code}): não foi possível comprar {player_id}."

    @tool
    def vender_jogador(player_id: str, preco_fvs: int) -> str:
        """Lista um jogador do elenco à venda no mercado P2P por um preço em FV$.

        O jogador continua no elenco até outro clube comprá-lo. Falha se o
        jogador não pertencer ao clube ou já estiver listado.
        """
        try:
            world.listar_venda(club_id, player_id, preco_fvs)
            return f"{player_id} listado à venda por FV${preco_fvs:,}."
        except EconomyError as e:
            return f"ERRO ({e.code}): não foi possível listar {player_id} à venda."

    @tool
    def cancelar_venda(player_id: str) -> str:
        """Cancela a listagem de venda de um jogador, mantendo-o no elenco."""
        try:
            world.cancelar_venda(club_id, player_id)
            return f"Listagem de {player_id} cancelada."
        except EconomyError as e:
            return f"ERRO ({e.code}): não foi possível cancelar a listagem de {player_id}."

    @tool
    def escalar_time(formacao: str, titulares: list[_TitularInput], reservas: list[str]) -> str:
        """Define a escalação do clube para a próxima rodada.

        `formacao` deve ser uma das suportadas: 4-3-3, 4-4-2, 3-5-2, 4-2-3-1,
        5-3-2, 3-4-3. `titulares` é uma lista de {player_id, posicao} (11
        jogadores, 1 goleiro). `reservas` é uma lista de player_ids extras.
        Falha se a escalação violar as regras (setor incompatível, jogador
        não pertence ao clube, formação inválida).
        """
        try:
            tit = [(t.player_id, t.posicao) for t in titulares]
            lineup = world.escalar(club_id, formacao, tit, reservas)
            return f"Escalação {formacao} definida com {len(lineup.titulares)} titulares."
        except LineupError as e:
            return f"ERRO ({e.code}): escalação inválida."

    return [comprar_jogador, vender_jogador, cancelar_venda, escalar_time]
