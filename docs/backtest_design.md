---
doc_type: design
purpose: Diseño del harness de backtest multi-copa (Fase 3) + contrato de su oráculo. Pre-aprobación D2 ANTES de construir.
audience: [agents, humans]
when_to_use:
  - Antes de construir wcprode/backtest.py o tests/test_backtest_oracle.py
  - Para entender por qué la calibración de ξ se mide por dirección, no por valor
last_verified: 2026-06-15
maintenance: design-frozen-on-approval
related_docs:
  - DECISIONS.md
  - prode_rules.md
---

# Backtest multi-copa — diseño (Fase 3)

## Pregunta

¿El modelo sirve out-of-sample medido por **expected points** (la métrica que paga el
prode, `match_points`), y está **ξ bien calibrado**? RPS/Brier/log-loss son diagnóstico
de calibración, NO la métrica de decisión (prode_rules §3.3, EV-pure no rank-dependent).

## Decisiones (JP, 2026-06-15)

1. **Oráculo de ξ = DIRECCIONAL** (espíritu O9b), no recovery puntual. Rationale abajo (§Rationale).
2. **Set de copas = WC2018 + WC2014 + WC2010** (3 copas, era moderna, ~192 partidos held-out).
   **WC2022 RESERVADA virgen** — guardrail duro en el script (no debe solapar 2022-11-20..2022-12-18).
3. Granularidad **por fecha**, ventana de fit **`fit_since` móvil de 8 años + decay**, equipo
   no visto = **skip con log** (defaults del orquestador, bajo riesgo).

## Hallazgo de costo (benchmark 2026-06-15)

Fit denso completo (41.639 partidos pre-2018, 322 selecciones) = **4.7s**. Con ventana de
8 años antes del `base_date` = **0.8s**, con ρ̂/γ idénticos (−0.0789 vs −0.0785 / 0.2940 vs
0.2944): el decay con ξ=0.0018 (half-life 385d) ya manda lo de >8 años a peso ~0.005, así
que la ventana es gratis, no una aproximación. **El cómputo NO es restricción**: 3 copas ×
~28 fechas × ~7 valores de ξ ≈ 10-45 min.

## Contrato de API (`wcprode/backtest.py`)

Descompuesto en funciones puras para que el oráculo asierte exacto.

```python
def build_train(played, target_date, *, window_years=8) -> pd.DataFrame:
    """Partidos utilizables para predecir un partido en target_date (str o Timestamp).
    Frontera superior ESTRICTA: date < target_date (sin leakage). Borde inferior INCLUSIVO:
    date >= target_date - window_years*365.25 d (None = todo el historial). Subset, no muta.
    (El borde inferior es holgado: a 8a el peso de decay ya es ~0, ver §Hallazgo de costo.)"""

def score_prediction(grid, actual, *, knockout=False, pen_win_prob=0.55) -> int:
    """Puntos del prode = match_points(optimize_match(grid,...)['best'], actual).
    Usa la cadena YA oraculizada (optimizer + scoring); NO re-implementa el puntaje."""

@dataclass
class BacktestResult:
    points: np.ndarray   # pts por partido predicho; points[i] ALINEA con records[i]
    records: list[dict]  # por partido, EN ORDEN TEMPORAL ascendente: date (ISO str/Timestamp,
                         # ordenable), home, away, neutral, pred (ph,pa), actual (ah,aa), pts
    n_predicted: int     # == len(points) == len(records)
    n_skipped: int       # saltados por fallo de predict (unseen + masa), on_predict_error='skip'
    ep: float            # media sobre los n_predicted (skips EXCLUIDOS): points.sum()/n_predicted
    se: float            # SE bootstrap, np.random.default_rng(seed) LOCAL (reproducible entre procesos)
    xi: float
    fit_rho: bool

def rolling_origin_points(played, held_out, *, xi, fit_rho=True, window_years=8,
                          knockout=False, on_predict_error="skip", n_boot=2000, seed=20260615) -> BacktestResult:
    """Backtest rolling-origin held-out por expected points.
    Precondición: held_out ⊆ played (los held-out alimentan los trains de fechas
    posteriores -> rolling REAL). Por cada fecha D distinta en held_out (asc):
      eng = DixonColesEngine(xi, fit_rho).fit(build_train(played, D, window_years), base_date=D)
      por cada partido de held_out en D: score_prediction(eng.predict(...).grid, actual).
    on_predict_error: 'skip' (default, cuenta en n_skipped) | 'raise'. predict puede fallar
    con ValueError (equipo no visto) O AssertionError (grilla degenerada: lam/mu explotan
    con ξ alto sobre data rala -> el engine hace fail-loud, engine.py:346). El skip cubre AMBAS.
    base_date=D es OBLIGATORIO (ancla el decay en el día de predicción). NOTA: el resultado es
    ~invariante al base_date (reescalarlo multiplica todos los pesos por una constante -> mismo
    argmin del MLE, salvo ruido de convergencia ~5e-3 verificado); se fija D por semántica, no
    por sensibilidad. El leakage real vive en build_train (frontera <D), no en base_date."""

def xi_grid_search(played, held_out, xi_grid, *, fit_rho=True, **kw) -> dict:
    """rolling_origin_points por cada xi. Devuelve:
    {'table': [(xi, ep, se, n_pred), ...], 'argmax_xi': xi*, 'results': {xi: BacktestResult}}."""
```

`played` = universo completo de jugados (incluye las copas held-out). `held_out` = subset a
predecir (mismo schema: date, home_team, away_team, home_score, away_score, neutral).

## Oráculo (`tests/test_backtest_oracle.py`, INTOCABLE D2) — 4 tiers

Generador sintético PROPIO (independiente del de test_engine_oracle), con fuerzas que pueden
variar en el tiempo. Filosofía: reducir a invariante exacta o a dirección anclada en teoría.

| Tier | Test | Asserción / bug que atrapa |
|------|------|----------------------------|
| **1 Frontera** | `train_split_strictly_before` | `build_train(_, D)` = exactamente `{date < D}`. Atrapa `<=` vs `<`. |
| | `same_day_excluded` | Partido en la misma fecha D no entra al train del otro. |
| **2 No-leakage** | `future_poison_no_change` | **El test crítico.** Resultado extremo inyectado en D+30 → predicción en D **idéntica** (bit a bit). Con leakage, el veneno futuro movería los ratings. |
| | `past_poison_does_change` | Control de poder: el mismo veneno en el **pasado** SÍ cambia la predicción. Descarta un harness que pase el anterior por ignorar todo. |
| | `target_result_does_not_leak` | **(review A6)** El marcador del propio target no entra en su fit en el rolling INTEGRADO. Atrapa `<= D` en el loop interno (que `build_train` aislado no ve). |
| | `records_aligned_and_ordered` | **(review M1/M4)** `points[i]==records[i]['pts']` y records en orden temporal ascendente. |
| **3 ξ (direccional)** | `stationary_prefers_low_xi` | Fuerzas constantes → EP(ξ=0) > EP(ξ=0.1) + 0.20. (No se asierta argmax==0: plateau plano.) |
| | `regime_change_prefers_higher_xi` | Cambio de régimen → EP(ξ=0.003) > EP(ξ=0) + 0.40. |
| **4 Sanity** | `deterministic` | Misma data+config+seed → mismo points/ep/se bit a bit. |
| | `score_prediction_uses_oracled_chain` | **(review A4)** En múltiples casos (12/5/2/0) + knockout: `score_prediction` == `match_points(optimize_match(...)['best'], actual)`. |
| | `ep_and_points_consistency` | **(review A5/H2)** pts ∈ [0,12]; EP "vivo" (>1); `ep == points.sum()/n_predicted` (denominador fijado). |
| | `predict_error_skips_and_counts` | predict que falla (unseen=`ValueError` / masa=`AssertionError`) → skip + `n_skipped`; `on_predict_error='raise'` propaga. |
| | `xi_grid_search` | **(review H1)** Tabla ξ→EP bien formada, `argmax_xi` = mayor EP y consistente con `rolling_origin_points`. Es la función que produce el veredicto de Fase 3. |

## Rationale — por qué direccional y no recovery puntual de ξ

El handoff pedía "recuperar un ξ KNOWN dentro de tolerancia" (tipo O8). **Se rechazó por
frágil:** el ξ óptimo no tiene forma cerrada — depende de la velocidad del proceso generador,
del tamaño de muestra, de la densidad de partidos, y de que EP es una métrica escalonada (no
suave). Un assert `ξ* = 0.0018 ± 0.0005` sería un número mágico sin ancla teórica, que falla
espurio o pasa vacío. Lo que SÍ tiene ancla es la **dirección**, exactamente como O9b
(`two_eras_decay_direction`) testeó dirección y no valor: sin no-estacionariedad, decaer solo
tira información (ξ bajo gana); con cambio de régimen el pasado lejano engaña (ξ alto gana). Si
el harness recupera esas dos direcciones en datos sintéticos donde la respuesta se conoce por
construcción, su veredicto sobre USA/Brasil-Marruecos en datos reales es confiable.

## No-leakage — la garantía

`build_train(played, D)` filtra `date < D` (estricto) y `fit(..., base_date=D)`. Ningún
partido con fecha ≥ D toca el fit que predice D. Tier 1 lo verifica por construcción (split
exacto) y Tier 2 por conducta (el veneno futuro no mueve la predicción pasada; el pasado sí).
`fit_since` (8a) acota por ABAJO (descarta lo viejo) — ortogonal al no-leakage, que es el borde
superior.

## Calibración del Tier 3 (barrido empírico 2026-06-15)

Generador sintético (en el oráculo, `_synth`): n_teams=14, n_dates=72 fechas mensuales,
gamma=0.25, Poisson independiente (fit_rho=False para aislar ξ), held_out = últimas 12
fechas, **seed=1**. Barrido de calibración: 2 escenarios × signal ∈ {0.6, 0.9, 1.2} × 5
seeds × ξ ∈ {0, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1}.

- **Estacionario** (signal=0.9): `EP(ξ=0) > EP(ξ=0.1) + 0.20`. Margen seed=1 = **1.36**;
  mínimo sobre 5 seeds = 0.42. (No se asierta `argmax==0`: el plateau {0, 3e-4, 1e-3} es
  plano por ruido de muestreo; la señal robusta vive en extremo-bajo vs extremo-alto.)
- **Régimen** (signal=1.2): `EP(ξ=0.003) > EP(ξ=0) + 0.40`. Margen seed=1 = **1.37**;
  mínimo sobre 5 seeds = 0.75. argmax=ξ=0.003 en 5/5 seeds.

**Hallazgo de robustez (encontrado validando el oráculo):** con ξ alto sobre data rala, el
fit ve pocos partidos y λ/μ explotan (p.ej. λ=7.86); la grilla truncada a max_goals=15
pierde >0.1% de masa y el engine hace **fail-loud** (`AssertionError`, engine.py:346). El
backtest de Sonnet ya lo evidenciaba (n_pred caía 168→143 en ξ=0.1). Por eso el harness trata
CUALQUIER fallo de predict (ValueError unseen + AssertionError masa) como skip contado
(`on_predict_error`). `test_stationary_prefers_low_xi` usa ξ=0.1 a propósito: fuerza ese
manejo de forma ejecutable (si el harness no lo cubre, el test crashea en vez de pasar).

## Validación del oráculo (pre-aprobación)

El oráculo se verificó SATISFACIBLE por un harness correcto ANTES de congelarlo: una referencia
mínima e independiente (la implementación obvia de `build_train` / `score_prediction` /
`rolling_origin_points` / `xi_grid_search`, NO el harness de producción) pasa las **14
aserciones (v2, tras la review)**. Tier 1: split exacto. Tier 2: veneno futuro deja la predicción
en `(4,0)` idéntica, veneno pasado la mueve a `(1,2)`, y el marcador del target no filtra
(`(4,0)==(4,0)`). Tier 3: reproduce los EP del barrido de Sonnet (seed=1). Tier 4: `xi_grid_search`
da argmax=0.0 con tabla `{0.0: 5.167, 0.1: 3.806}`. La referencia es desechable y NO se comparte
con el builder: Sonnet construye `wcprode/backtest.py` desde el contrato, no desde la referencia.

## Review adversarial (2 revisores en frío, 2026-06-15)

Dos revisores independientes (Sonnet, sin el razonamiento del autor ni la referencia) atacaron
el oráculo antes de congelarlo: R1 (poder: construir harness incorrectos que pasen) y R2
(cobertura/intención/ambigüedad del contrato). Veredicto del orquestador sobre cada finding:

**Aceptados → oráculo v2 (11→14 tests):**
- **A6 (HIGH):** `<= D` en el loop interno de `rolling_origin_points` mete el target en su
  propio train; Tier 1 sólo prueba `build_train` aislado. → `test_target_result_does_not_leak`.
- **H1 (HIGH):** `xi_grid_search` (produce el veredicto) sin test. → `test_xi_grid_search`.
- **H2 (HIGH):** denominador de `ep` ambiguo. → fijado a `points.sum()/n_predicted` (contrato + assert).
- **A4 (MED):** `score_prediction` con un solo caso. → multi-caso 12/5/2/0 + knockout.
- **A5 (MED):** bounds tautológico. → assert de EP "vivo".
- **M1/M4 (MED):** alineación/orden de records. → `test_records_aligned_and_ordered`.
- **M3/M5 (LOW):** borde de window, seed local. → fijados en el contrato.

**Descartados (con razón):**
- **A2/M2 (HIGH/MED) — base_date mal anclado:** ambos revisores convergieron en el mismo
  mecanismo ERRÓNEO ("cambia el peso relativo recientes/viejos"). Falso: los pesos relativos
  son `exp(-ξ·(date_n−date_m))`, independientes de base_date. Verificado: base=D vs
  base=max(train) difieren sólo 5e-3 (ruido de convergencia del MLE sobre verosimilitud chata,
  no sesgo del decay) y el efecto es CONSISTENTE entre valores de ξ → no contamina el argmax.
  Se fija base_date=D por semántica; no se testea (sería frágil). "Convergence ≠ evidence"
  aplicado a la propia review.
- **A1, A7:** ya mitigados por el par poison y por predict_error (los propios revisores lo confirman).
- **L2 (knockout bounds), L3 (fragilidad de seed):** fuera de scope (Fase 3 = grupos) / el
  colchón de 1.36–1.37 ya absorbe la variación de seed.
