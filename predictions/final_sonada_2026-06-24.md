# Oráculo Mundialista — Final Soñada (Monte Carlo de torneo)

## Provenance / config
- **Método:** 50000 simulaciones del bracket WC2026 verificado (docs/final_sonada_design.md §3.1), probs por matchup del DixonColesEngine.
- **Fit:** 49453 partidos, xi=0.0018, rho=-0.0830, gamma=0.2083.
- **Condicionamiento:** condicionado en 48 partidos jugados (PROVISIONAL, grupos incompletos). seed=20260624.
- **Knobs (JP 2026-06-15):** tilt anfitrión por sede (knockouts), penales 0.55 al favorito.
- **Objetivo:** 10·P(campeón) + 10·P(subcampeón), A≠B (prode_rules §3.2).

## Par óptimo

- **Campeón:** Argentina  (P=0.253 ± 0.002)
- **Subcampeón:** Spain  (P=0.094)
- **EV esperado:** 3.47 pts (de 20 posibles)

## Marginales (top 12)

| # | Campeón | P | ±SE | Subcampeón | P |
|---|---------|---|-----|------------|---|
| 1 | Argentina | 0.253 | 0.002 | Argentina | 0.106 |
| 2 | Spain | 0.109 | 0.001 | Spain | 0.094 |
| 3 | France | 0.066 | 0.001 | France | 0.070 |
| 4 | Portugal | 0.066 | 0.001 | Portugal | 0.067 |
| 5 | England | 0.064 | 0.001 | Germany | 0.062 |
| 6 | Germany | 0.051 | 0.001 | England | 0.055 |
| 7 | Morocco | 0.049 | 0.001 | Colombia | 0.053 |
| 8 | Colombia | 0.047 | 0.001 | Morocco | 0.049 |
| 9 | Brazil | 0.046 | 0.001 | Brazil | 0.045 |
| 10 | Japan | 0.041 | 0.001 | Japan | 0.044 |
| 11 | Netherlands | 0.033 | 0.001 | Norway | 0.041 |
| 12 | Norway | 0.032 | 0.001 | Netherlands | 0.040 |

## Lectura honesta

- **Subcampeón ≠ 2° favorito:** subcampeón = llega a la final y la pierde; su marginal la maximiza el fuerte-pero-no-dominante, no el favorito (prode_rules §3.2).
- **xi=0.0018 CALIBRADO (D7):** en plateau plano de EP held-out [0.0005-0.003]; no recalibrar.
- **N=50000:** el SE de las marginales del top está reportado; la cola es ruidosa.
- **PROVISIONAL (grupos incompletos):** 48 partidos de grupo condicionados; el resto (Fecha 3 + knockouts) simulado. La cola es ruidosa.
