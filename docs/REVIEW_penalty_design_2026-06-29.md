---
doc_type: review
purpose: Resultado de la revisión adversarial PRE-BUILD (5 agentes + verificación directa del orquestador) sobre docs/penalty_model_design.md. Gate de diseño ANTES de aprobar el oráculo (Fase 1, D2). Diagnóstico de diseño, NO rediseño (D9).
audience: [agents, humans]
when_to_use:
  - Antes de aprobar el oráculo del modelo de penales/ET (Fase 1)
  - Antes de revisar/reescribir docs/penalty_model_design.md
  - Entender por qué Nivel 1 (solo término de penales) es incoherente con su propio criterio §7
last_verified: 2026-06-29
maintenance: snapshot
status: NO-GO (revisar diseño → después aprobar oráculo)
related_docs:
  - penalty_model_design.md (EL PLAN revisado)
  - REVIEW_r32_findings_2026-06-28.md (finding HIGH que origina el plan; matiz línea 44)
  - prode_rules.md §1.4 (scoring KO a 120') + §3 (draw option value)
  - DECISIONS.md (D2 oráculo intocable, D3 dependency-gate, D8/D10 bar EP, D9 anti-drift)
---

# Revisión PRE-BUILD — Modelo de penales/alargue (ET) · Findings

**Prompt/encargo:** gate de diseño READ-ONLY antes de aprobar el oráculo (Fase 1, D2). Validar que el oráculo se apruebe sobre un diseño sólido.

**Gate:** 2×2 = Error **HIGH** (toca numérica que define cómo se predice TODO el KO restante) × Synthesis **COMPLEX** → **FULL SYSTEM**. Vehículo: 5 agentes (4 reviewers Opus frescos read-only en paralelo + 1 operator Sonnet con pre/postflight). Cold, prompt autocontenido. Consolidación + **verificación DIRECTA del orquestador** sobre los findings que mueven la conclusión (convergence ≠ evidence).

---

## Veredicto: NO-GO para congelar el oráculo (Fase 1) con el diseño actual — revisar primero, después aprobar

El enfoque es **recuperable y mayormente sólido**: la estructura `f_ET < 1` es correcta, no hay dependencias nuevas (D3 limpio), no se tocan los 4 oráculos, la ingesta es segura y WC2022 se mantiene virgen. Pero el diseño tiene **un problema de coherencia CRÍTICO** (verificado a mano por el orquestador) que, oraculizado tal cual, hornearía un término mal caracterizado. **No es rechazo del componente**; es "revisar el doc → después aprobar el oráculo". Las correcciones son baratas y pre-build.

El núcleo: `prode_rules §1.4` puntúa el marcador KO a **120'**. El término de penales y el **crédito-BASE de empate** (los 5 pts de outcome, y los 12 de exacto) sufren **el mismo gap 90'→120'**. Nivel 1 corrige solo el término de penales y deja intacto el crédito base — que es **más grande**.

---

## Findings consolidados (Agent Orchestration v0.5 §8)

| # | Sev | Finding | Locator | Provenance | Conf | Falsified_by |
|---|-----|---------|---------|-----------|------|--------------|
| 1 | **CRITICAL** | **Nivel 1 corrige la mitad MENOR del sesgo; el titular "cierra el grueso" está invertido.** El término de penales y el crédito-BASE de empate (5 pts outcome) sufren el MISMO gap 90'→120'. Nivel 1 descuenta solo el de penales (`5·P_d·(1−f)·pwp`) y deja intacto el base (`5·P_d·(1−f)`), que es **1/pwp = 1.82× MÁS GRANDE**. El matiz del orquestador en `REVIEW_r32_findings:44` ya lo concedió. Shippear Nivel 1 solo crea una incoherencia nueva: ET descuenta el bonus pero no el outcome. | `penalty_model_design.md:48,73-77`; `optimizer.py:32-39`; `prode_rules.md:59-62` | **VERIFIED (cómputo propio: ratio 1.82× robusto en f_ET∈[0.50,0.60])** | 0.9 | Que `match_points` ya descuente el outcome del empate por f_ET (no lo hace — grid 90' puro), o pwp→1 |
| 2 | **CRITICAL** | **§7 ("gap del spec ⇒ exento del bar EP de ρ/KN") se aplica inconsistente.** El mismo argumento "matchear el scoring 120'" fuerza el Nivel 2 (crédito-base), que §4 difiere. O ambos son "fix de gap" (shippear los dos o ninguno bajo el mismo gate), o el gate es discrecional (racionalización para colar complejidad). El principio es legítimo; su aplicación parcial no. | `penalty_model_design.md` §4,§7; `prode_rules.md:144` | VERIFIED (lógica del doc) | 0.85 | Un criterio que separe Nivel 1 de Nivel 2 *distinto* de "es la mitad más grande" (que #1 refuta) |
| 3 | **HIGH** | **f_ET ≈ 0.53 al c=0.30 del diseño, por debajo del 0.55–0.60 declarado; el ancla empírica (~50% de empates resueltos en ET) pide c≈⅓.** Verificado: c=0.25→0.579, **c=0.30→0.531**, c=⅓→0.503, c=0.40→0.456. El rango está presentado optimista. "c≈⅓ ajustado por cautela a 0.25–0.30" conflaciona: ⅓ ES el time-scaling (30'/90'); bajar c SUBE f_ET → corrige MENOS. La magnitud (todo el punto) descansa en una constante no derivada. | `penalty_model_design.md:50-55` | VERIFIED (cómputo propio) | 0.8 | Cita de literatura de tasa de gol/minuto en ET < 90' por el factor afirmado (el doc no da ninguna) |
| 4 | **HIGH** | **El oráculo (§5) tiene un test degenerado y le faltan dos clave.** `f_ET=0` es **inalcanzable** por λ finito (`Σ Pois·Pois ≥ e^−(λh+λa) > 0`) → no es edge real. Faltan: (i) **monotonicidad** (EV-empate estrictamente ↓ en f_ET); (ii) **regresión de flips** que fije Ivory Coast/Belgium/Switzerland al favorito a f_ET∈[0.5,0.65]; (iii) pin del rango de truncamiento de `Σ_k`. El ancla `f_ET=1` recupera el actual es correcto, pero no fija el cambio. | `penalty_model_design.md:79-88` | VERIFIED (math) | 0.85 | Que el ancla f_ET=1 + número-a-mano ya fijen el flip (no lo hacen) |
| 5 | **HIGH** | **Punto λ SIN resolver (bloquea el diseño del oráculo).** El optimizer recibe solo `grid`, no λ (`ScorelineGrid.__slots__=("grid",)`; `predict` descarta lam/mu). El doc lo deja "a evaluar". La superficie del test depende de la opción → no se puede congelar el oráculo antes de decidir. **Recomendación (más limpia, 0 riesgo de oráculo): opción (c) λ desde marginales del grid** (`λ_h≈Σ_h h·P(h,·)`), todo dentro de `optimizer.py`, sin tocar `engine.py`/`test_engine_oracle.py`. | `penalty_model_design.md:57-59`; `engine.py:333-350,98` | VERIFIED | 0.9 | Un atributo λ ya presente en ScorelineGrid (no existe) |
| 6 | MEDIUM | **El "neto 7→4 flips, 4 genuinos aguantan" se arrastra de un proxy que NO incluye la interacción base.** La corrida `pwp=0.275` (`REVIEW_r32_findings:69`) emula solo el descuento del bonus; corregir también el base (Nivel 2) empuja MÁS a favoritos y podría voltear alguno de los 4 "genuinos". La conclusión de flips no está validada para el mundo post-corrección. | `penalty_model_design.md` §3a; `REVIEW_r32_findings:69` | INFERRED | 0.6 | Una corrida pre-build de la fórmula Nivel-1 real sobre los 4 → todos siguen empate |
| 7 | MEDIUM | **Part (b) es scope creep para ~0 EV confirmado.** Verificado en `shootouts.csv`: el equipo listado-primero gana **54.1%** (367/678), first_shooter presente solo **37.8%** (256/678), gana **53.1%** (136/256) — todo ≈0.55, el constante actual. El diseño mismo predice β≈0. Construir (b) agrega calibración + join cross-era + superficie de oráculo por EV nulo → viola su propio §8 "no over-engineer". **Shippear (a); dejar pen_win_prob=0.55.** | `shootouts.csv`; `penalty_model_design.md:65-69` | VERIFIED (datos propios) | 0.8 | Un feature de matchup con |β| materialmente ≠0 held-out (el diseño predice lo contrario) |
| 8 | MEDIUM | **Fuga de virginidad WC2022 en (b): 8 de 26 filas calendario-2022 son Nov/Dic** (ventana WC2022 finals 20-nov..18-dic), probablemente tandas de la WC2022 (Croatia-Japón, NED-ARG, ARG-FRA…). pen_win_prob es base-rate global (ortogonal al fit held-out), pero ingerirlas roza la regla. **Excluir las 8 (o todo post-WC2022) de la calibración.** Además §8 ("gate data_validation") es aspiracional: **no existe `validate_shootouts`** (`validate_results` haría SchemaError sobre el schema de 5 cols). | `shootouts.csv` (8×Nov/Dic-2022); `data_validation.py:107-110`; `backtest.py:279-288` | VERIFIED (conteo propio) | 0.8 | Que las 8 filas no sean de la WC2022 finals / que (b) se descarte |
| 9 | MEDIUM | **Posible error direccional en el modelo de ET (no captado).** `f_ET=Σ Pois·Pois` asume dos Poisson **independientes y homogéneos**; en ET real, con el marcador igualado ambos juegan cauto (suprime goles) → P(sigue empatado) **> f_ET** → la corrección verdadera es más suave (menos flips que el upper-bound). El doc no lo flaggea. Segundo orden, pero no nulo. | `penalty_model_design.md:52-54`; `engine.py:64-89` | INFERRED | 0.55 | Datos ET-only mostrando persistencia de empate ≈ Poisson independiente (martj42 no separa 90'/120' → no testeable con datos pineados) |
| 10 | LOW | **"679 tandas" miscuenta por 1: son 678** (679 líneas incl. header, sin newline final; `wc -l`=678 es artefacto). El lock `rows_incl_header:679` es correcto, sha bit-idéntico (`e52e503b…`). Solo la prosa del diseño cuenta el header como tanda. | `shootouts.csv`; `sources.lock.json` | VERIFIED (propio) | 0.95 | — |
| 11 | LOW✓ | **Blast radius contenido.** Solo `test_backtest_oracle.py:237` llama `optimize_match(knockout=True)`; con `f_et` default=1.0 queda verde sin editarse. `tournament.py` resuelve penales por sampling (`_play_ko_match`), **no** comparte el path del optimizer → su Monte Carlo y oráculo intactos. Grupos (`knockout=False`) intactos. | `test_backtest_oracle.py:237`; `tournament.py:211-369` | VERIFIED_IN_ARTIFACT | 0.9 | Un oráculo que asierte EV numérico con knockout=True (ninguno) |
| 12 | LOW✓ | **Sin deps nuevas (D3 limpio), proceso D2 OK.** `scipy.stats.poisson`+numpy ya importados; f_ET no dispara el gate. Oráculo de penales = 5º archivo separado, pre-aprobado antes del build, sin tocar los 4. **Salvo** que (b) use logístico vía sklearn/statsmodels → sería dep nueva. **Pin: "numpy/scipy only".** | `engine.py:34-37`; `penalty_model_design.md` §5,§6 | VERIFIED | 0.9 | Un import nuevo en el build (ninguno diseñado) |

---

## Verificación DIRECTA del orquestador (no re-leyendo agentes)

Cómputos propios en sandbox aislado (numpy/python puro, sin tocar el repo):

**#1 — descomposición del EV de un pick-empate (d,d).** Para un empate a 90' de prob `P_d` que se resuelve en ET con prob `(1−f)`:
- Término de penales que Nivel 1 **REMUEVE** = `5·P_d·(1−f)·pwp`
- Crédito-base de outcome (5 pts) que Nivel 1 **DEJA** = `5·P_d·(1−f)` (el outcome solo se cobra si sigue empate a 120')

Con `P_d=0.27`, `pwp=0.55`:

| f_ET | over-credit REMOVIDO (penales) | over-credit DEJADO (base) | ratio dejado/removido |
|------|------|------|------|
| 0.50 | 0.371 | 0.675 | **1.82** |
| 0.53 | 0.349 | 0.634 | **1.82** |
| 0.60 | 0.297 | 0.540 | **1.82** |

El ratio = `1/pwp` exacto, invariante a f_ET. **El base que Nivel 1 deja sin tocar es 1.82× el que corrige** → "cierra el grueso del sesgo" es cuantitativamente al revés. (Nota de justicia: hay un offset parcial — la masa de empate que se resuelve en ET acredita picks decisivos y a veces deja +2 al pick-empate; ambos efectos empujan en la MISMA dirección — hacia el favorito — así que la corrección base completa (Nivel 2) empuja *más* a favoritos, no menos.)

**#3 — f_ET para par parejo (λ_90=1.3 c/u):** c=0.25→0.5787, c=0.30→**0.5308**, c=⅓→0.5031, c=0.40→0.4557. Sanity `f_ET(0,0)=1.0` ✓. Al c del diseño (0.30) ya cae por debajo del 0.55–0.60 declarado.

**#7 — base-rates de `shootouts.csv` (678 filas):** listado-primero gana 367/678=**0.541**; first_shooter presente 256/678=**0.378**; first_shooter gana 136/256=**0.531**. Todos ≈0.55 → β≈0 defendible, (b) de bajo impacto.

**#8 — conteo 2022:** 26 filas calendario-2022, **8 en Nov/Dic** (ventana WC2022 finals). sha256 del CSV bit-idéntico al lock; pin intacto.

**#10 — conteo exacto:** `awk NR`=679 líneas (sin newline final), `splitlines`→678 filas de datos. Lock `rows_incl_header:679` correcto.

---

## Qué corregir en el diseño ANTES de aprobar el oráculo (prioridad)

1. **(bloqueante, #1/#2) Resolver Nivel 1 vs Nivel 2.** Acción más valiosa y barata, pre-build: correr una **descomposición read-only del EV sobre los 15 grids R32 reales**, partiendo cada pick-empate en {exacto, outcome-empate no-exacto, un-equipo, término-penales} y cuantificar cuánto sobre-acredita el gap 90'→120' en cada uno. Con eso, decidir:
   - **(A)** scopear **Nivel 1 + Nivel 2 juntos** como una sola corrección coherente "puntuar el grid KO a 120'" (**recomendación del orquestador** — principista, cierra el gap real), o
   - **(B)** mantener Nivel 1 pero **corregir el titular** ("fija la mitad de penales", no "el grueso") y re-correr el análisis de flips con la interacción base incluida antes de afirmar "neto 7→4".
2. **(bloqueante, #5) Fijar la exposición de λ** en el texto → opción (c) marginales del grid (cero riesgo de oráculo, todo dentro de `optimizer.py`).
3. **(#4) Rehacer el oráculo:** sacar `f_ET=0`, agregar monotonicidad + regresión de flips, pinear truncamiento de `Σ_k`.
4. **(#3) Anclar c a ~⅓** (fracción empírica ~50%), exponerlo como constante nombrada (estilo `DEFAULT_PEN_WIN_PROB`) con sensibilidad reportada; corregir la prosa "cautela baja c".
5. **(#7/#8/#12) Datos/seguridad:** dropear (b) de Nivel 1 (o solo base-rate, sin logístico → sin sklearn/statsmodels); escribir `validate_shootouts()`; **excluir las 8 filas Nov/Dic-2022**; corregir "679→678".

---

## Preflight (R0) — GO

Operator Sonnet, dry-run de ejecutabilidad:
- **Suite:** no corrible en el sandbox Linux de esta sesión (scipy/pytest ausentes; instalar dispararía D3). 113/113 se **hereda** de la verificación independiente del 28-jun (`REVIEW_r32_findings`), y ninguno de los 21 archivos sucios pre-existentes toca `wcprode/` ni `tests/` → engine/optimizer/oráculos byte-unchanged desde esa verificación.
- **shootouts.csv:** columnas `date,home_team,away_team,winner,first_shooter`; sin columna de rating (se derivaría del fit DC).
- **Punto de integración:** `optimizer.py:39` (`ev += 5.0 * float(np.trace(grid)) * pen_win_prob`), confirmado.
- **λ:** no expuesto por `predict()` → punto abierto real.
- **Deps:** `scipy.stats.poisson` ya importado; sin deps nuevas para f_ET.
- **Verdict: GO** (ejecutable como build; sin blocker duro), con la asunción rota "679 filas" y el gap de λ flaggeados.

## Postflight (R3) — PASS (integridad)

| Check | Result | Evidence |
|---|---|---|
| HEAD sin commit | PASS | `949cdd6` |
| Set de archivos modificados = baseline | PASS | 21 archivos pre-existentes; 0 nuevos; 0 bajo `wcprode/`, `tests/`, `penalty_model_design.md`, `data/raw/`, `sources.lock.json` |
| 4 oráculos byte-unchanged | PASS | `git diff --stat` de los 4 → vacío |
| `data/raw/` + lock intactos | PASS | `git diff --stat` → vacío |
| Suite | NA/heredada | scipy/pytest ausentes; no instalar (D3) |
| Temp files | PASS | 0 artefactos de la review |

Repo 100% intacto, read-only respetado: **0 cambios atribuibles a la review** (este doc de findings es el único output).

### Checklist de salida antes del oráculo (Fase 1)
1. Diseño revisado y aprobado por JP (Nivel 1-vs-2 resuelto, λ fijado, c anclado, (b) decidido).
2. Oráculo de penales/ET redactado y **pre-aprobado** (D2) como 5º archivo intocable.
3. Suite re-corrida verde en el `.venv` canónico (Windows/3.14).
4. Entrada en `DECISIONS.md` (D14) logueando la aprobación del oráculo.

---

*Diagnóstico de diseño, **no** rediseño (D9). El enfoque se sostiene; el objetivo es que el oráculo se apruebe sobre un diseño coherente (D2). WC2022 virgen, 4 oráculos intocables, EV-pure, dependency-gate. "We do it our way."*
