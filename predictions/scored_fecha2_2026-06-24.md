# Oráculo Mundialista — Reporte Fecha 2 (scored)

## Provenance

- **Predicciones:** `fecha2_full_2026-06-18.txt`
- **Actuals:** `actuals_fecha2_2026-06-24.md`
- **Rung 1:** vs resultados = verdad (el veredicto serio es Fase 3, backtest multi-copa)
- **Scoring:** `wcprode.scoring.match_points` VERBATIM de `docs/prode_rules.md §2`
- **N:** 24 partidos

## Tabla de resultados

| Fecha | Partido | Pred | Real | Outcome✓ | GolMatch | Pts | EV | Pts−EV | Prov. |
|-------|---------|------|------|----------|----------|-----|----|--------|-------|
| 2026-06-18 | Canada vs Qatar | 2-0 | 6-0 | ✓ | ✓ | 7 | 6.00 | 1.00 |  |
| 2026-06-18 | Czech Republic vs South Africa | 1-0 | 1-1 | ✗ | ✓ | 2 | 4.34 | -2.34 |  |
| 2026-06-18 | Mexico vs South Korea | 1-0 | 1-0 | ✓ | ✓ | 12 | 4.55 | 7.45 |  |
| 2026-06-18 | Switzerland vs Bosnia and Herzegovina | 1-0 | 4-1 | ✓ | ✗ | 5 | 5.24 | -0.24 |  |
| 2026-06-19 | Brazil vs Haiti | 3-0 | 3-0 | ✓ | ✓ | 12 | 6.26 | 5.74 |  |
| 2026-06-19 | Scotland vs Morocco | 0-1 | 0-1 | ✓ | ✓ | 12 | 5.02 | 6.98 |  |
| 2026-06-19 | Turkey vs Paraguay | 1-0 | 0-1 | ✗ | ✗ | 0 | 3.67 | -3.67 |  |
| 2026-06-19 | United States vs Australia | 0-1 | 2-0 | ✗ | ✗ | 0 | 3.58 | -3.58 |  |
| 2026-06-20 | Ecuador vs Curaçao | 2-0 | 0-0 | ✗ | ✓ | 2 | 6.85 | -4.85 |  |
| 2026-06-20 | Germany vs Ivory Coast | 1-0 | 2-1 | ✓ | ✗ | 5 | 4.51 | 0.49 |  |
| 2026-06-20 | Netherlands vs Sweden | 2-1 | 5-1 | ✓ | ✓ | 7 | 4.63 | 2.37 |  |
| 2026-06-20 | Tunisia vs Japan | 0-1 | 0-4 | ✓ | ✓ | 7 | 5.71 | 1.29 |  |
| 2026-06-21 | Belgium vs Iran | 1-0 | 0-0 | ✗ | ✓ | 2 | 4.43 | -2.43 |  |
| 2026-06-21 | New Zealand vs Egypt | 0-1 | 1-3 | ✓ | ✗ | 5 | 5.07 | -0.07 |  |
| 2026-06-21 | Spain vs Saudi Arabia | 2-0 | 4-0 | ✓ | ✓ | 7 | 6.35 | 0.65 |  |
| 2026-06-21 | Uruguay vs Cape Verde | 1-0 | 2-2 | ✗ | ✗ | 0 | 5.51 | -5.51 |  |
| 2026-06-22 | Argentina vs Austria | 1-0 | 2-0 | ✓ | ✓ | 7 | 5.46 | 1.54 |  |
| 2026-06-22 | France vs Iraq | 2-0 | 3-0 | ✓ | ✓ | 7 | 6.16 | 0.84 |  |
| 2026-06-22 | Jordan vs Algeria | 0-2 | 1-2 | ✓ | ✓ | 7 | 5.04 | 1.96 |  |
| 2026-06-22 | Norway vs Senegal | 1-0 | 3-2 | ✓ | ✗ | 5 | 4.10 | 0.90 |  |
| 2026-06-23 | Colombia vs DR Congo | 1-0 | 1-0 | ✓ | ✓ | 12 | 5.08 | 6.92 |  |
| 2026-06-23 | England vs Ghana | 2-0 | 0-0 | ✗ | ✓ | 2 | 6.03 | -4.03 |  |
| 2026-06-23 | Panama vs Croatia | 0-2 | 0-1 | ✓ | ✓ | 7 | 5.29 | 1.71 |  |
| 2026-06-23 | Portugal vs Uzbekistan | 1-0 | 5-0 | ✓ | ✓ | 7 | 5.50 | 1.50 |  |

## Totales

| Métrica | Con provisional (N=24) | Sin provisional (N=24) |
|---------|------------------------|----------------------------------|
| Total pts | **139** | **139** |
| Media pts/partido | **5.792** | **5.792** |
| Suma EV | 124.38 | — |
| Media EV | 5.183 | — |
| Ratio real/EV | +11.8% | — |

## Lectura honesta

N=24 — ruidoso, no es veredicto. El veredicto serio es Fase 3 (backtest WC2022 virginal, multi-copa).

**Lo que más dolió (pts por debajo de EV):**
- Uruguay vs Cape Verde: pred 1-0, real 2-2 → 0 pts (EV 5.51, Δ -5.51)
- Ecuador vs Curaçao: pred 2-0, real 0-0 → 2 pts (EV 6.85, Δ -4.85)
- England vs Ghana: pred 2-0, real 0-0 → 2 pts (EV 6.03, Δ -4.03)

**Lo que mejor salió (más pts):**
- Mexico vs South Korea: pred 1-0, real 1-0 → 12 pts (EV 4.55, Δ +7.45)
- Scotland vs Morocco: pred 0-1, real 0-1 → 12 pts (EV 5.02, Δ +6.98)
- Colombia vs DR Congo: pred 1-0, real 1-0 → 12 pts (EV 5.08, Δ +6.92)

**Resumen:** +11.8% vs expectativa propia (media real 5.792 vs media EV 5.183). Esperado para N pequeño dada la alta varianza del scoring.
