# Backtest multi-copa — calibración de ξ (Fase 3)

**Fecha:** 2026-06-15 · **Harness:** `wcprode/backtest.py` (oráculo `tests/test_backtest_oracle.py`, D6) ·
**Comando:** `.venv/Scripts/python.exe scripts/backtest_multicup.py` (grid default, modo full, ventana 8a, bootstrap 2000 iter, seed 20260615).

Rolling-origin held-out por copa (fit con `date < D` + decay, `base_date=D`; sin leakage). EP = expected points
realizados por partido bajo `match_points`. WC2022 RESERVADA virgen (futuro respecto a todo `build_train`).

## Resultado

**Agregado (media no ponderada de EP sobre 3 copas; SE agregado ≈ 0.27):**

| ξ | EP medio | nota |
|--------|----------|------|
| 0.0001 | 4.92 | |
| 0.0005 | 5.02 | |
| 0.0010 | **5.13** | argmax agregado |
| **0.0018** | **5.03** | **valor actual (club-calibrado)** |
| 0.0030 | 5.11 | |
| 0.0050 | 4.58 | −0.55 vs plateau (≈2 SE) |
| 0.0100 | 4.19 | −0.94 vs plateau (≈3.4 SE) |

**Por copa (EP; argmax de cada una en negrita):**

| ξ | WC2018 | WC2014 | WC2010 |
|--------|--------|--------|--------|
| 0.0001 | 5.00 | **4.92** | 4.83 |
| 0.0005 | **5.09** | 4.63 | 5.33 |
| 0.0010 | 4.98 | 4.75 | 5.66 |
| 0.0018 | 4.86 | 4.31 | 5.92 |
| 0.0030 | 4.75 | 4.59 | **5.98** |
| 0.0050 | 4.23 | 4.55 | 4.95 |
| 0.0100 | 4.39 | 3.89 | 4.28 |
| **argmax** | 0.0005 | 0.0001 | 0.0030 |
| SE (intra) | ~0.46 | ~0.44 | ~0.54 |

n_predicted = 64, n_skipped = 0 en todas las celdas (cobertura total de equipos con ventana 8a).

## Interpretación

1. **Plateau plano [0.0005–0.0030]:** diferencias internas ≤0.10 EP, <0.5 SE. ξ=0.0018 está dentro.
   El argmax agregado (0.0010) NO es significativamente mejor que 0.0018.
2. **Lo único robusto:** ξ ≥ 0.005 degrada significativamente (2–3.4 SE). Más memoria corta = peor.
   La dirección del miedo "ξ club-agresivo" apuntaba al lado equivocado: subir ξ es lo que mata el EP.
3. **Heterogeneidad por copa:** WC2010 prefiere ξ alto (0.0030); 2018/2014 prefieren bajo (0.0005/0.0001).
   Ninguna copa pone a ξ=0.0018 significativamente lejos de su propio argmax. La "ξ óptima" varía por
   torneo más de lo que 3 copas (N=192) pueden resolver.

## Veredicto

**Mantener ξ=0.0018. No recalibrar.** Está dentro del plateau; mover a 0.0010 sería sobreajustar al ruido del
backtest. **USA 4-1 (Fecha 1) y Morocco 5º (Final Soñada) eran ruido de muestra pequeña, NO un sesgo sistemático
de ξ.** El miedo del handoff (ξ demasiado agresivo) no se sostiene; si acaso, ξ alto es lo peligroso.

**Caveat (poder):** N=192, SE alto, EP escalonado (poco sensible a ξ dentro del plateau). Suficiente para la
decisión (no tocar ξ; evitar ξ≥0.005), no para afirmar que 0.0018 sea el óptimo exacto. Un diagnóstico más suave
(log-loss sobre P(h,a), pendiente #10) o más copas (2006/2002, a costa de fútbol más viejo) afinarían.
