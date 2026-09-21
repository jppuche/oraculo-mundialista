---
doc_type: review
purpose: Reporte consolidado de la revisión adversarial READ-ONLY del tramo Round of 16 (scoring) + predicciones de Cuartos (QF). Síntesis del orquestador con verification log propio. Diagnóstico, no rediseño (D9).
audience: [agents, humans]
when_to_use:
  - Antes de scorear la primera ronda KO con un pick de empate (leer finding M1)
  - Al auditar la fidelidad del refresh R16→QF (D16)
last_verified: 2026-07-08
maintenance: snapshot
related_docs:
  - DECISIONS.md (D14, D15, D16)
  - REVIEW_r16_qf_prompt_2026-07-08.md (prompt maestro)
  - reviews/r16_qf/ (prompts + outputs crudos, audit trail §8)
---

# REVIEW consolidado — R16 (scoring) + QF (predicciones) — 2026-07-08

## Veredicto

**El tramo R16→QF es SÓLIDO. Números fieles, guard-rails intactos, reprogramación genuina.** No hay
finding CRITICAL ni HIGH. El núcleo auditado resiste la verificación directa del orquestador (no solo
la convergencia de los reviewers):

- **R16 = 50 pts / 6.250 / +27.8% es FIEL** — recálculo con `match_points` real, celda por celda (7,12,0,5,12,7,5,2), y aritmética de totales reproducida por 3 vías independientes (Verifier con la función real, DS y Adversarial a mano, orquestador).
- **La reprogramación de fecha (06→07-jul) es genuina y NO enmascara ninguna corrupción** — diff completo vs el backup `25e30198`: **un solo hunk**, 8 filas `NA-NA`→score (2 con fecha corrida) + 4 fixtures QF, **0 filas con score previo alteradas** en ~49.5k.
- **Guard-rails intactos:** hash-pin `273c731` (sha256 exacto), oráculos sin editar (git diff vacío + suite 122/122), WC2022 virgen del held-out, EV-pure (D9), fit sin leakage (49493→49501 = +8 R16 jugados).

**El valor de la review está en 3 findings MEDIUM de PROCESO/INTERPRETACIÓN, ninguno invalida lo
reportado**, pero uno (M1, la asimetría EV↔scorer del +5) muerde en semis/final si no se arregla
antes. Todo es diagnóstico; nada re-litiga el diseño del modelo a 120' (D14, ya auditado en su gate).

---

## 1. Gate + método (Agent Orchestration v0.5)

- **2×2:** Error MEDIUM-HIGH (toca el ledger de calibración = objetivo #1, y la jugada real del prode) × Synthesis COMPLEX → **FULL SYSTEM**.
- **Vehículo:** 4 subagentes READ-ONLY, fresh y cold, prompt autocontenido (aunque `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` estaba disponible, el patrón §7 —reviewers independientes anti-anclaje → orquestador integra y hace de adversario cruzado— se sirve mejor con fan-out paralelo que con debate mutuo; los 4 roles son lentes ortogonales, no discrepan sobre el mismo punto).
- **Modelo por tarea (§7):** Opus para DS / Adversarial / Metodología (juicio); Sonnet para el Verifier (fidelidad mecánica).
- **Audit trail (§8):** prompts + outputs crudos emparejados en `docs/reviews/r16_qf/NN_<rol>__{prompt,output}.md`. Este reporte + el prompt maestro cierran el trail. Correcciones viven acá, no editando los crudos.

## 2. Verification log del orquestador (deciders verificados DIRECTAMENTE)

`convergence ≠ evidence`. Re-verifiqué los findings de mayor impacto por recálculo/lectura propia, no re-leyendo agentes:

| # | Claim decisivo | Cómo lo verifiqué | Verdicto |
|---|----------------|-------------------|----------|
| V1 | R16 = 50 pts / +27.8% | Recálculo a mano (7+12+0+5+12+7+5+2=50; EV 39.12; 6.250/4.890=+27.8%) + Verifier con `match_points` real, sin celda distinta | **CONFIRMADO** |
| V2 | +27.8% es indistinguible de cero (jackpot-dominado) | `scipy.stats.ttest_1samp` sobre la columna Pts−EV: R16 **t=0.924, p=0.386**; KO(23) **t=0.908, p=0.374** | **CONFIRMADO** |
| V3 | Sin los 2 exactos R16 → −11.1%; KO(23) sin 3 exactos → −7.4% | Recálculo directo | **CONFIRMADO** |
| V4 | 0 scores históricos alterados (reprogramación genuina) | `diff` completo backup `25e30198` vs `results.csv`: **1 hunk** (líneas 49495-49506), 8 `NA-NA`→score (Argentina-Egypt y Switzerland-Colombia con fecha 06→07) + 4 QF `NA-NA`, **0 otras filas** | **CONFIRMADO (evidencia dura, no aserción)** |
| V5 | sha256 `results.csv`/`shootouts.csv` == lock | `sha256sum` propio: `b58624fd…` y `9576c12d…` exactos | **CONFIRMADO** |
| V6 | Oráculos intocables (D2) | `git diff HEAD` de los 5 `*_oracle.py`: **vacío**; `git status` limpio salvo `docs/reviews/` | **CONFIRMADO** |
| V7 | Suite 122/122 | Verifier corrió `pytest -q` → "122 passed in 49.72s"; corroborado por V6 (código sin cambios desde el commit) | **CONFIRMADO** (no re-corrido: git-state limpio + O4/D12 evita pytest redundante) |
| V8 | Asimetría EV↔scorer del +5 (M1) | Lectura: `optimizer.py:39-40` suma `5·trace(grid120)·0.55` para picks de empate; `score_matchday.py:207` llama `match_points` SIN `pen_pred/pen_actual`; `scoring.py:37` exige `pen_pred` para el +5 | **CONFIRMADO** |
| V9 | El modelo a 120' NO garantiza 0 empates | `scored_r32`: Mexico 0-0 (pick de empate) sobrevivió el argmax en R32 | **CONFIRMADO** |

Ninguna verificación refutó a un reviewer. El P(emp120')≈0.27 de Mexico (→ ~0.74 de opción-penal en su EV) queda como color: el **mecanismo** del +5 está confirmado por código; el valor exacto no cambia ningún verdicto.

## 3. Findings consolidados

Ningún **CRITICAL/HIGH**. Deduplicados de los 4 reviewers, clasificados por impacto.

### MEDIUM

**M1 — Asimetría EV↔scorer del +5 de penales (doble descableado). [convergencia 4/4]**
- **Qué:** el optimizer suma `5·P(empate 120')·0.55` al EV de un pick de empate (`optimizer.py:39-40`), pero (a) el scorer llama `match_points` sin `pen_pred/pen_actual` → nunca acredita el +5 (`score_matchday.py:207`), y (b) `actuals_from_csv.py` ni siquiera propaga el ganador de la tanda. Un pick de empate que vaya a penales queda **sub-scoreado 5 pts Y comparado contra un EV que ya incluyó el +5** → doble sesgo en `Pts−EV` y `ratio real/EV`, que ES la métrica de calibración (objetivo #1).
- **Estado:** INERTE hoy (R16 y QF = 0 picks de empate; verificado). El único empate del torneo (Mexico R32) NO fue a penales, así que nunca mordió el score — pero su EV **sí** incluyó ~0.74 irrealizable (lado-EV ya activo).
- **Por qué importa:** el modelo a 120' NO elimina empates (Mexico sobrevivió, P=0.27); semis/final = matchups balanceados = mayor P(empate) **y** mayor chance de penales. El sesgo se activaría en el dato N=1 más visible e irreversible (la final).
- **Atenuante:** es un bug de **MEDICIÓN**, no de predicción. `predict_knockouts.py:81-83` ya emite el favorito de la tanda → la **jugada real cargada en el prode no se ve afectada**. Fix barato (2 scripts no-oráculo, sin tocar el engine ni los oráculos).
- **Dictamen (accionable):** *registrar y arreglar ANTES de scorear la primera ronda KO que contenga un pick de empate.* No urgente hoy; sí antes de semifinales. Al computar cada ronda, chequear si el argmax devuelve un empate; si aparece, parchear `actuals_from_csv.py` (merge de `shootouts.csv` para emitir el ganador) + `score_matchday.py` (pasar `pen_pred` desde el "favorito X" del `.txt` y `pen_actual`). Decidir además la semántica del benchmark: o el scorer cobra el +5, o el EV del optimizer lo excluye — para comparar peras con peras.
- Locators: `wcprode/optimizer.py:39-40`, `wcprode/scoring.py:37-39`, `scripts/score_matchday.py:207`, `scripts/actuals_from_csv.py:81-86`, `scripts/predict_knockouts.py:81-83`. Provenance: VERIFIED_IN_ARTIFACT. Confidence: HIGH.

**M2 — El +27.8% es ruido jackpot-dominado; el titular sobre-vende la calibración amplia. [DS + Adversarial]**
- **Qué:** todo el surplus vive en 2 marcadores exactos (Paraguay 0-1 France, Portugal 0-1 Spain = 24 de 50 pts). Los otros 6 picks rinden **−11.1% vs su propio EV**. Verificado por el orquestador: surplus vs 0 → **t=0.924, p=0.386** (indistinguible de cero); KO(23) sin los 3 exactos → **−7.4%**. **No hay sub-estimación sistemática del EV** en ninguna dirección (N=23, z<1).
- **Matiz honesto:** el reporte `scored_r16` YA dice "N=8 ruidoso, no es veredicto" y lista los exactos como "lo que mejor salió" → la honestidad NO está ausente, pero **falta la descomposición** que le muestre al lector que 2 celdas cargan todo el surplus (y las otras 6 subrinden).
- **Dictamen:** interpretación, no cálculo (los números son fieles). Diagnóstico, no rediseño — **no se toca el modelo**. Opcional: añadir una línea de "descomposición jackpot" a la lectura honesta del reporte. El tracking KO (R32 +4.1% · R16 +27.8%) debe leerse como **ruido de N chico, no tendencia**; el veredicto serio sigue siendo Fase 3 (cerrada).
- Locators: `predictions/scored_r16_2026-07-08.md:15-32,48`. Provenance: VERIFIED_IN_ARTIFACT. Confidence: HIGH.

**M3 — El scorer descarta en silencio predicciones sin actual (guard asimétrico). [Adversarial + Verifier]**
- **Qué:** el loop de `score_matchday.py` itera sobre `actuals`. Un **actual sin predicción** aborta ruidosamente (`sys.exit(1)`); una **predicción sin actual** se ignora sin aviso (N encoge en silencio). Verificado en memoria por el Verifier con las funciones reales.
- **Por qué importa:** este refresh estuvo *a 1 día* de morder — R16 era 04-06 jul; 2 partidos se corrieron al 07-07; solo se scorearon porque `--to` se fijó a mano a `2026-07-07`. Con `--to 2026-07-06` (fin original de ronda) → N=6 silencioso, sin error. La cobertura 8/8 dependió de vigilancia manual de la ventana.
- **Dictamen:** robustez de proceso. Opcional (no-oráculo): warning si `set(preds) − set(actuals)` ≠ ∅, o documentar en el runbook que `--to` debe cubrir reprogramaciones. No mordió; se resuelve junto a M1 si se toca el scorer.
- Locators: `scripts/score_matchday.py:197-232`. Provenance: VERIFIED_IN_ARTIFACT. Confidence: HIGH.

### LOW

**L1 — §1.6 (reprogramado → solo ranking General) no conectada a D16. [Adversarial + Metodología]**
`prode_rules.md §1.6`: un partido reprogramado a fecha posterior "cuenta solo para el ranking General, no para la ronda". Los 2 R16 se movieron 06→07-jul. **Matiz del orquestador (baja el finding a LOW):** (a) el propio §1.6 dice explícito *"No optimizer impact"* → **cero impacto en la calibración/EV que es el objetivo #1**; solo tocaría el "score de fecha" en el prode real de la oficina (anecdótico, objetivo #3); (b) es dudoso que un corrimiento **intra-ronda de 1 día** (R16 sigue abierta, editable por-kickoff) caiga bajo §1.6, que apunta a suspensiones/posposiciones fuera de la ronda; (c) depende de un ASSUMED no observable read-only: que el prode de la oficina haya reprogramado **igual** que martj42 (fuente de fútbol ≠ plataforma del prode). **Acción:** verificar con JP/plataforma; registrar una nota de una línea en D16. Provenance: VERIFIED (regla) + ASSUMED (aplicación). Confidence: MEDIUM.

**L2 — El `scored_r16` muestra la fecha VIEJA (07-06) de los 2 reprogramados. [DS + Adversarial + Metodología]**
Hereda `p["date"]` del `.txt` de predicciones (`score_matchday.py:216`); se jugaron 07-07. Higiene de trazabilidad; 0 impacto en puntaje (el join ignora la fecha). `data/actuals_r16_2026-07-08.md` sí tiene 07-07.

**L3 — "0 scores históricos alterados" es aserción manual, no gate codificado. [Adversarial]**
No existe función de diff en el pipeline (`ingest.py`/`data_validation.py`); la garantía se reconstruye desde el `_quarantine/`. **Mitigado:** el orquestador la verificó directamente (V4) — el residual es que no está automatizada. Considerar un helper de diff en el runbook de re-pin.

**L4 — La asimetría del +5 no está en el backlog de `STATUS.md`. [Metodología]**
Vive solo en el decision-log (D15:238, D16:250), y D15 solo captura el sub-scoreo (no el lado-EV ni el parche a `actuals_from_csv.py`). Se resuelve promoviéndola a backlog de STATUS con scope completo, junto con M1.

**L5 — Staleness de headers de doc. [Metodología]**
`STATUS.md` `last_verified: 2026-07-04` (cuerpo describe el 07-08); `HANDOFF_knockouts.md:33` mantiene la línea vestigial "martj42 más reciente verificado: d5fe0956 (2026-06-28)" que se contradice con el pin activo `273c731`. Cosmético.

**L6 — Cruft de plantilla: columna "Sin provisional (N=8)" vacía en `scored_r16`. [DS]**
Vestigio del overlay FotMob de grupos (D11); irrelevante en R16 hash-puro. Cosmético.

### Watch item (no bug)

**W1 — Norway 1-2 England: no hay sobre-reacción del fit; el riesgo es el OPUESTO. [DS]**
Con ξ=0.0018 (half-life ~385 días) un solo batacazo no domina el rating; el output lo confirma (England sigue favorito, A 0.52; Norway NO flipeó). El modelo ya sub-rateó a Norway en R16 (dio Brazil 2-1, la peor caída, −4.51) y la mantiene underdog en QF. Es **coherente con D9** (no perseguir forma reciente), pero concentra riesgo modelo-vs-realidad en Norway. Watch item, no acción.

## 4. Guard-rails verificados INTACTOS

- **Aritmética del scoring:** 50 pts / 6.250 / +27.8% fiel (Verifier con función real + 3 recálculos).
- **Join:** por `(home, away)`, date-agnóstico → 8/8, sin pérdida ni duplicado; home/away no swapeado.
- **Pin / integridad de datos:** sha256 `results.csv`+`shootouts.csv` == lock exacto; gate 49505/49505, 0 dropped (gate real corrido); reprogramación = 1 solo hunk, 0 históricos alterados (diff propio vs backup); backup del quarantine no adulterado (su sha256 == su lock).
- **Oráculos (D2):** git diff de los 5 `*_oracle.py` vacío; suite 122/122.
- **Fit sin leakage:** 49493→49501 = +8 = exactamente los 8 R16 jugados (estaban `NA` al predecirlos); ξ=0.0018 (D7), fit_rho=True (D8/D10), pen_win_prob=0.55, grid@120'(c=0.333) idénticos R16↔QF.
- **WC2022 virgen:** cero backtest en D16; WC2022 solo aparece como disclaimer. (Matiz correcto: WC2022 SÍ está en el training productivo con decay — el guard-rail la reserva del **held-out**, no del training.)
- **EV-pure (D9):** reusa engine/optimizer/penalty congelados; ningún ajuste a mercado/diagnóstico.
- **QF razonables:** los 8 participantes = 8 ganadores de R16 (sin error de crossing); 0 empates esperado por diseño (D14).

## 5. Qué NO sabemos (advisory)

- **¿El prode de la oficina reprogramó los 2 R16 igual que martj42?** No observable read-only. Activa o no §1.6 (L1) — que igual no toca la calibración.
- **¿Los actuals de KO son el marcador a 120' (post-ET, pre-tanda)?** Consistente (Switzerland 0-0 con la tanda en `shootouts.csv` aparte), pero no confirmado fila por fila sobre el CSV. Es load-bearing para scorear un modelo a 120'.
- **El P(emp120') exacto de Mexico (≈0.27):** no re-leído del `r32_full`; el mecanismo del +5 (M1) está confirmado por código, el valor exacto es color.
- **N chico:** todo el tracking KO (23 partidos) es ruido; ninguna afirmación de calibración es concluyente. El veredicto serio fue Fase 3 (cerrada).

## 6. Recomendaciones (priorizadas)

1. **Antes de semifinales (gated):** arreglar M1 — al computar cada ronda KO, si el argmax devuelve un pick de empate, cablear el +5 en el scorer (`score_matchday.py` + `actuals_from_csv.py` con `shootouts.csv`) y decidir la semántica EV↔score. Promover a backlog de STATUS con scope completo (cierra L4). Fix no-oráculo, no toca el modelo.
2. **Registrar (barato, cuando haya aire):** nota §1.6 en D16 (L1); bump de `last_verified` + borrar la línea vestigial del HANDOFF (L5).
3. **Opcional (higiene):** descomposición jackpot en la lectura de `scored_r16` (M2); warning de preds-sin-actual o nota de `--to` en el runbook (M3); helper de diff en el re-pin (L3).
4. **No hacer:** nada que toque el modelo a 120', los oráculos, ξ/ρ, ni re-optimizar sobre el tracking. Todo lo anterior es proceso/medición/higiene. *"We do it our way."*

## 7. Audit trail

- Prompt maestro: `docs/REVIEW_r16_qf_prompt_2026-07-08.md`.
- Reviewers (prompt + output crudo emparejados): `docs/reviews/r16_qf/0{1..4}_<rol>__{prompt,output}.md`.
- Verificación del orquestador: §2 de este doc (recálculos en la sesión; comandos reproducibles).
- **2º round:** no lo veo necesario — 0 findings CRITICAL/HIGH, convergencia alta, deciders verificados. A criterio de JP si quiere profundizar el vector "actuals a 120' fila por fila" o la semántica del +5 antes de tocar el scorer.

## 8. Estado de resolución (2026-07-11, D17)

JP optó por ejecutar las recomendaciones §6. Estado por finding (el fix vive en `DECISIONS.md` D17; las correcciones NO editan los outputs crudos de §7):

| Finding | Estado | Cómo |
|---------|--------|------|
| **M1** (asimetría EV↔scorer del +5) | ✅ **RESUELTO** | Semántica decidida (el scorer cobra el +5, no se quita del EV → no toca el modelo). `ingest.load_shootouts` + `actuals_from_csv` (Nota `pen: X`) + `score_matchday.penalty_pred_actual`. 8 tests de cableado; suite 122→130. R16 re-scoreado idéntico (50 pts). |
| **M2** (jackpot-dominancia no descompuesta) | ✅ **RESUELTO** | `score_matchday` emite descomposición jackpot data-driven ("sin los N exactos: X%"). `scored_r16` regenerado la muestra (−11.1%). |
| **M3** (preds-sin-actual en silencio) | ✅ **RESUELTO** | Warning no-abortante en `score_matchday` (avisa qué predicción quedó sin actual + recordá revisar `--to`). |
| **L1** (§1.6 reprogramados) | ✅ **REGISTRADO** | Nota §1.6 agregada a D16 (sin impacto en calibración; a confirmar con la plataforma si importa el ranking de fecha). |
| **L4** (gap del +5 fuera del backlog) | ✅ **CERRADO** | Se arregló en vez de diferir; documentado en D17. |
| **L5** (staleness de headers) | ✅ **RESUELTO** | `last_verified` de STATUS y HANDOFF bumpeados a 2026-07-11; línea vestigial `d5fe0956` del HANDOFF corregida. |
| **L2** (fecha vieja en `scored`) | ⏸️ **NO ACCIONADO** | Cosmético; el join ignora la fecha. Fuera de las recomendaciones §6. |
| **L3** (helper de diff en re-pin) | ✅ **RESUELTO** | `scripts/diff_repin.py`: clasifica el diff de un re-pin (NA→score / reprogramación / altas vs ⚠️ score→score alterado; exit 1 si hay alteración). Validado contra el re-pin `25e30198→273c731`: 8 NA→score, 2 reprogramados, 4 altas, **0 alterados**. Codifica la aserción antes manual "0 históricos alterados". |
| **L6** (cruft "Sin provisional") | ⏸️ **NO ACCIONADO** | Cosmético; vestigio del overlay de grupos. |
| **W1** (Norway sub-rating) | 👁️ **WATCH** | No es bug (coherente con D9); se observa, no se actúa. |

**Guard-rails del fix:** 0 oráculos tocados (`git diff` de los 5 `*_oracle.py` vacío), engine/optimizer/ξ/ρ/pen_win_prob sin cambios, suite 130/130. Es medición/proceso, no rediseño (D9).
