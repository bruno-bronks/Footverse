"""Footverse — motor determinístico da Fase 1.

A regra fundadora (Design Doc §4): tudo que afeta o jogo (saldo, pontos,
resultado) vem deste motor determinístico, nunca de um LLM. A camada de IA
apenas lê o estado e produz texto/sugestão.
"""

__version__ = "0.1.0"
