# Backtest KO held-out — modelo a 120' (c=⅓) vs sin alargue (c=0)

**Confirmatorio (N chico), NO decisorio.** El gate del modelo de penales/ET es corrección teórica
+ oráculo (D14); este backtest apoya la dirección, no la "prueba". **WC2022 RESERVADA VIRGEN** (no entra).

## Setup

- **Held-out:** KO de WC2018/14/10 = los **últimos 16 por fecha** de cada WC (64 = 48 grupos + 16 KO;
  verificado: empate-120' == a-penales por año → 4/4, 4/4, 2/2). **N=48 KO, 10 a penales.**
- **Rolling-origin:** por cada KO, fit DC-full (ξ=0.0018, fit_rho) sobre `build_train` previo
  (window 8a, `base_date`=fecha del partido), predict, scorear.
- **Scoring KO completo:** marcador a 120' (`results.csv`) + penales (`shootouts.csv`): si el pick es
  empate y el partido fue a penales, +5 si el favorito del modelo (`pen_pred`) == ganador real de la
  tanda (`pen_actual`). `match_points` VERBATIM.
- **Pareado:** mismo grid por partido; `c=0` (draw-option-value sobre el grid 90', el comportamiento
  viejo) vs `c=⅓` (grid a 120', el modelo D14).

## Resultado

| Métrica | c=0 (viejo) | c=⅓ (120', D14) |
|---|---|---|
| EP/partido | 4.479 | **5.208** |
| Total (N=48) | 215 | 250 |

**ΔEP = +0.729 · SE pareado 0.571 · z = +1.28** (no significativo). Picks distintos: **20/48**.

| Año | EP c=0 | EP c=⅓ | a-penales |
|-----|--------|--------|-----------|
| WC2018 | (16 KO) | | 4 |
| WC2014 | (16 KO) | | 4 |
| WC2010 | (16 KO) | | 2 |

## Lectura honesta

- **Dirección a favor del modelo a 120'**, consistente con la corrección teórica. El modelo gana en
  los KO que se **resuelven** (la mayoría: el viejo malgastaba picks de empate sobre partidos que
  tuvieron ganador — France-Argentina 4-3, Belgium-England 2-0, Spain-Portugal, Argentina-Germany…)
  y **pierde** en los ~10 que fueron a **penales** (ahí el viejo, prediciendo empate y acertando la
  tanda, cobraba el +5/+17; peor caso para el nuevo: **Paraguay-Japan 0-0 → viejo 17 pts vs nuevo 2**).
- **z=1.28 NO es significativo** (N=48, esperado). El diseño §7 lo anticipó: gate = corrección +
  oráculo, NO significancia (poca potencia con N chico de KO). El backtest **no contradice** el
  modelo; lo **apoya**.
- El trade-off es el correcto: renunciar al +5 ocasional de penales a cambio de acertar al favorito
  en la mayoría → **neto positivo** en held-out (+0.73 pts/partido).

## Reproducir

`.venv/Scripts/python.exe scripts/backtest_knockouts.py`
