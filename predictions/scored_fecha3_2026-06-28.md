# Oráculo Mundialista — Reporte Fecha 3 (scored)

## Provenance

- **Predicciones:** `fecha3_full_2026-06-24.txt`
- **Actuals:** `actuals_fecha3_2026-06-28.md`
- **Rung 1:** vs resultados = verdad (el veredicto serio es Fase 3, backtest multi-copa)
- **Scoring:** `wcprode.scoring.match_points` VERBATIM de `docs/prode_rules.md §2`
- **N:** 24 partidos

## Tabla de resultados

| Fecha | Partido | Pred | Real | Outcome✓ | GolMatch | Pts | EV | Pts−EV | Prov. |
|-------|---------|------|------|----------|----------|-----|----|--------|-------|
| 2026-06-24 | Bosnia and Herzegovina vs Qatar | 1-0 | 3-1 | ✓ | ✗ | 5 | 4.65 | 0.35 |  |
| 2026-06-24 | Canada vs Switzerland | 0-1 | 1-2 | ✓ | ✗ | 5 | 3.53 | 1.47 |  |
| 2026-06-24 | Mexico vs Czech Republic | 1-0 | 3-0 | ✓ | ✓ | 7 | 4.78 | 2.22 |  |
| 2026-06-24 | Morocco vs Haiti | 2-0 | 4-2 | ✓ | ✗ | 5 | 6.37 | -1.37 |  |
| 2026-06-24 | Scotland vs Brazil | 0-1 | 0-3 | ✓ | ✓ | 7 | 4.73 | 2.27 |  |
| 2026-06-24 | South Africa vs South Korea | 0-1 | 1-0 | ✗ | ✗ | 0 | 4.56 | -4.56 |  |
| 2026-06-25 | Curaçao vs Ivory Coast | 0-2 | 0-2 | ✓ | ✓ | 12 | 6.26 | 5.74 |  |
| 2026-06-25 | Ecuador vs Germany | 0-1 | 2-1 | ✗ | ✓ | 2 | 4.07 | -2.07 |  |
| 2026-06-25 | Japan vs Sweden | 2-0 | 1-1 | ✗ | ✗ | 0 | 4.94 | -4.94 |  |
| 2026-06-25 | Paraguay vs Australia | 0-0 | 0-0 | ✓ | ✓ | 12 | 4.04 | 7.96 |  |
| 2026-06-25 | Tunisia vs Netherlands | 0-2 | 1-3 | ✓ | ✗ | 5 | 5.86 | -0.86 |  |
| 2026-06-25 | United States vs Turkey | 2-1 | 2-3 | ✗ | ✓ | 2 | 3.34 | -1.34 |  |
| 2026-06-26 | Cape Verde vs Saudi Arabia | 0-0 | 0-0 | ✓ | ✓ | 12 | 3.74 | 8.26 |  |
| 2026-06-26 | Egypt vs Iran | 0-0 | 1-1 | ✓ | ✗ | 5 | 3.81 | 1.19 |  |
| 2026-06-26 | New Zealand vs Belgium | 0-2 | 1-5 | ✓ | ✗ | 5 | 6.12 | -1.12 |  |
| 2026-06-26 | Norway vs France | 1-2 | 1-4 | ✓ | ✓ | 7 | 3.69 | 3.31 |  |
| 2026-06-26 | Senegal vs Iraq | 1-0 | 5-0 | ✓ | ✓ | 7 | 5.32 | 1.68 |  |
| 2026-06-26 | Uruguay vs Spain | 0-1 | 0-1 | ✓ | ✓ | 12 | 5.08 | 6.92 |  |
| 2026-06-27 | Algeria vs Austria | 0-1 | 3-3 | ✗ | ✗ | 0 | 3.62 | -3.62 |  |
| 2026-06-27 | Colombia vs Portugal | 1-2 | 0-0 | ✗ | ✗ | 0 | 3.33 | -3.33 |  |
| 2026-06-27 | Croatia vs Ghana | 1-0 | 2-1 | ✓ | ✗ | 5 | 4.97 | 0.03 |  |
| 2026-06-27 | DR Congo vs Uzbekistan | 0-0 | 3-1 | ✗ | ✗ | 0 | 4.89 | -4.89 |  |
| 2026-06-27 | Jordan vs Argentina | 0-2 | 1-3 | ✓ | ✗ | 5 | 6.85 | -1.85 |  |
| 2026-06-27 | Panama vs England | 0-2 | 0-2 | ✓ | ✓ | 12 | 6.28 | 5.72 |  |

## Totales

| Métrica | Con provisional (N=24) | Sin provisional (N=24) |
|---------|------------------------|----------------------------------|
| Total pts | **132** | **132** |
| Media pts/partido | **5.500** | **5.500** |
| Suma EV | 114.83 | — |
| Media EV | 4.785 | — |
| Ratio real/EV | +15.0% | — |

## Lectura honesta

N=24 — ruidoso, no es veredicto. El veredicto serio es Fase 3 (backtest WC2022 virginal, multi-copa).

**Lo que más dolió (pts por debajo de EV):**
- Japan vs Sweden: pred 2-0, real 1-1 → 0 pts (EV 4.94, Δ -4.94)
- DR Congo vs Uzbekistan: pred 0-0, real 3-1 → 0 pts (EV 4.89, Δ -4.89)
- South Africa vs South Korea: pred 0-1, real 1-0 → 0 pts (EV 4.56, Δ -4.56)

**Lo que mejor salió (más pts):**
- Cape Verde vs Saudi Arabia: pred 0-0, real 0-0 → 12 pts (EV 3.74, Δ +8.26)
- Paraguay vs Australia: pred 0-0, real 0-0 → 12 pts (EV 4.04, Δ +7.96)
- Uruguay vs Spain: pred 0-1, real 0-1 → 12 pts (EV 5.08, Δ +6.92)

**Resumen:** +15.0% vs expectativa propia (media real 5.500 vs media EV 4.785). Esperado para N pequeño dada la alta varianza del scoring.
