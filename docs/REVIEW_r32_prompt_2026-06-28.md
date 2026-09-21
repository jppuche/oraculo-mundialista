# Prompt — Revisión crítica del Oráculo Mundialista (R32 + sesión 2026-06-28)

> Pegá el bloque de abajo como PRIMER mensaje de una sesión NUEVA de Claude Code en `<repo-root>`.
> Es un análisis READ-ONLY (diagnóstico, no rediseño). Audit trail (Agent Orchestration v0.5 §8).

---

Sos el **orquestador (Opus)** de una revisión adversarial de lo que se hizo en la última sesión del Oráculo Mundialista. Vas a desplegar un **validation gate de 3 agentes** y sintetizar + verificar vos mismo. **No delegues la verificación.** Es READ-ONLY: no modifiques código, datos ni predicciones.

## Paso 0 — Contexto mínimo (leé en este orden)
1. `CLAUDE.md`, `STATUS.md`, `docs/HANDOFF_knockouts.md` — estado, fase (KNOCKOUTS) y guard-rails.
2. `agent-orchestration.md` (the author's private orchestration playbook, not included here) — **el método que vas a usar** (Agent Orchestration v0.5): el 2×2 (§2), el role library + round structure (§7), el verification contract para review-agents (§8). Seguilo al pie.

## Qué se hizo (lo que vas a auditar)
- **Re-pin** martj42 `211a4c8`→`d5fe0956` con quarantine+diff: 24 NA→score (grupos 06-24..06-27), +16 fixtures R32, **0 históricos alterados**, gate 49493/49493.
- **Fecha 3 scoreada**: 132/24 = 5.500 pts, **+15.0% vs EV** (`predictions/scored_fecha3_2026-06-28.md`).
- **Round of 32 predicho** (15 cruces, `predictions/r32_full_2026-06-28.txt`) con `optimize_match(knockout=True, pen_win_prob=0.55)`. Hallazgo: **7/15 picks son empate** por el **draw-option-value** (el +5 de penales solo se cobra prediciendo empate → `expected_points` suma `5·P(empate)·pen_win_prob` a la diagonal). Sensibilidad medida: **4/15 picks cambian** si `pen_win_prob ∈ [0.45, 0.65]`.
- Cableado nuevo: `scripts/predict_knockouts.py` + `wcprode/ingest.py::wc2026_knockout_fixtures`. Suite **113/113** (no se tocó numérica oraculizada). SA-Canada (R32 del 28) quedó fuera: ya jugado, entra hash-puro en el commit martj42 del 29.

## Artefactos a analizar (read-only)
- `predictions/r32_full_2026-06-28.txt` — los 15 picks.
- `wcprode/optimizer.py` — `expected_points` / `optimize_match` (el draw-option-value vive acá).
- `scripts/predict_knockouts.py` — el cableado.
- `predictions/scored_fecha3_2026-06-28.md` — el score de F3.
- `docs/prode_rules.md` (§1.4 penales, §2 scoring, §3 EV), `docs/DECISIONS.md` (D1–D12).

## Diseño del gate
Corré el 2×2: esto es **Error MEDIUM-HIGH × Synthesis COMPLEX → FULL SYSTEM**. **Vehículo:** agent team (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) para debate mutuo; si el flag no está, **subagentes paralelos** read-only (`tools: Read, Grep, Glob`) con prompt adversarial explícito. **3 roles FRESH** (anti-anchoring), cada uno con spawn prompt **autocontenido** (son cold, no heredan esta conversación — pasales qué leer, qué evaluar y el output schema):

**1. Data Scientist (Reviewer-domain analyst, Opus)** — rigor estadístico/ML.
- ¿El draw-option-value (`5·P(emp)·pen_win_prob` en la diagonal) está bien formulado? ¿Modela `P(va a penales)·P(gano la tanda)` correctamente, o doble-cuenta / omite algo?
- ¿`pen_win_prob=0.55` constante es defendible, o introduce sesgo sistemático hacia el empate?
- ¿El fit DC (rho≈−0.086, gamma≈0.208, xi=0.0018) y las probabilidades H/D/A son razonables? ¿Calibración?
- ¿`argmax EV` sobre la grilla es la métrica de decisión correcta para este prode (12/5/2 + bonus penal)?
- ¿7/15 empates es señal genuina o artefacto del scoring?

**2. Adversarial (Reviewer-adversarial, Opus)** — devil's advocate, tratá de ROMPERLO.
- ¿El draw-option-value es "gaming" de las reglas del prode más que predicción honesta del partido? ¿Qué se rompe si el supuesto de penales está mal?
- ¿El +15% de F3 es suerte (N=24, alta varianza)? Competing hypotheses para los 7 empates.
- Hidden assumptions, overinterpretation, cherry-picking. Buscá el contraejemplo que invalida una conclusión.

**3. Metodología (Verifier-fidelity + proceso, Opus)** — DIRECT_FETCH ground truth + guard-rails.
- ¿Los números del reporte son **fieles** a los artefactos? Recalculá un par de EV y el score de F3 de forma independiente.
- ¿Se respetó hash-pin (quarantine+diff, 0 históricos alterados), oráculos intocables (suite 113/113 sin editar oráculos), WC2022 virgen, EV-pure (no re-optimizar sobre el mercado, D9)?
- ¿El cableado tocó numérica oraculizada? ¿`wc2026_knockout_fixtures` y el manejo de `neutral` (anfitriones) están bien?
- ¿La interpretación es honesta (N chico = no concluyente)? Coherencia con D1–D12.

## Output (cada finding — Agent Orchestration v0.5 §8)
| # | Severity (CRITICAL/HIGH/MEDIUM/LOW) | Finding | Locator (file:line / artefacto) | Provenance (VERIFIED_IN_ARTIFACT/INFERRED/ASSUMED) | Confidence | Falsified_by |

Read-only: ningún agente edita nada; devuelven findings crudos al orquestador.

## Tu trabajo (orquestador)
- Consolidá con vista integral; clasificá critical/medium/low.
- **Verificá vos** los top 3-5 findings que más cambien la conclusión — DIRECT (grep / abrí el archivo / recalculá), NO re-leyendo al agente. `convergence ≠ evidence`.
- Synthesis advisory con sección "qué no sabemos". Marcá lo no verificado como `[UNVERIFIED]`.
- Preguntá a JP si quiere un 2º round adversarial sobre los findings críticos.

## Guard-rail duro
Es **DIAGNÓSTICO, no rediseño**. NO re-optimizar el modelo sobre este análisis ni sobre el mercado (D9). El veredicto serio de "¿el modelo es bueno?" ya está en Fase 3 (CERRADA: ninguna dependencia goles-goles se gana su lugar, `fit_rho=True`). Esto evalúa el **trabajo y el razonamiento** de la sesión, no manda cambiar el modelo. *"We do it our way."*
