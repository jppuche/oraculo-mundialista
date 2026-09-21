# Oráculo Mundialista — Reporte Semifinales (scored)

## Provenance

- **Predicciones:** `semis_full_2026-07-14.txt`
- **Actuals:** `actuals_semis_2026-07-18.md`
- **Rung 1:** vs resultados = verdad (el veredicto serio es Fase 3, backtest multi-copa)
- **Scoring:** `wcprode.scoring.match_points` VERBATIM de `docs/prode_rules.md §2`
- **N:** 2 partidos

## Tabla de resultados

| Fecha | Partido | Pred | Real | Outcome✓ | GolMatch | Pts | EV | Pts−EV | Prov. |
|-------|---------|------|------|----------|----------|-----|----|--------|-------|
| 2026-07-14 | France vs Spain | 0-1 | 0-2 | ✓ | ✓ | 7 | 4.16 | 2.84 |  |
| 2026-07-15 | England vs Argentina | 0-1 | 1-2 | ✓ | ✗ | 5 | 4.49 | 0.51 |  |

## Totales

| Métrica | Con provisional (N=2) | Sin provisional (N=2) |
|---------|------------------------|----------------------------------|
| Total pts | **12** | **12** |
| Media pts/partido | **6.000** | **6.000** |
| Suma EV | 8.65 | — |
| Media EV | 4.325 | — |
| Ratio real/EV | +38.7% | — |

## Lectura honesta

N=2 — ruidoso, no es veredicto. El veredicto serio es Fase 3 (backtest WC2022 virginal, multi-copa).

**Lo que más dolió (pts por debajo de EV):**
- England vs Argentina: pred 0-1, real 1-2 → 5 pts (EV 4.49, Δ +0.51)
- France vs Spain: pred 0-1, real 0-2 → 7 pts (EV 4.16, Δ +2.84)

**Lo que mejor salió (más pts):**
- France vs Spain: pred 0-1, real 0-2 → 7 pts (EV 4.16, Δ +2.84)
- England vs Argentina: pred 0-1, real 1-2 → 5 pts (EV 4.49, Δ +0.51)

**Resumen:** +38.7% vs expectativa propia (media real 6.000 vs media EV 4.325). Esperado para N pequeño dada la alta varianza del scoring.
