# Prompt — Revisión adversarial del tramo R16 + predicciones de Cuartos (QF)

> Pegá el bloque de abajo como PRIMER mensaje de una sesión NUEVA de Claude Code en `<repo-root>`.
> READ-ONLY (validación de trabajo ya hecho, NO rediseño). Audit trail (Agent Orchestration v0.5 §8).
> v2: 4 roles (Verifier-fidelity Sonnet separado de Metodología Opus) + preservación de prompts/outputs.

---

Sos el **orquestador (Opus)** de una revisión adversarial del tramo **Round of 16 + predicciones de Cuartos (QF)** del Oráculo Mundialista. Es **READ-ONLY**: no modifiques nada de código/datos/predicciones. Desplegás un equipo de reviewers y sintetizás + **verificás vos mismo** (DIRECT_FETCH / recálculo). No delegues la verificación.

## Paso 0 — Contexto mínimo (leé en este orden)
1. `CLAUDE.md`, `STATUS.md`, `docs/HANDOFF_knockouts.md` — estado (Cuartos), guard-rails.
2. `agent-orchestration.md` (the author's private orchestration playbook, not included here) — **el método** (Agent Orchestration **v0.5**, `last_verified` 2026-06-26, vigente y sin cambios al 2026-07-08): 2×2 (§2), role library + round structure (§7), verification contract (§8). Seguilo.
3. `docs/DECISIONS.md` **D14, D15, D16** — modelo de penales/ET + refresh R16→QF.

## Qué se hizo (lo que vas a auditar)
- **Re-pin R16→QF** martj42 `25e30198`→`273c731` (07-jul): 6 R16 NA→score + **2 R16 reprogramados por martj42 del 06 al 07** (Argentina 3-2 Egypt, Switzerland 0-0 Colombia [pen]) → R16 8/8; +4 fixtures QF; +1 shootout. El quarantine marcó los 2 reprogramados como "removidas" → se concluyó "cambio de fecha, no corrupción, 0 históricos alterados". Gate 49505/49505.
- **R16 scoreado (8/8): 50 pts, 6.250, +27.8% vs EV** (`scored_r16_2026-07-08.md`). 7/8 outcomes; exactos Paraguay 0-1 France y Portugal 0-1 Spain (12 c/u). Única caída: Brazil 2-1→**1-2 Norway** (0 pts).
- **QF PREDICHO (4/4)** (`qf_full_2026-07-08.txt`, grid@120', D14): France 1-0 Morocco, Spain 1-0 Belgium, Argentina 1-0 Switzerland, Norway 1-2 England. Todos favoritos, 0 empates.
- Previo (otras sesiones): R32 15/15 = 78 pts (+4.1%); R16 predicho el 04-jul (`r16_full_2026-07-04.txt`); modelo de penales/ET (D14, `penalty.overtime_grid`, 5º oráculo, suite 122/122).

## Artefactos a analizar (read-only)
- `predictions/scored_r16_2026-07-08.md` (+ `data/actuals_r16_2026-07-08.md`) — el scoring R16.
- `predictions/r16_full_2026-07-04.txt`, `predictions/qf_full_2026-07-08.txt` — predicciones R16 / QF.
- `predictions/scored_r32_2026-07-04.md` — R32 (coherencia).
- `scripts/score_matchday.py` + `scripts/actuals_from_csv.py` — el scorer (**ojo: no pasa `pen_pred/pen_actual`**).
- `scripts/predict_knockouts.py` + `wcprode/penalty.py` + `wcprode/optimizer.py` — el modelo a 120'.
- `docs/prode_rules.md` §1.4 (scoring KO 120' + penales), `data/raw/sources.lock.json` (`_repin_note`).

## Diseño del gate
2×2: **Error MEDIUM-HIGH × Synthesis COMPLEX → FULL SYSTEM**. Vehículo: agent team (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) si está; si no, subagentes read-only (`Read, Grep, Glob`) con prompt adversarial. Reviewers FRESH, cold, spawn prompt autocontenido. **Modelo por tarea (§7):** Opus para juicio/adversarial/domain; **Sonnet para el fidelity mecánico**.

**1. Data Scientist (Opus)** — rigor estadístico/ML.
- ¿El **+27.8%** de R16 (50/8) es fiel y bien interpretado? N=8 → ¿ruido? ¿Los 2 exactos (12 c/u) dominan? Sensibilidad leave-out.
- ¿El modelo a 120' (D14) se aplicó bien en R16 y QF? ¿Fit correcto (base_date, decay, ξ=0.0018, ρ/γ del header)?
- ¿Las predicciones QF (todos favoritos, **0 empates**) son razonables? ¿`Norway 1-2 England` coherente tras el batacazo Norway→Brazil, o el fit sobre-reaccionó a 1 partido?
- **Calibración acumulada KO** (R32 15 + R16 8 = 23): EV predicho vs realizado (+4.1%, +27.8%) — ¿sub-estima sistemáticamente o ruido?

**2. Adversarial (Opus)** — tratá de ROMPERLO.
- ¿El join con **fechas reprogramadas** (predicción fecha-06 vs actual fecha-07 en Argentina-Egypt / Switzerland-Colombia) perdió/duplicó algún partido?
- **La nota latente del scorer (D15):** `score_matchday` no puntúa el +5 de penales. Switzerland-Colombia fue 0-0 (penales), predijimos Colombia (no empate) → 2 pts. ¿Y si en QF/semis un pick de empate va a penales — hay tal pick? ¿El modelo a 120' **garantiza** 0 empates o puede colar uno?
- ¿La reprogramación de fecha esconde un score que sí cambió y se enmascaró? ¿Over-interpretación del +27.8%? Hidden assumptions, cherry-picking.

**3. Verifier — fidelity (Sonnet)** — DIRECT_FETCH ground truth, recálculo MECÁNICO (sin juicio).
- **Recalculá el score R16 de cero:** `match_points((pred),(real))` sobre las 8 (predicciones de `r16_full_2026-07-04.txt` vs actuals del CSV re-pineado). ¿Da **50 pts / +27.8%**, celda por celda?
- Verificá que se scorearon los **8** (ninguno perdido por el cambio de fecha 06→07).
- Diff del re-pin: las 2 "removidas" (fecha-06) = MISMO matchup (home/away) que las agregadas (fecha-07); **0 filas score→score distinto**. Gate 49505.
- sha256 del `results.csv`/`shootouts.csv` local == el lock (`273c731`). Suite 122/122 y `git diff` de los 5 `*_oracle.py` = vacío (no editados).

**4. Metodología / proceso (Opus)** — guard-rails + coherencia (juicio).
- Guard-rails: hash-pin (pin `273c731`), **WC2022 RESERVADA VIRGEN** (no aparece en fit/score), EV-pure (D9). ¿El proceso del refresh (re-pin → score → predict) es consistente con D13/D14?
- **¿La nota del scorer (penales) es un gap de proceso** que muerde en rondas futuras, o el modelo a 120' lo hace inofensivo? Dictaminá con criterio, no solo constatá.
- Coherencia D14/D15/D16; la reprogramación de fecha bien documentada (D16). ¿Falta registrar algo?

## Output (cada finding — Agent Orchestration v0.5 §8)
| # | Severity | Finding | Locator (file:line / artefacto) | Provenance (VERIFIED_IN_ARTIFACT/INFERRED/ASSUMED) | Confidence | Falsified_by |

Read-only: ningún agente edita nada; devuelven findings crudos.

## Audit trail (Agent Orchestration v0.5 §8 — preservá prompts + outputs)
Guardá EMPAREJADOS el spawn prompt de cada reviewer Y su output crudo, sin editarlos:
`docs/reviews/r16_qf/<NN>_<rol>__prompt.md` + `<NN>_<rol>__output.md`. El prompt es parte del audit trail (permite evaluar el triángulo prompt→output→trabajo integrado). Este doc (el prompt maestro) y el reporte consolidado `docs/REVIEW_r16_qf_findings_2026-07-08.md` cierran el mismo trail. Las correcciones viven en el reporte consolidado, no editando los outputs crudos.

## Tu trabajo (orquestador)
- Consolidá; clasificá critical/medium/low. **Verificá vos** los top 3-5 findings (recálculo directo / grep / abrir el archivo), NO re-leyendo agentes. `convergence ≠ evidence`.
- Synthesis advisory (`docs/REVIEW_r16_qf_findings_2026-07-08.md`) con "qué no sabemos". Preguntá a JP si querés un 2º round.

## Guard-rail duro
Es **DIAGNÓSTICO, no rediseño (D9).** El **modelo a 120' (D14) ya fue revisado** en su propio gate — acá se audita su **APLICACIÓN** en R16/QF y el proceso operativo (re-pin, scoring), NO se re-litiga el diseño del modelo. WC2022 virgen, oráculos intocables, EV-pure. El tracking KO es N chico (no concluyente); el veredicto serio es Fase 3 (cerrada). *"We do it our way."*
