---
doc_type: design
purpose: Diseño del Poisson bivariado de Karlis-Ntzoufras (Fase 3) + contrato de su oráculo. Pre-aprobación D2 ANTES de construir.
audience: [agents, humans]
when_to_use:
  - Antes de construir wcprode/bivariate.py o de tocar tests/test_bivariate_oracle.py
  - Para entender por qué KN solo captura dependencia positiva y por qué eso es parte del resultado
last_verified: 2026-06-15
maintenance: design-frozen-on-approval
related_docs:
  - backtest_design.md
  - DECISIONS.md
---

# Poisson bivariado (Karlis-Ntzoufras) — diseño (Fase 3)

## Pregunta

¿Una dependencia goles-goles **explícita y global** (no solo la corrección τ de 4 celdas de
Dixon-Coles) se gana su lugar en **expected points held-out** contra selecciones? Es la **otra
mitad de #8**: #8 (EP, ΔEP=+0.042, z=+0.57) y #10 (log-loss, z=+1.47 tendiendo a peor) ya
midieron que la corrección ρ de DC **no** aporta en ninguna métrica. El bivariado mide la
forma explícita. Junto con #8/#10 cierra la pregunta completa "¿alguna forma de dependencia
aporta?". Métrica de decisión = EP held-out (log-loss = diagnóstico, D9: no sesga el diseño).

## Decisiones (JP, 2026-06-15)

1. **Alcance = KN puro, `λ3≥0`** (solo correlación positiva). NO se extiende a diagonal-inflated
   ni copula. El colapso a doble-Poisson independiente cuando la data prefiere dependencia
   negativa **ES parte del resultado**, no una limitación a tapar.
2. **Validación del oráculo = satisfacible (orquestador) + red-team adversarial de 2 revisores**
   en frío (mismo estándar que D5 tournament y D6 backtest).
3. `ξ=0.0018` fijo (D7), **WC2022 reservada virgen**, oráculos existentes intocables (D2),
   ningún diagnóstico (mercado #9 / log-loss #10) sesga el diseño (D9).

## El modelo (Karlis & Ntzoufras 2003)

`X = W1 + W3`, `Y = W2 + W3`, con `Wi ~ Poisson(λi)` independientes. `X`=goles local, `Y`=visita.
- Medias por la **misma regresión que DC** (comparación limpia): `log λ1 = attack_h − defence_a
  + γ·(1−neutral)`, `log λ2 = attack_a − defence_h`. Gauge `mean(attack)=0`. Time-decay con el
  mismo `ξ` (peso `w_m=exp(−ξ·días)`).
- `λ3` = covarianza común, **escalar constante**, bound `[0, λ3_max]` (análogo a `rho_bounds`).
  `Cov(X,Y)=λ3`. Permite `λ3=0` exacto en la frontera.
- pmf cerrada: `P(x,y)=e^{−(λ1+λ2+λ3)}(λ1^x/x!)(λ2^y/y!) Σ_{k=0}^{min(x,y)} C(x,k)C(y,k)k!(λ3/(λ1λ2))^k`.
- **Caso límite `λ3=0` ⇒ doble-Poisson independiente** = `DixonColesEngine(fit_rho=False)` (ρ0).

**Sin dependencias nuevas** (dependency-gate D3): la pmf sale con `math`/`scipy.special` +
`scipy.stats.poisson` + `scipy.optimize.minimize`, todo en el árbol. El método de fit es libre
(L-BFGS-B con gradiente numérico era el default sugerido — pero **D10: el numérico NO converge con ~300 equipos reales; el build final usa gradiente ANALÍTICO**, ver Addendum);
el oráculo es agnóstico al método.

## Alcance honesto (declarado y confirmado por JP)

KN solo captura correlación **positiva** (`λ3≥0`; la `Corr` de la grilla vive en `[0, ~0.22]`
para λ3 plausibles, **nunca negativa** — verificado). DC estimó `ρ̂≈−0.13` (EPL) / `≈−0.079`
(selecciones): **negativa**. **Predicción declarada:** al fittear data de selecciones el MLE
empuja `λ3→0` (frontera) y el bivariado **colapsa a ρ0**. Probable resultado: `bivariado ≈ ρ0`
en EP y log-loss. No invalida el experimento — "la dependencia positiva explícita tampoco
aporta" es un resultado. El test `t3e` ancla este colapso conductualmente.

## Contrato de API (`wcprode/bivariate.py`)

```python
def bivariate_pmf_grid(lam1, lam2, lam3, max_goals) -> np.ndarray:
    """Grilla RAW (sin normalizar), forma (max_goals+1, max_goals+1). λ3=0 ⇒ outer de Poisson."""

class BivariatePoissonEngine:
    def __init__(self, xi=0.0018, max_goals=15, lambda3_bounds=(0.0, 1.0), fit_lambda3=True): ...
    def fit(self, df, base_date=None, fit_since=None) -> self
        # fitted attrs: .attack_ .defence_ .home_adv_ .lambda3_ .loglik_ .teams_
        # fit_lambda3=False ⇒ lambda3_=0.0 EXACTO. Gauge mean(attack)=0.
    def predict(self, home, away, neutral=True) -> ScorelineGrid
        # reusa wcprode.engine.ScorelineGrid (.grid normalizada, .p_home_win/.p_draw/.p_away_win)
        # equipo no visto -> ValueError ; masa truncada < 0.999 -> AssertionError (fail-loud)
```

**MISMA interfaz que `DixonColesEngine`.** Para enchufarlo al harness D6 se generaliza
`rolling_origin_points` / `rolling_origin_logloss` con un `engine_factory` **opcional (default
DC)** — backward-compatible, así `test_backtest_oracle.py` (INTOCABLE) queda verde sin tocarse.
El reporting pareado (`PairedComparison`/`PairedLogLoss`) ya es agnóstico al modelo.

## Oráculo (`tests/test_bivariate_oracle.py`, INTOCABLE D2) — 4 tiers, 16 tests (→17 con `t1c`, D10)

Filosofía igual que los otros 3 oráculos: invariante exacta o dirección anclada en teoría.
Referencia de pmf **independiente = convolución directa** `Σ_k P(W3=k)P(W1=x−k)P(W2=y−k)`
(deriva de la construcción, NO de la fórmula cerrada algebraica). Generador sintético propio.

| Tier | Test | Asserción / bug que atrapa |
|------|------|----------------------------|
| **1 reduce-to-independent** | `t1a_lambda3_zero_is_outer_poisson` | `pmf_grid(λ1,λ2,0)`==`outer(Pois,Pois)`, rtol 1e-12. La raíz; tb ancla que la grilla es RAW. |
| | `t1b_engine_lambda3_zero_equals_rho0` | Cross-fit contra DC-ρ0 oraculizado: params/grilla idénticos (neutral y localía), `lambda3_=0.0` exacto, gauge `mean(attack)=0`. |
| **2 recovery + decay** | `t2a_parameter_recovery` | Data KN con λ3>0 conocido → fit recupera att/def/γ/λ3 (~SE). |
| | `t2b_loglik_discriminator` | Bajo la log-lik de referencia (convolución), fitted ≥ true. Pmf mal sumada / swap λ1λ2 / k mal → argmax subóptimo, falla. |
| | `t2c_decay_enters_loglik` | O9b-style: equipo fuerte-viejo/débil-reciente → con decay se ve débil. Atrapa un bivariado que ignora `w_m`. |
| **3 dependencia + límite + wiring** | `t3a_grid_covariance_equals_lambda3` | `Cov(grilla predict)=λ3_`, umbral 1e-6. |
| | `t3b_positive_dependence_only` | λ3>0→Cov>0 creciente; λ3=0→Cov=0; `Cov=λ3` exacto (incl. λ3=1.0). KN nunca da Cov<0. |
| | `t3c_fit_directional_invariants` | Fuerte gana más; localía sube P(home); grilla normalizada (O6-style). |
| | `t3d_predict_wiring_matches_manual_assembly` | `predict`==ensamblaje manual con `bivariate_pmf_grid(λ desde attrs)`, neutral y localía. Mata swap λ1↔λ2 y γ mal cableado. |
| | `t3e_negative_dependence_collapses_to_independent` | Data anti-correlacionada (Cov<0) → `λ3_→0` (frontera). Ancla bound inferior + límite estructural (el corazón del experimento). |
| **4 pmf + contrato harness** | `t4a_closed_form_equals_convolution` | Cerrada==convolución (casos asimétricos + simétrico λ1=λ2), rtol 1e-12. |
| | `t4b_marginals_are_poisson` | Marginales=`Pois(λ1+λ3)`/`Pois(λ2+λ3)` (distribución completa: media Y varianza). |
| | `t4c_grid_mass_and_normalization` | RAW masa∈[0.999,1]; normalizada suma 1, ≥0. |
| | `t4d_unknown_team_contract` | Equipo no visto → `ValueError` (skip del harness). |
| | `t4e_degenerate_grid_raises_assertion` | λ explota → masa<0.999 → `AssertionError` (el otro skip del harness). |
| | `t4f_interface_contract` | Firma `.fit(df,base_date,fit_since)` con `fit_since` que filtra; atributos presentes; `.predict→.grid` normalizada + p_home/draw/away. |

## Red-team adversarial (2 revisores en frío, 2026-06-15)

Dos revisores Sonnet independientes (sin la referencia desechable ni el razonamiento del autor)
atacaron el oráculo v1 (11 tests): R1 = poder (engines incorrectos que pasen), R2 = cobertura/
contrato. Veredicto del orquestador (cada finding juzgado y los clave **verificados
empíricamente**, no aceptados a ciegas — "convergence ≠ evidence"):

**Aceptados → oráculo v2 (11→16 tests):**
- **Bound / límite estructural** (R1-F2 + R2-M4): data anti-correlacionada → `λ3_=0.000000` exacto. → `t3e`.
- **Wiring de `predict`** (R1-F1/F3/F6): swap λ1↔λ2 y γ no anclados. → `t3d` (`predict`==ensamblaje manual, margen real 0.0).
- **`AssertionError` de masa degenerada** (R2-H2 + R1-F10): contrato de skip del harness. → `t4e`.
- **Time-decay** (R2-H3): el bivariado podía ignorar `w_m` silenciosamente. → `t2c` (O9b-style, margen 0.51).
- **`fit_since` + interface + `lambda3_=0` + gauge** (R2-H1/H4/M5 + R1-F8). → `t4f` + asserts en `t1b`.
- **Tolerancias** (R1-F5/F6): `t1b` 1e-3→1e-5, `t3a` 0.02→1e-6 (márgenes reales 1e-7/1e-10).
- **Casos extra** (R2-L1 simétrico λ1=λ2, R2-M3 λ3=1.0). → `t4a`/`t3b`.

**Descartados (con razón):**
- **R2-L3 (λ3≤min(λ1,λ2) por no-negatividad) — FALSO, verificado:** la convolución de Poissons
  no-negativas es ≥0 para todo λ3≥0; `λ3=2.0` con `λ1=λ2=0.5` da `min(grilla)=1.75e-43≥0`, masa 1.0.
  No existe esa cota superior en KN (sí en DC, donde τ puede ser <0). "Convergence ≠ evidence".
- **R2-M2 (convención de `loglik_`):** el experimento compara EP/log-loss sobre la **grilla**
  P(h,a), no `loglik_`; la convención del término constante `log(x!y!)` es irrelevante. Documentado, no testeado.
- **R2-M6 (`BacktestResult.fit_rho`):** es tarea de la generalización del harness (build), no del oráculo del modelo.
- **R1-F4/F9, R2-M1, R2-L2:** ya cubiertos (t1a/t4a/t4b) o fuera de scope (selecciones siempre tienen neutrales).

## Validación pre-congelamiento

El oráculo se verificó **SATISFACIBLE** por una referencia mínima e independiente
(implementación obvia: fórmula cerrada del paper + L-BFGS-B con gradiente numérico, **NO** el
build de producción) que pasa los **16 tests**. La referencia se mantuvo FUERA del repo durante
el red-team (anti-anchoring) y se BORRA en el commit ancla pre-build: el builder Sonnet
construye `wcprode/bivariate.py` desde este contrato, no desde la referencia.

## Método (post-aprobación)

1. Congelar oráculo (commit ancla, oráculo rojo hasta el build) + borrar la referencia desechable.
2. **Delegar build a Sonnet** (cold-prompt): `BivariatePoissonEngine` + `bivariate_pmf_grid`
   contra el oráculo; generalizar el harness backward-compatible. NO tocar los 3 oráculos
   existentes ni el engine DC.
3. **Validar (orquestador):** suite verde sin tocar oráculos; recálculo independiente de la pmf
   en 2 partidos; reduce-to-independent a mano. Tests de regresión nuevos para el harness generalizado.
4. **Correr** comparación pareada **bivariado vs DC-full vs ρ0** sobre WC2018/14/10, EP held-out
   + log-loss, SE pareado, N=192.
5. **Interpretar + documentar:** reporte `predictions/backtest_bivariado_<fecha>.md`, **D10**, STATUS/CLAUDE/README.

## Guard-rails (no re-litigar)

Oráculo pre-aprobado ANTES de construir (D2) · EP held-out métrica de decisión · ningún
diagnóstico sesga el diseño (D9) · WC2022 virgen · ξ=0.0018 fijo (D7) · 3 oráculos existentes
intocables · dependency-gate (sin paquetes nuevos).

## Addendum — qué pasó en el build (D10, 2026-06-16)

- **Gradiente analítico, no numérico.** El build delegado arrancó con gradiente numérico (como
  sugería este diseño). Pasaba el oráculo (8 equipos) pero **no convergía con ~300 equipos reales**
  (Δlog-lik≈43, λ3 espurio=0, conclusión OPUESTA: daba bivariado PEOR que ρ0). Se reemplazó por
  **gradiente analítico** (ecuaciones EM de KN vía `E[W3|x,y]`; forma de diferencias para ∂P/∂λ3,
  estable en λ3=0), validado con gradient-check vs `scipy.approx_fprime` (~1e-5).
- **Oráculo reforzado: `t1c` (16→17).** El blindspot era de **dimensionalidad**: los tests usaban
  8 equipos densos, donde cualquier optimizador converge. `t1c` exige que `biv(λ3=0)` CONVERJA a la
  log-lik de DC-ρ0 sobre el universo REAL (~300 equipos ralos, datos pineados como O4/O5). Edición
  del orquestador al oráculo congelado (D2 lo permite, logueada en DECISIONS D10).
- **Resultado:** el bivariado **no se gana su lugar** — EP bivF vs ρ0 z=1.73 (no sig), vs DC-full
  z=1.25; log-loss empate; λ3≈0.05. **Mantener `fit_rho=True`.** La predicción "colapsa a ρ0" fue
  parcialmente equivocada: hay dependencia positiva leve (λ3>0), pero no significativa. Validación
  metodológica: `bivI≡rho0` Δ=0.0000 (sin confound). Evidencia: `predictions/backtest_bivariado_2026-06-16.md`.
