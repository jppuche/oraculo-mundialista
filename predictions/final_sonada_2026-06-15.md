# Oráculo Mundialista — Final Soñada (Monte Carlo de torneo)

## Provenance / config
- **Método:** 50000 simulaciones del bracket WC2026 verificado (docs/final_sonada_design.md §3.1), probs por matchup del DixonColesEngine.
- **Fit:** 49306 partidos, xi=0.0018, rho=-0.0662, gamma=0.2108.
- **Condicionamiento:** PROVISIONAL (pin pre-torneo). seed=20260624.
- **Knobs (JP 2026-06-15):** tilt anfitrión por sede (knockouts), penales 0.55 al favorito.
- **Objetivo:** 10·P(campeón) + 10·P(subcampeón), A≠B (prode_rules §3.2).

## Par óptimo

- **Campeón:** Argentina  (P=0.162 ± 0.002)
- **Subcampeón:** Spain  (P=0.087)
- **EV esperado:** 2.48 pts (de 20 posibles)

## Marginales (top 12)

| # | Campeón | P | ±SE | Subcampeón | P |
|---|---------|---|-----|------------|---|
| 1 | Argentina | 0.162 | 0.002 | Spain | 0.087 |
| 2 | Spain | 0.141 | 0.002 | Argentina | 0.082 |
| 3 | England | 0.070 | 0.001 | England | 0.059 |
| 4 | France | 0.065 | 0.001 | France | 0.058 |
| 5 | Morocco | 0.063 | 0.001 | Brazil | 0.056 |
| 6 | Brazil | 0.060 | 0.001 | Morocco | 0.054 |
| 7 | Portugal | 0.054 | 0.001 | Portugal | 0.053 |
| 8 | Germany | 0.042 | 0.001 | Germany | 0.048 |
| 9 | Japan | 0.038 | 0.001 | Colombia | 0.042 |
| 10 | Colombia | 0.037 | 0.001 | Japan | 0.040 |
| 11 | Netherlands | 0.034 | 0.001 | Switzerland | 0.038 |
| 12 | Norway | 0.029 | 0.001 | Netherlands | 0.037 |

## Lectura honesta

- **Subcampeón ≠ 2° favorito:** subcampeón = llega a la final y la pierde; su marginal la maximiza el fuerte-pero-no-dominante, no el favorito (prode_rules §3.2).
- **xi=0.0018** (era el #1 knob abierto). *[Nota post-D7 (2026-06-15): el backtest multi-copa CONFIRMÓ ξ=0.0018 dentro de un plateau plano — no es sesgo. Ver DECISIONS D7. Estas marginales son del pin pre-torneo; la corrida definitiva ~06-24 re-fittea.]*
- **N=50000:** el SE de las marginales del top está reportado; la cola es ruidosa.
- **PROVISIONAL:** corrida con grupos incompletos (o pin pre-torneo). La definitiva es cerca del 2026-06-24 con Fechas 1-2 (re-pin martj42 + re-fit).
