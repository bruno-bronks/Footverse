# SPEC-005 — Jogador: Atributos, Valor de Mercado e Pontuação

**Status:** Rascunho
**Camada:** Motor determinístico (núcleo de modelagem)
**Depende de:** SPEC-003 (modelo de posição) · **Referenciada por:** SPEC-002 (preço de compra), SPEC-004 (pontuação da rodada), SPEC-001 (pré-condição: mercado populado)

---

## Objetivo
Definir, de forma **determinística e reprodutível**, quatro coisas que as outras specs deixaram em aberto:

1. **Modelo de atributos** do jogador (schema + faixas).
2. **Overall (OVR)** por posição — o número único derivado dos atributos.
3. **Fórmula de valor de mercado** (FV$) — usada por SPEC-002.
4. **Fórmula de pontuação por jogador** numa rodada — usada por SPEC-004.
5. **Geração do mercado barato de Série D** — a pré-condição de mundo que faz o loop fechar (clube nasce sem elenco).

Tudo aqui é **motor determinístico**: nenhum LLM participa. Regra fundadora do Design Doc §4.

---

## 1. Modelo de atributos

Cada jogador tem 7 atributos técnicos/físicos (escala **0–100**), mais idade e forma.

| Campo | Sigla | Faixa | Observação |
|-------|-------|-------|------------|
| `ritmo` | PAC | 0–100 | velocidade/aceleração |
| `finalizacao` | FIN | 0–100 | acabamento ofensivo |
| `passe` | PAS | 0–100 | passe/criação |
| `drible` | DRI | 0–100 | condução/1v1 |
| `defesa` | DEF | 0–100 | marcação/desarme |
| `fisico` | FIS | 0–100 | força/resistência |
| `goleiro` | GK | 0–100 | só relevante para `GOL` |
| `idade` | — | 16–40 | usada no valor |
| `forma` | — | 0–100 | dinâmica; default 70 no jogador novo |
| `posicao_natural` | — | enum SPEC-003 | uma das 8 posições finas |

> **Fase 1:** sem potencial/evolução, sem moral, sem lesões. `forma` muda só por gancho de temporada (SPEC-006), não nesta spec.

---

## 2. Overall (OVR) por posição

`OVR = round( Σ peso_posicao[attr] × attr )`, com os pesos abaixo (cada linha soma 1,00). Usa-se os pesos da **posição em que o jogador está sendo avaliado** (natural, para valor; do slot, para pontuação — ver §4).

| Posição | PAC | FIN | PAS | DRI | DEF | FIS | GK |
|---------|:---:|:---:|:---:|:---:|:---:|:---:|:--:|
| GOL  | 0.05 | —    | 0.10 | —    | —    | 0.15 | 0.70 |
| ZAG  | 0.10 | 0.05 | 0.10 | —    | 0.45 | 0.30 | — |
| LAT  | 0.25 | 0.05 | 0.15 | 0.10 | 0.30 | 0.15 | — |
| VOL  | 0.05 | 0.05 | 0.25 | 0.10 | 0.35 | 0.20 | — |
| MEI  | 0.10 | 0.15 | 0.35 | 0.25 | 0.10 | 0.05 | — |
| MEIA | 0.15 | 0.20 | 0.30 | 0.30 | —    | 0.05 | — |
| EXT  | 0.30 | 0.20 | 0.15 | 0.30 | —    | 0.05 | — |
| ATA  | 0.20 | 0.40 | 0.05 | 0.15 | —    | 0.20 | — |

OVR resultante fica na escala 0–100. (`—` = peso 0.)

---

## 3. Valor de mercado (FV$)

Régua **"milhões baixa"** (Design Doc §7): titular comum de Série D (~OVR 55) ≈ **3M**; craque (~OVR 75) ≈ **20M**.

```
valor_fvs = ROUND_100k( VALOR_REF × RATE^(OVR − OVR_REF) × fator_idade )
            com piso de PISO_VALOR
```

| Constante | Valor | Significado |
|-----------|-------|-------------|
| `VALOR_REF` | 3_000_000 | valor de um OVR de referência |
| `OVR_REF` | 55 | OVR de referência |
| `RATE` | 1.10 | cada +1 OVR ≈ +10% de valor (dobra a cada ~7 pts) |
| `PISO_VALOR` | 100_000 | ninguém é de graça |
| `ROUND_100k` | — | arredonda para o múltiplo de 100.000 mais próximo (half-up) |

**Determinismo do expoente:** `OVR − OVR_REF` é **inteiro**, então `RATE^k` é calculado por **multiplicação repetida** (exponenciação inteira), nunca por `pow()` de libm — assim o resultado é idêntico em qualquer plataforma. Para `k` negativo, usa-se `1 / RATE^(−k)`.

**`fator_idade`** (multiplicador, tabela determinística):

| Idade | ≤19 | 20–23 | 24–28 | 29–31 | 32–34 | ≥35 |
|-------|:---:|:-----:|:-----:|:-----:|:-----:|:---:|
| fator | 0.85 | 0.95 | 1.00 | 0.85 | 0.65 | 0.45 |

### Exemplos (verificáveis no Harness)
| OVR | Idade | Cálculo | `valor_fvs` |
|-----|-------|---------|-------------|
| 55 | 26 | 3M × 1.10⁰ × 1.00 | **3.000.000** |
| 75 | 26 | 3M × 1.10²⁰ × 1.00 ≈ 20.18M | **20.200.000** |
| 45 | 22 | 3M × 1.10⁻¹⁰ × 0.95 ≈ 1.10M | **1.100.000** |
| 35 | 33 | 3M × 1.10⁻²⁰ × 0.65 ≈ 0.29M | **300.000** |
| 62 | 30 | 3M × 1.10⁷ × 0.85 ≈ 4.97M | **5.000.000** |

> Confirma a régua: Série D vive na faixa **0,1M–5M**, com craques raros chegando a ~20M.

---

## 4. Pontuação por jogador na rodada (consome SPEC-004)

A SPEC-004 chama esta fórmula para cada titular e soma. Toda aleatoriedade vem da seed **derivada server-side** (SPEC-004): `seed = hash(SEASON_SECRET + club_id + rodada_id)`. Cada jogador e cada tipo de evento usa um **stream independente**: `rng(seed, player_id, "<stream>")`.

### 4.1 Nota (0–10)
```
ovr_slot   = OVR do jogador usando os pesos da POSIÇÃO DO SLOT (não a natural)
fator_forma= 0.90 + 0.20 × (forma / 100)              # 0.90–1.10
eps        = uniforme(-1.0, +1.0)  via rng(seed, player_id, "nota")
nota       = clamp( 5.0 + (ovr_slot − 50)/12 + (fator_forma − 1.0)×10 + eps×1.5 , 0.0, 10.0 )
```
(Usar o OVR do slot recompensa escalar o jogador na posição certa; como a elegibilidade da SPEC-003 é por setor, a diferença é pequena, mas existe.)

### 4.2 Eventos ofensivos (semeados, por jogador)
```
λ_gol    = GOAL_RATE   × peso_ataque[slot]  × (FIN/100) × (nota/7)
λ_assist = ASSIST_RATE × peso_criacao[slot] × (PAS/100) × (nota/7)
gols        = poisson(λ_gol,    rng(seed, player_id, "gol")),    teto 4
assistencias= poisson(λ_assist, rng(seed, player_id, "assist")), teto 3
```

| Slot | `peso_ataque` | `peso_criacao` |
|------|:---:|:---:|
| ATA | 1.00 | 0.50 |
| EXT | 0.80 | 0.80 |
| MEIA | 0.70 | 1.00 |
| MEI | 0.40 | 0.90 |
| VOL | 0.20 | 0.50 |
| LAT | 0.20 | 0.60 |
| ZAG | 0.15 | 0.20 |
| GOL | 0.00 | 0.00 |

`GOAL_RATE = 0.50`, `ASSIST_RATE = 0.40`.

### 4.3 Eventos defensivos (nível de time — clean sheet, gols sofridos, defesas)
Como na Fase 1 **não há confronto direto** (SPEC-004 fora de escopo), o adversário é uma **abstração** derivada da seed + divisão:
```
D = média( DEF e FIS de {GOL, ZAG, LAT, VOL} titulares, + GK do goleiro )   # força defensiva
O = FORCA_BASE_DIVISAO[divisao] × (1 + uniforme(-0.15,+0.15) via rng(seed, "adversario"))
λ_sofridos = clamp( BASE_GC × (O / D), 0, 6 )
gols_sofridos = poisson(λ_sofridos, rng(seed, "gols_sofridos"))             # 1× por time
clean_sheet   = (gols_sofridos == 0)
λ_defesas = clamp( DEF_RATE × (O / 100) × (GK/100), 0, 8 )                   # só GOL
defesas   = poisson(λ_defesas, rng(seed, "defesas"))
```
`FORCA_BASE_DIVISAO = {SERIE_D: 45, SERIE_C: 55, SERIE_B: 65, SERIE_A: 75}`, `BASE_GC = 1.2`, `DEF_RATE = 0.6`.

### 4.4 Conversão em pontos (centésimos — SPEC-004 §1b)
```
pts = NOTA_SCALE × (nota − 5.0)
    + gols          × PT_GOL
    + assistencias  × PT_ASSIST
    + (clean_sheet e slot ∈ {GOL,ZAG,LAT,VOL}) × PT_SG
    + (slot == GOL) × defesas × PT_DD
    − (slot ∈ {GOL,ZAG}) × gols_sofridos × PT_GS
```
armazenado como inteiro `pts_centi = round_half_up(pts × 100)`.

| Constante | Valor |
|-----------|:-----:|
| `NOTA_SCALE` | 2.0 |
| `PT_GOL` | 8.0 |
| `PT_ASSIST` | 5.0 |
| `PT_SG` | 5.0 |
| `PT_DD` | 1.0 |
| `PT_GS` | 1.0 |

### 4.5 Exemplo (substitui o breakdown ilustrativo da SPEC-004)
Atacante `ovr_slot=74`, `forma=90`, `FIN=80`, `PAS=60`; rodada que sorteou `nota=8.4`, `gols=1`, `assist=1`:
```
nota_part = 2.0 × (8.4 − 5.0) = 6.8
gol       = 1 × 8.0           = 8.0
assist    = 1 × 5.0           = 5.0
pts       = 19.8  →  pts_centi = 1980
```
Goleiro `GK=78`, time com `clean_sheet=true`, `defesas=4`, `nota=7.0`:
```
nota_part = 2.0 × (7.0 − 5.0) = 4.0
sg        = 5.0
defesas   = 4 × 1.0 = 4.0
pts       = 13.0  →  pts_centi = 1300
```

---

## 5. Pontuação do clube (liga SPEC-004 §3)
`pontos_clube_centi = Σ pts_centi dos 11 titulares`. Reservas não pontuam (Fase 1). Exibição = `pontos_centi / 100`.

---

## 6. Geração do mercado barato de Série D

Pré-condição do loop: o clube nasce sem elenco (SPEC-001) e precisa achar 11+ jogadores compráveis com 50M.

1. **Determinística por seed de mundo:** cada slot de jogador é gerado de `rng(SEASON_SECRET, "market", slot_idx)`. Recriar o mundo com a mesma `SEASON_SECRET` reproduz o mercado **idêntico**.
2. **Distribuição de OVR (Série D):** **OVR-alvo** `~ Normal(μ=50, σ=7)`, **clampado em [35, 70]**. Maioria 43–57; topo de Série D ~70 (≈ 12,5M no pico de idade), raro. OVR 75+ (o "craque ~20M" da §3) **é só âncora de escala — não aparece em Série D**; surge em divisões superiores. Escassez proposital.
3. **Atributos coerentes com o OVR:** gera-se cada atributo em torno de `OVR_alvo + viés_posicao[attr]` com jitter seeded, clampa [1,99]; depois **recalcula o OVR real** pela §2 a partir dos atributos gerados (o OVR é sempre a verdade derivada, nunca um campo solto). **Nota:** como o recálculo afasta levemente do alvo, a distribuição *realizada* de OVR é **aproximadamente** Normal(50,7), não exata — o alvo controla a tendência, não o valor final.
4. **Idade:** `Normal(μ=24, σ=4)` clampado [17, 36].
5. **Composição garantida:** o mercado de cada mundo novo contém pelo menos **`MIN_MERCADO_POR_SETOR`** jogadores compráveis por setor (GOL/DEF/MEI/ATA), garantindo que 50M montem um XI legal em qualquer formação da SPEC-003. Sugerido: `{GOL: 6, DEF: 16, MEI: 16, ATA: 12}` (≥ 50 jogadores).
6. **Preço = `valor_fvs` (§3)**, recalculado quando atributos/forma mudam (Fase 1: imutável dentro da temporada).

---

## 7. Constantes calibráveis (resumo)
| Grupo | Constantes |
|-------|-----------|
| Valor | `VALOR_REF=3M`, `OVR_REF=55`, `RATE=1.10`, `PISO_VALOR=100k`, `fator_idade[]` |
| Pontuação | `GOAL_RATE=0.50`, `ASSIST_RATE=0.40`, `BASE_GC=1.2`, `DEF_RATE=0.6`, `NOTA_SCALE=2.0`, `PT_GOL=8`, `PT_ASSIST=5`, `PT_SG=5`, `PT_DD=1`, `PT_GS=1` |
| Mundo | `FORCA_BASE_DIVISAO{}`, `MIN_MERCADO_POR_SETOR{}`, distribuições de OVR/idade |

Todas vivem num único módulo de configuração de economia/simulação — calibráveis sem tocar na lógica.

---

## 8. Determinismo (o ponto crítico)
- **Sem `float` no resultado final:** pontos saem em `pts_centi` (inteiro), valor em FV$ (inteiro). Cálculos intermediários em IEEE-754 double com **ordem de avaliação fixada**; arredondamento final **half-up**.
- **`RATE^k`** por exponenciação inteira (sem `pow` de libm).
- **PRNG fixo e especificado** (ex.: PCG32 / xorshift128+ com algoritmo congelado), nunca o RNG default da linguagem. Cada stream tem sub-seed próprio.
- **⚠️ Transcendentais são o maior risco cross-platform** — `exp()` na amostragem **Poisson** (§4.2–4.3) e `sin/cos/log/sqrt` na amostragem **Normal/Box-Muller** da geração de mercado (§6.2/6.4). Mitigar com **implementações congeladas** (não as da libm do SO): Poisson por soma de exponenciais com PRNG fixo; Normal por método **Ziggurat ou inversa-CDF tabelada** congelada. Cobrir com teste de reprodutibilidade explícito em mais de uma plataforma.

---

## 9. Invariantes (testáveis no Harness)
- **Valor monotônico no OVR:** para idade fixa, `OVR↑ ⇒ valor_fvs↑` (ou igual após arredondamento).
- **Ancoragem da régua:** `valor(OVR=55, idade=26) == 3_000_000` e `valor(OVR=75, idade=26) ∈ [20.0M, 20.5M]` (âncora de escala; OVR 75 não ocorre na Série D — ver §6.2).
- **Piso:** nenhum `valor_fvs < PISO_VALOR`.
- **OVR é derivado:** recalcular o OVR a partir dos atributos reproduz o valor armazenado (não há OVR "solto").
- **Reprodutibilidade da pontuação:** mesma seed + mesmos atributos ⇒ `pts_centi` idêntico (byte-a-byte).
- **Reprodutibilidade do mundo:** mesma `SEASON_SECRET` ⇒ mercado idêntico (mesmos jogadores, atributos e preços). *(A distribuição de OVR é aproximadamente Normal(50,7) — testar tendência/faixa, não conformidade exata.)*
- **Loop viável:** todo mundo gerado permite montar ao menos um XI legal (SPEC-003) dentro de `ORCAMENTO_INICIAL_FVS`.
- **Consistência interna:** `pontos_clube_centi == Σ titulares.pts_centi` (casa com SPEC-004).

---

## 10. Fora de escopo
- Potencial/evolução de atributos, crescimento por idade, scouting de jovens (Fase 2+).
- Química de time, moral, fadiga, lesões (Fase 2+).
- Confronto direto real entre dois clubes (Fase 2) — aqui o adversário é abstração de divisão.
- Variação de preço por demanda de mercado / inflação dinâmica (Fase 5).
