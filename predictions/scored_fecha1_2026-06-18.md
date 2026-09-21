# Oráculo Mundialista — Reporte Fecha 1 (scored)

## Provenance

- **Predicciones:** `groups_full_2026-06-10.txt` (fit del 2026-06-09, modo full, DC + time-decay)
- **Actuals:** `actuals_2026-06-18.md` (captura 2026-06-15 ~AM, provisto por JP)
- **Rung 1:** vs resultados = verdad (el veredicto serio es Fase 3, backtest multi-copa)
- **Scoring:** `wcprode.scoring.match_points` VERBATIM de `docs/prode_rules.md §2`
- **N:** 24 partidos (incl. 1 provisional: Sweden–Tunisia)

## Tabla de resultados

| Fecha | Partido | Pred | Real | Outcome✓ | GolMatch | Pts | EV | Pts−EV | Prov. |
|-------|---------|------|------|----------|----------|-----|----|--------|-------|
| 2026-06-11 | Mexico vs South Africa | 1-0 | 2-0 | ✓ | ✓ | 7 | 5.35 | 1.65 |  |
| 2026-06-11 | South Korea vs Czech Republic | 1-0 | 2-1 | ✓ | ✗ | 5 | 3.57 | 1.43 |  |
| 2026-06-12 | Canada vs Bosnia and Herzegovina | 1-0 | 1-1 | ✗ | ✓ | 2 | 5.24 | -3.24 |  |
| 2026-06-12 | United States vs Paraguay | 0-1 | 4-1 | ✗ | ✓ | 2 | 3.55 | -1.55 |  |
| 2026-06-13 | Australia vs Turkey | 0-1 | 2-0 | ✗ | ✗ | 0 | 3.73 | -3.73 |  |
| 2026-06-13 | Brazil vs Morocco | 0-0 | 1-1 | ✓ | ✗ | 5 | 3.76 | 1.24 |  |
| 2026-06-13 | Haiti vs Scotland | 0-2 | 0-1 | ✓ | ✓ | 7 | 4.84 | 2.16 |  |
| 2026-06-13 | Qatar vs Switzerland | 0-3 | 1-1 | ✗ | ✗ | 0 | 6.32 | -6.32 |  |
| 2026-06-14 | Germany vs Curaçao | 4-0 | 7-1 | ✓ | ✗ | 5 | 6.79 | -1.79 |  |
| 2026-06-14 | Ivory Coast vs Ecuador | 0-0 | 1-0 | ✗ | ✓ | 2 | 5.03 | -3.03 |  |
| 2026-06-14 | Netherlands vs Japan | 0-1 | 2-2 | ✗ | ✗ | 0 | 3.59 | -3.59 |  |
| 2026-06-14 | Sweden vs Tunisia | 1-0 | 5-1 | ✓ | ✗ | 5 | 3.56 | 1.44 |  |
| 2026-06-15 | Belgium vs Egypt | 1-0 | 1-1 | ✗ | ✓ | 2 | 4.49 | -2.49 |  |
| 2026-06-15 | Iran vs New Zealand | 1-0 | 2-2 | ✗ | ✗ | 0 | 5.36 | -5.36 |  |
| 2026-06-15 | Saudi Arabia vs Uruguay | 0-1 | 1-1 | ✗ | ✓ | 2 | 5.65 | -3.65 |  |
| 2026-06-15 | Spain vs Cape Verde | 2-0 | 0-0 | ✗ | ✓ | 2 | 6.34 | -4.34 |  |
| 2026-06-16 | Argentina vs Algeria | 1-0 | 3-0 | ✓ | ✓ | 7 | 5.25 | 1.75 |  |
| 2026-06-16 | Austria vs Jordan | 2-0 | 3-1 | ✓ | ✗ | 5 | 5.25 | -0.25 |  |
| 2026-06-16 | France vs Senegal | 1-0 | 3-1 | ✓ | ✗ | 5 | 4.33 | 0.67 |  |
| 2026-06-16 | Iraq vs Norway | 0-2 | 1-4 | ✓ | ✗ | 5 | 5.84 | -0.84 |  |
| 2026-06-17 | England vs Croatia | 1-0 | 4-2 | ✓ | ✗ | 5 | 4.57 | 0.43 |  |
| 2026-06-17 | Ghana vs Panama | 1-0 | 1-0 | ✓ | ✓ | 12 | 3.66 | 8.34 |  |
| 2026-06-17 | Portugal vs DR Congo | 1-0 | 1-1 | ✗ | ✓ | 2 | 5.17 | -3.17 |  |
| 2026-06-17 | Uzbekistan vs Colombia | 0-1 | 1-3 | ✓ | ✗ | 5 | 5.31 | -0.31 |  |

## Totales

| Métrica | Con provisional (N=24) | Sin provisional (N=24) |
|---------|------------------------|----------------------------------|
| Total pts | **92** | **92** |
| Media pts/partido | **3.833** | **3.833** |
| Suma EV | 116.55 | — |
| Media EV | 4.856 | — |
| Ratio real/EV | -21.1% | — |

## Nota honesta

N=24 — ruidoso, no es veredicto. El veredicto serio es Fase 3 (backtest WC2022 virginal, multi-copa).

**Lo que le dolió al modelo:** Las 2 jugadas contrarian-riesgosas fallaron (USA como underdog: predijimos 0-1 Paraguay, real 4-1 → 2 pts de 5 posibles; Australia perdiendo ante Turkey: predijimos 0-1, real 2-0 → 0 pts). Qatar–Switzerland con EV altísimo (6.32) whiffeó completamente: predijimos 0-3, real 1-1 → 0 pts.

**Lo que acertó:** El contrarian Brazil 0-0 Morocco acertó el empate → 5 pts (pred era modal 0-0, P=0.16; fue 1-1, outcome draw = correcto). Mexico–South Africa y Haiti–Scotland dieron 7 pts c/u (ganador + un goleo exacto). Germany–Curaçao: predijimos 4-0, real 7-1 → 5 pts (ganador correcto).

**Resumen:** -21.1% vs expectativa propia (media real 3.833 vs media EV 4.856). Esperado para N pequeño dado alta varianza del scoring.
