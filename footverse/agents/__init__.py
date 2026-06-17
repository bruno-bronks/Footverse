"""Camada de agentes assistivos do Footverse (DESIGN_DOC §4/§5).

Scout/Coach/Finance são LangGraph ReAct agents que APENAS leem o estado do
World e produzem conselho/narrativa em linguagem natural.

Regra fundadora: nenhuma tool aqui escreve estado de jogo. Se a camada de
IA cair, o motor determinístico continua funcionando normalmente.

Instalação: pip install '.[agents]'
"""

from __future__ import annotations
