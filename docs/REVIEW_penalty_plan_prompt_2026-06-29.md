# Prompt — Revisión PRE-BUILD del diseño del modelo de penales/ET

> Pegá el bloque de abajo como PRIMER mensaje de una sesión NUEVA de Claude Code en `<repo-root>`.
> Es READ-ONLY (revisión de un diseño, NO build). Audit trail (Agent Orchestration v0.5 §8).

---

Sos el **orquestador (Opus)** de una revisión **PRE-BUILD** del diseño del modelo de penales/alargue (ET) del Oráculo Mundialista. Es **READ-ONLY**: NO construyas nada, NO toques código ni datos ni instales nada. El objetivo es validar el **DISEÑO** antes de aprobar el oráculo (Fase 1, D2). Desplegás un equipo de 5 (4 reviewers + 1 operator con pre/postflight dry-run) y sintetizás + verificás vos. **No delegues la verificación.**

## Paso 0 — Contexto mínimo (leé en este orden)
1. `CLAUDE.md`, `STATUS.md`, `docs/HANDOFF_knockouts.md` — estado, fase (KNOCKOUTS), guard-rails.
2. `agent-orchestration.md` (the author's private orchestration playbook, not included here) — **el método** (Agent Orchestration v0.5): 2×2 (§2), role library + round structure (§7), verification contract para review-agents (§8). Seguilo.
3. `docs/penalty_model_design.md` — **EL PLAN A REVISAR.**
4. `docs/REVIEW_r32_findings_2026-06-28.md` — el finding HIGH que origina el plan.

## Artefactos a analizar (read-only)
- `docs/penalty_model_design.md` — el diseño.
- `wcprode/optimizer.py` (línea ~39) — el término actual `5·trace(grid)·pen_win_prob`.
- `wcprode/engine.py` — el grid DC (¿expone los `λ` que el plan necesita para `f_ET`?).
- `docs/prode_rules.md` §1.4 (scoring KO, marcador a 120') + §3 (draw option value, pide `P(draw over 90/120)`).
- `data/raw/shootouts.csv` — fuente de la parte (b) (columnas, 679 filas).
- `docs/data_security.md` (threat model de ingesta) + `docs/DECISIONS.md` (D2 oráculo, D3 dependency-gate).

## Diseño del gate (5 agentes)
2×2: **Error HIGH** (toca numérica oraculizada, define cómo se predice TODO el KO) × **Synthesis COMPLEX** → **FULL SYSTEM**. Vehículo: agent team (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) si está; si no, subagentes read-only (`tools: Read, Grep, Glob`) con prompt adversarial. Cada agente cold → spawn prompt **autocontenido**.

**R0 — Operator (Sonnet): PREFLIGHT con dry-run → GO/NO-GO.** Verificá que el plan es EJECUTABLE sin construir nada:
- Baseline: `.venv/Scripts/python.exe -m pytest tests/ -q` → ¿**113 verde**? (aislada — O4/D12: sin Monte Carlo en paralelo).
- ¿`data/raw/shootouts.csv` existe y tiene las columnas que el plan asume? Inspeccioná el header (date, home_team, away_team, winner, ...).
- ¿`optimizer.py` tiene el punto de integración (el término en `expected_points`)? ¿`engine.py` expone los `λ` del partido o hay que derivarlos del grid?
- ¿El plan implica dependencias nuevas? (`scipy.stats` ya está; ¿algo más? → gate D3).
- Emití **GO/NO-GO** con los supuestos verificados/rotos del plan.

**R1 — 4 reviewers FRESH en paralelo** (read-only, cold, spawn prompt autocontenido — pasales qué leer, qué evaluar, el output schema):

**1. Data Scientist (Opus)** — rigor estadístico/ML.
- ¿`f_ET = Σ_k Pois(λ_h_ET,k)·Pois(λ_a_ET,k)` es la fórmula correcta de P(sigue empatado tras ET)? ¿El ET no-muerte-súbita lo justifica?
- ¿`λ_ET = c·λ_90` con `c≈⅓` es razonable? ¿`f_ET ≈ 0.55–0.60` es plausible vs datos históricos de tandas?
- ¿La calibración de `pen_win_prob` desde `shootouts.csv` es sólida? ¿El supuesto "tandas ~aleatorias → ≈0.55" se sostiene?
- ¿El criterio de aceptación (corrección teórica vs significancia, por N chico — §7 del diseño) es correcto, o hay que exigir backtest con potencia?

**2. Adversarial (Opus)** — tratá de ROMPER el plan.
- ¿El "no es complejidad opcional sino corrección de gap" es válido, o una racionalización para saltarse el criterio de Fase 3 (medir si se gana su lugar)?
- ¿El factor `f_ET≈0.5` está bien, o el modelo de ET tiene un error (ej. ignora que el equipo que va perdiendo en ET ataca más → más goles → menos empate)?
- ¿El plan introduce un sesgo opuesto? ¿Over-engineering? ¿Qué supuesto, si cae, invalida el Nivel 1?

**3. Programador experto (Opus)** — rigor de implementación.
- ¿El plan es implementable limpio? ¿El punto abierto (optimizer necesita `λ`, hoy sólo recibe el grid) está bien resuelto? ¿API/parámetros?
- ¿El oráculo (Fase 1) está bien diseñado (tests con respuesta analítica, `f_ET=1` recupera el actual, edge cases)? ¿Cubre los caminos?
- ¿La integración en `optimize_match` puede romper alguno de los 4 oráculos intocables? ¿Regresión de los picks actuales?

**4. Seguridad (Opus)** — ¿hacemos algo inseguro?
- ¿Dependencias nuevas? → **dependency-gate D3** (audit doc en `docs/dep_audits/` ANTES de instalar). ¿El plan instala algo?
- ¿`shootouts.csv` se ingesta seguro (CSV-only, hash-pin en `sources.lock`, gate `data_validation`)? ¿Algún `pickle`/`.db`/deserialización/código-que-ejecuta-data?
- ¿Respeta el threat model de `data_security.md`? ¿`WC2022` sigue virgen (no se toca en el backtest)?
- ¿El plan toca el `.venv` / instala / corre algo de red sin gate?

**R2 — Tu trabajo (orquestador):**
- Consolidá con vista integral; clasificá critical/medium/low. **Verificá vos** los top 3-5 findings (DIRECT: grep/abrí el archivo/corré un cálculo), NO re-leyendo agentes. `convergence ≠ evidence`.
- Emití **GO / NO-GO sobre el plan**: ¿está listo para la Fase 1 (oráculo)? ¿Qué hay que corregir en el diseño antes?

**R3 — Operator (Sonnet): POSTFLIGHT.**
- Integridad: ¿el repo quedó intacto (read-only respetado, `git status` limpio, 0 cambios)? ¿La suite sigue verde? Cleanup de cualquier temporal.
- Checklist de salida: qué falta antes de aprobar el oráculo.

## Output (cada finding — Agent Orchestration v0.5 §8)
| # | Severity (CRITICAL/HIGH/MEDIUM/LOW) | Finding | Locator (file:line / artefacto) | Provenance (VERIFIED_IN_ARTIFACT/INFERRED/ASSUMED) | Confidence | Falsified_by |

Read-only: ningún agente edita nada; devuelven findings crudos al orquestador.

## Guard-rail duro
Es revisión **PRE-BUILD** de un **DISEÑO**. NO construir, NO codear, NO instalar, NO tocar datos. El objetivo es que el oráculo (Fase 1) se apruebe sobre un diseño sólido (D2). Diagnóstico sobre el plan. `WC2022` virgen, 4 oráculos intocables, EV-pure (D9), dependency-gate (D3). *"We do it our way."*
