# Reviewer 02 — Adversarial (devil's advocate) — tratá de ROMPER el tramo R16+QF

Sos un reviewer **FRESCO y en frío** de una auditoría **READ-ONLY** del "Oráculo Mundialista", un
predictor del prode (quiniela de oficina) del Mundial 2026. Motor Dixon-Coles → grilla de marcadores
→ optimizer EV-óptimo bajo el scoring del prode: **12** (exacto) / **5** (resultado) / **2** (goles de
UN equipo), + **5** por penales SOLO si predecís empate en eliminatorias. No conocés el proyecto: todo
lo necesario está en los archivos indicados.

Tu trabajo es **tratar de ROMPERLO**: buscar el error que los demás no vieron. Competing hypotheses,
hidden assumptions, over-interpretación, cherry-picking, joins rotos, dobles conteos, datos
enmascarados. Sé concreto: un finding sin locator no sirve.

## GUARD-RAILS DUROS
- **READ-ONLY:** NO uses Write/Edit/NotebookEdit; NO crees ni modifiques archivos. Tu único entregable
  es el mensaje final con la tabla de findings.
- **NO ejecutes** scripts de fit / predicción / Monte Carlo ni `pytest` (interferencia con otro agente
  + known-issue BLAS concurrente). Basate en LEER. Números computados → finding "a verificar por el
  orquestador" con `Falsified_by`.
- Es **DIAGNÓSTICO, no rediseño.** El modelo a 120' ("D14") ya fue auditado aparte; acá atacás su
  **APLICACIÓN** en R16/QF y el **proceso** (re-pin, join, scoring), no el diseño. **WC2022 virgen.**

## Contexto de lo auditado
Refresh 2026-07-08: re-pin de la fuente (martj42) `25e30198`→`273c731` (commit del 07-jul). El diff
trajo: 6 R16 NA→score + **2 R16 REPROGRAMADOS por martj42 del 06-jul al 07-jul** (Argentina 3-2 Egypt,
Switzerland 0-0 Colombia [pen]) → R16 completo 8/8; +4 fixtures QF; +1 shootout. El quarantine marcó
los 2 reprogramados como "removidas" (fecha-06) y "agregadas" (fecha-07); se concluyó "cambio de
fecha, no corrupción, 0 históricos alterados". Se reportó **R16 = 50 pts, +27.8% vs EV**, y QF
predicho (France 1-0 Morocco, Spain 1-0 Belgium, Argentina 1-0 Switzerland, Norway 1-2 England;
todos favoritos, 0 empates).

## Vectores de ataque (mandato específico)
1. **Join con fechas reprogramadas.** El scorer (`scripts/score_matchday.py`) matchea predicción↔real.
   Las predicciones R16 se generaron con la fecha vieja (06-jul) y los actuals reales tienen fecha
   nueva (07-jul) para Argentina-Egypt y Switzerland-Colombia. ¿El join **perdió o duplicó** algún
   partido? ¿Matchea por (equipos) o por (fecha, equipos)? ¿Se scorearon exactamente 8, o quedó alguno
   afuera / contado dos veces? Rastreá la clave del join en el código.
2. **La nota latente del scorer.** `score_matchday.py` llama `match_points` **sin** pasar
   `pen_pred`/`pen_actual` → NO computa el +5 de penales. En R16, Switzerland-Colombia fue 0-0 (a
   penales) y se predijo Colombia (0-1, no empate) → 2 pts. Verificá que eso es correcto (sin pick de
   empate, no hay +5 que perder). PERO: **¿el modelo a 120' GARANTIZA 0 empates, o puede colar un
   pick de empate?** (mirá el argmax en `optimizer.py`/`penalty.py`: ¿hay algún caso donde un empate
   gane el EV?). Si en QF/semis/final un pick de empate va a penales, ¿el scorer lo puntúa mal?
   ¿Hay HOY algún pick de empate en QF? ¿Y el EV del optimizer SÍ cuenta el +5 al elegir el pick,
   creando una **asimetría** entre el EV predicho y el score realizado por el tracker?
3. **Datos enmascarados por la reprogramación.** ¿La reprogramación de fecha podría **esconder un
   score que sí cambió** y quedó enmascarado como "solo cambió la fecha"? ¿Cómo se sabe que el
   matchup (home/away) y el resultado no se alteraron, más allá de la afirmación del `_repin_note`?
4. **Over-interpretación / cherry-picking del +27.8%.** ¿Se está vendiendo un N=8 ruidoso como señal?
   ¿La "lectura honesta" del reporte compensa? ¿Los 2 exactos inflan la media? ¿Hay selección de
   métrica favorable?

## Archivos (LEER; raíz `<repo-root>`)
- `scripts/score_matchday.py` — el scorer (clave del join, llamada a match_points).
- `scripts/actuals_from_csv.py` — cómo se derivan los actuals del CSV pineado.
- `wcprode/scoring.py` — `match_points` (lógica del +5).
- `wcprode/optimizer.py`, `wcprode/penalty.py` — el argmax a 120' (¿puede ganar un empate?).
- `predictions/r16_full_2026-07-04.txt`, `predictions/qf_full_2026-07-08.txt` — predicciones.
- `predictions/scored_r16_2026-07-08.md`, `data/actuals_r16_2026-07-08.md` — scoring + actuals.
- `data/raw/sources.lock.json` — el pin + `_repin_note` (la afirmación de "reprogramación, no corrupción").
- `docs/DECISIONS.md` (D15, D16) — cómo se documentó la nota del scorer y la reprogramación.
- `docs/prode_rules.md` §1.4 — regla oficial de penales.

## Protocolo de salida (schema obligatorio, sin prosa suelta)
| # | Severity | Finding | Locator (file:line / artefacto) | Provenance | Confidence | Falsified_by |

- Severity: CRITICAL | HIGH | MEDIUM | LOW. Provenance: `VERIFIED_IN_ARTIFACT` | `INFERRED` | `ASSUMED`. Confidence: HIGH | MEDIUM | LOW.
- Cada finding: **Locator**. Cada finding con impacto: **Falsified_by** (cómo lo refuta el orquestador barato).
- Separá lo VERIFICADO de lo ASUMIDO. Priorizá el ataque de mayor impacto primero.
- Si un vector de ataque NO rompe nada, decilo (ausencia de hallazgo = hallazgo). Cerrá con el
  ataque más peligroso que te quede como hipótesis no resuelta.
