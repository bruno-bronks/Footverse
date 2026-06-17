"""Constantes calibráveis de economia e simulação.

Tudo que é "número de balanceamento" vive aqui — calibrável sem tocar na
lógica do motor. Referências: SPEC-005 (jogador/valor/pontuação) e
SPEC-006 (temporada/progressão).
"""

from __future__ import annotations

# ───────────────────────────── Economia (SPEC-001/002) ─────────────────────
ORCAMENTO_INICIAL_FVS: int = 50_000_000
MAX_ELENCO: int = 30

# ───────────────────────────── Valor de mercado (SPEC-005 §3) ───────────────
VALOR_REF: int = 3_000_000          # valor de um OVR de referência
OVR_REF: int = 55                   # OVR de referência
RATE: float = 1.10                  # cada +1 OVR ≈ +10% de valor
PISO_VALOR: int = 100_000           # ninguém é de graça
ROUND_STEP: int = 100_000           # arredondamento do valor (half-up)

# fator de idade (multiplicador determinístico) — faixas de SPEC-005 §3
def fator_idade(idade: int) -> float:
    if idade <= 19:
        return 0.85
    if idade <= 23:
        return 0.95
    if idade <= 28:
        return 1.00
    if idade <= 31:
        return 0.85
    if idade <= 34:
        return 0.65
    return 0.45

# ───────────────────────────── Pontuação por jogador (SPEC-005 §4) ──────────
GOAL_RATE: float = 0.50
ASSIST_RATE: float = 0.40
BASE_GC: float = 1.2                # gols sofridos base (nível de time)
DEF_RATE: float = 0.6              # taxa de defesas do goleiro

# pesos de papel ofensivo por posição do slot (SPEC-005 §4.2)
PESO_ATAQUE: dict[str, float] = {
    "ATA": 1.00, "EXT": 0.80, "MEIA": 0.70, "MEI": 0.40,
    "VOL": 0.20, "LAT": 0.20, "ZAG": 0.15, "GOL": 0.00,
}
PESO_CRIACAO: dict[str, float] = {
    "ATA": 0.50, "EXT": 0.80, "MEIA": 1.00, "MEI": 0.90,
    "VOL": 0.50, "LAT": 0.60, "ZAG": 0.20, "GOL": 0.00,
}

NOTA_SCALE: float = 2.0
PT_GOL: float = 8.0
PT_ASSIST: float = 5.0
PT_SG: float = 5.0                  # clean sheet (defensores/GOL)
PT_DD: float = 1.0                  # defesa difícil (GOL)
PT_GS: float = 1.0                  # gol sofrido (GOL/ZAG)

# ───────────────────────────── Mundo / divisões (SPEC-005 §4.3, SPEC-006) ───
DIVISOES: tuple[str, ...] = ("SERIE_A", "SERIE_B", "SERIE_C", "SERIE_D")

FORCA_BASE_DIVISAO: dict[str, int] = {
    "SERIE_A": 75,
    "SERIE_B": 65,
    "SERIE_C": 55,
    "SERIE_D": 45,
}

# geração do mercado barato (SPEC-005 §6)
MERCADO_OVR_MU: float = 50.0
MERCADO_OVR_SIGMA: float = 7.0
MERCADO_OVR_MIN: int = 35
MERCADO_OVR_MAX: int = 70
MERCADO_IDADE_MU: float = 24.0
MERCADO_IDADE_SIGMA: float = 4.0
MERCADO_IDADE_MIN: int = 17
MERCADO_IDADE_MAX: int = 36
MERCADO_ATTR_JITTER: float = 6.0   # desvio do ruído por atributo na geração
MIN_MERCADO_POR_SETOR: dict[str, int] = {"GOL": 6, "DEF": 16, "MEI": 16, "ATA": 12}

# ───────────────────────────── Temporada (SPEC-006) ─────────────────────────
CLUBES_POR_DIVISAO: int = 20
RODADAS_POR_TEMPORADA: int = 38
N_PROMOVIDOS: int = 4
N_REBAIXADOS: int = 4

MEDIA_PONTOS_NPC: dict[str, int] = {
    "SERIE_A": 80,
    "SERIE_B": 76,
    "SERIE_C": 72,
    "SERIE_D": 68,
}
DESVIO_PONTOS_NPC: float = 18.0

# premiação de fim de temporada por resultado (faucet via ledger, SPEC-006 §4.5)
PREMIO_POR_RESULTADO: dict[str, int] = {
    "CAMPEAO": 30_000_000,
    "PROMOVIDO": 8_000_000,
    "PERMANECE": 3_000_000,
    "REBAIXADO": 1_000_000,
}

# atualização de forma no rollover (SPEC-006 §5)
FORMA_MU: float = 65.0
FORMA_SIGMA: float = 12.0
FORMA_MIN: int = 30
FORMA_MAX: int = 95
