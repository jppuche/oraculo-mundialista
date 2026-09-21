# Reviewer 03 — Verifier (fidelity) — recálculo MECÁNICO, DIRECT ground-truth

Sos el **verificador de fidelidad** de una auditoría READ-ONLY del "Oráculo Mundialista" (predictor
del prode del Mundial 2026). Tu trabajo es **mecánico, sin juicio de diseño**: recalcular el score de
cero, verificar hashes y contar filas. NO opines sobre si el modelo es bueno; solo confirmá si los
números reportados son **fieles**, celda por celda. Sos cold: todo lo necesario está acá o en los
archivos/comandos indicados.

## Scoring del prode (lo que computa `wcprode.scoring.match_points`)
- **12** si el marcador exacto coincide (H y A).
- Si no: **+5** si el resultado (H/D/A) coincide, **+2** si coincide la cantidad de goles de UN equipo (H o A). B y C apilan (máx 7 no-exacto).
- **+5** de penales SOLO si predijiste empate Y el partido fue a penales Y acertaste el ganador de la tanda. (En R16 no hay picks de empate → este término es 0.)

## REGLAS DE EJECUCIÓN
- **READ-ONLY:** NO uses Write/Edit/NotebookEdit; NO modifiques ningún archivo. Podés correr comandos
  de solo-lectura (python one-liners, sha256sum, wc, git diff/log, pytest). Tu entregable es el
  mensaje final con la tabla de findings.
- Usá el intérprete del repo: **`.venv/Scripts/python.exe`** (Windows). El repo está en
  `<repo-root>` (es el working dir).
- Para recalcular el score, **IMPORTÁ la función real** `from wcprode.scoring import match_points` —
  NO la reimplementes. Corré `match_points((ph,pa),(rh,ra))` por partido.

## Tarea 1 — Recalcular el score R16 de cero (celda por celda)
Predicciones (de `predictions/r16_full_2026-07-04.txt`) y resultados reales (de
`data/actuals_r16_2026-07-08.md`). Verificá primero que estos pares coinciden con esos archivos, y
después recalculá:

| Partido | Pred | Real | EV (del .txt) |
|---|---|---|---|
| Canada vs Morocco | 0-1 | 0-3 | 5.21 |
| Paraguay vs France | 0-1 | 0-1 | 5.54 |
| Brazil vs Norway | 2-1 | 1-2 | 4.51 |
| Mexico vs England | 0-1 | 2-3 | 4.33 |
| Portugal vs Spain | 0-1 | 0-1 | 4.33 |
| United States vs Belgium | 1-2 | 1-4 | 4.70 |
| Argentina vs Egypt | 1-0 | 3-2 | 6.45 |
| Switzerland vs Colombia | 0-1 | 0-0 | 4.05 |

Corré `match_points` sobre las 8. Reportá **pts por partido**, **total**, **media (total/8)**,
**suma EV**, **media EV**, y **ratio real/EV en %**. ¿Da **50 pts / media 6.250 / +27.8%**, exacto?
Comparalo con `predictions/scored_r16_2026-07-08.md` (tabla + totales) celda por celda: ¿algún pts,
EV, o `Pts−EV` distinto? ¿El conteo `Outcome✓`/`GolMatch` de cada fila es correcto?

## Tarea 2 — Cobertura del join (¿se scorearon los 8?)
Verificá que las **8** predicciones tienen su actual y viceversa (ninguna perdida/duplicada). OJO:
2 partidos (Argentina-Egypt, Switzerland-Colombia) fueron **reprogramados del 06-jul al 07-jul** en la
fuente. La predicción se generó con fecha vieja; el actual tiene fecha nueva. Confirmá que el join
del scorer (`scripts/score_matchday.py`) matchea por **equipos** (no por fecha) y que los 8 entran.
Fijate también si el scorer podría dejar una predicción sin actual **silenciosamente** (¿itera sobre
actuals o sobre predicciones? ¿aborta o ignora?).

## Tarea 3 — Fidelidad del pin (hashes + filas + diff del re-pin)
- `sha256sum data/raw/results.csv data/raw/shootouts.csv` → comparar con `data/raw/sources.lock.json`
  (campos `sha256`). ¿Coinciden EXACTO?
- Filas: `wc -l` de ambos vs `rows_incl_header` del lock (notá si difieren por newline final).
- Del `_repin_note` en el lock: las 2 "removidas" (fecha-06) deben ser el **MISMO matchup**
  (home/away) que las 2 "agregadas" (fecha-07), con **0 filas score→score distinto**. Verificá lo que
  puedas con los datos disponibles (p.ej. buscando esos matchups en `data/raw/results.csv` con grep:
  Argentina/Egypt, Switzerland/Colombia; ¿aparecen una sola vez, con score, fecha 07-jul?). Gate
  reportado: 49505.

## Tarea 4 — Suite + oráculos intactos
- `.venv/Scripts/python.exe -m pytest tests/ -q` → ¿**122 passed**? (corré esto SOLO; no lances otros
  scripts pesados en paralelo — hay un known-issue de BLAS concurrente.)
- `git diff --stat -- tests/test_engine_oracle.py tests/test_tournament_oracle.py tests/test_backtest_oracle.py tests/test_bivariate_oracle.py tests/test_penalty_oracle.py`
  → ¿**vacío** (no editados)? Complementá con `git status --short` y, si querés, `git log --oneline -3`
  sobre esos archivos para ver el último cambio.

## Protocolo de salida (schema obligatorio, sin prosa suelta)
| # | Severity | Finding | Locator (file:line / comando) | Provenance | Confidence | Falsified_by |

- Severity: CRITICAL | HIGH | MEDIUM | LOW. Provenance: `VERIFIED_IN_ARTIFACT` (lo corriste/leíste) | `INFERRED` | `ASSUMED`. Confidence: HIGH | MEDIUM | LOW.
- **Incluí SIEMPRE una fila de resultado por cada Tarea 1-4**, aunque sea "CONFIRMADO sin discrepancia"
  (con Severity LOW/─). Pegá los números crudos que obtuviste (pts por partido, hashes, conteo de tests).
- Si algo NO coincide, es al menos MEDIUM y va con el valor esperado vs el obtenido.
- No emitas juicio de diseño. Solo fidelidad mecánica. Cerrá listando qué comando corriste para cada tarea.
