---
doc_type: design
purpose: Diseño del modelo de alargue (ET) + penales para puntuar el grid KO a 120'. Corrige el gap diseño-implementación COMPLETO (prode_rules §1.4 puntúa a 120'; el optimizer usa el grid 90' tanto en el crédito-base de empate como en el término de penales). PRE-BUILD: el oráculo (Fase 1) se aprueba ANTES de construir (D2).
audience: [agents, humans]
when_to_use:
  - Antes de aprobar el oráculo del modelo de penales/ET (Fase 1) y de construir
  - Entender por qué el draw-option-value sobre-tiltea a empates y cómo se corrige a 120'
last_verified: 2026-06-29
maintenance: living
status: IMPLEMENTADO (D14, 2026-06-29) — oráculo aprobado (test_penalty_oracle, 9 tests); construido (penalty.overtime_grid); suite 122/122 al cierre de D14 (hoy 130/130 tras D17). El scorer cobra el +5 desde D17 (2026-07-11)
related_docs:
  - REVIEW_penalty_design_2026-06-29.md (la revisión que forzó esta v2 — opción A)
  - REVIEW_r32_findings_2026-06-28.md (finding HIGH original; matiz línea 44)
  - prode_rules.md §1.4 (scoring KO a 120') + §3 (draw option value)
  - DECISIONS.md (D2 oráculo intocable, D3 gate)
---

# Modelo de alargue (ET) + penales — Diseño v2

> **Cambio v1→v2 (revisión PRE-BUILD, NO-GO):** la v1 corregía **solo el término de penales**
> (factor `f_ET` sobre la diagonal). La revisión demostró que el gap 90'→120' infla **también el
> crédito-BASE de empate** (5 pts outcome), y que el base es **1/pwp = 1.82× más grande** que el
> término de penales → la v1 corregía la mitad MENOR e introducía una incoherencia (ET descuenta el
> bonus pero no el outcome). v2 = **opción A: puntuar el grid KO a 120' de forma completa.**

## 1. Problema (el gap completo)

`prode_rules.md §1.4` puntúa el marcador KO al **final tras alargue (120')**; un empate real
(`ah==aa`) significa que fue a penales. `§3` (línea 144,151) pidió `P(match ends in a draw)` /
`P(draw over 90/120)`. La implementación (`optimizer.py:39`) evalúa el EV contra el grid DC de
**90'** y usa `trace(grid)=P(empate 90')` en el término de penales.

Dos componentes del EV del pick-empate sufren el MISMO gap, y **ambos** se sobre-acreditan:
1. **Crédito-base** (12 exacto + 5 outcome-empate): se cobra sobre toda la masa de empate a 90',
   pero solo la fracción que sigue empatada a 120' es empate real. **Es el grueso** (`1/pwp ≈ 1.82×`).
2. **Término de penales** (`+5`): `5·P(empate 90')·pwp`, idem inflado.

`§4 #1`: sin multiplicadores por ronda → aplica uniforme R16→final (rinde más en rondas parejas).

**Verificación pre-build (orquestador, read-only sobre los 15 grids R32, `c=⅓`):** corregir el gap
COMPLETO vuelca **5/15 picks** a favorito (no 3): los 3 ya conocidos + **Brazil y Netherlands**.
Sobreviven 2 empates (Mexico f_ET=0.66, Australia f_ET=0.64, ambos P(empate) alta). Confirma que el
crédito-base era el grueso.

## 2. Corrección (opción A — una sola corrección coherente)

**Construir el grid a 120' (`grid_120`) y evaluar TODO el EV de KO contra él** (base + outcome +
exacto + penales). El alargue solo afecta a los partidos empatados a 90':

```
grid_120[h,a] = grid[h,a]                                  si h≠a   (terminó en 90', intacto)
para cada empate (k,k):  su masa grid[k,k] se reparte por el ET
    grid_120[k+g_h, k+g_a] += grid[k,k] · Pois(g_h; λ_h_ET) · Pois(g_a; λ_a_ET)
```
- `λ_h_ET = c·λ_h`, `λ_a_ET = c·λ_a`; `λ_h,λ_a` = **marginales del grid** (opción (c), §3.1).
- ET moderno **no es muerte súbita** → goles del ET = dos Poisson independientes sobre 30'.
- **Masa conservada** (`Σ grid_120 = Σ grid = 1`). Las celdas **no-empate** se preservan y además **reciben** la masa de empates resueltos en el ET (un empate (k,k) que termina (k+i,k+j) con i≠j cae en una no-empate → es el **offset al favorito**, #70). La **diagonal** de `grid_120` proviene SOLO de empates-90' (un no-empate a 90' terminó ahí). *(Corrección post-aprobación, detectada al implementar: la v2 decía "no-empate idénticas" — falso; la convolución les SUMA masa. T3 corregido en consecuencia.)*
- `P(va a penales) = trace(grid_120)` — y SOLO puede venir de empates-90' (un no-empate a 90'
  terminó ahí), así que `trace(grid_120) = P(empate 120')` exacto.
- `f_ET ≡ trace(grid_120)/trace(grid)` **emerge** del modelo; no es un parámetro ad-hoc.

Término de penales (caso `ph==pa`): `+ 5 · trace(grid_120) · pen_win_prob`.

**`f_ET=1` (equivalente `c→0`, sin goles en ET) ⇒ `grid_120 = grid` ⇒ recupera EXACTO el optimizer
actual.** En grupos (`knockout=False`) NO se construye `grid_120`: el path actual queda intacto.

### 3.1 Exposición de λ (resuelto — opción (c), #5)
El optimizer recibe solo el `grid`. Deriva los λ de las **marginales del propio grid**
(`λ_h = Σ_h h·P(h,·)`, idem `λ_a`), **dentro de `optimizer.py`** (o un `penalty.py` nuevo). **No
toca `engine.py` ni `test_engine_oracle.py`.** (Verificado en el análisis pre-build: funciona.)

### 3.2 `c` (anclado, #3)
`c` = escala temporal del ET = `30'/90' = ⅓`. Constante nombrada (`ET_TIME_SCALE`) con sensibilidad
reportada. Ancla empírica: ~50% de los empates-90' van a penales ⇒ `f_ET ≈ 0.50` promedio, que
`c=⅓` reproduce (análisis: f_ET∈[0.46,0.66], media ~0.52). **NO bajar `c` "por cautela"** — bajar
`c` SUBE f_ET (corrige menos). Limitación declarada (#9): Poisson independiente puede subestimar la
persistencia del empate (equipos cautos con marcador igualado) → f_ET real un pelo mayor; el ancla
empírica gobierna sobre el modelo.

### 3.3 `pen_win_prob` — constante 0.55, parte (b) DROPEADA (#7)
Base-rate verificado en `shootouts.csv` (678 tandas): listado-primero gana **0.541**, first_shooter
gana **0.531** → todo ≈0.55, `β≈0`. Calibrar por matchup = **over-engineering por EV nulo** (viola
el propio "no over-engineer"). **`pen_win_prob=0.55` constante; sin modelo de matchup, sin
`shootouts.csv` en el build, sin deps nuevas.** (Si alguna vez se ingiere `shootouts.csv`: escribir
`validate_shootouts()` — `validate_results` daría SchemaError sobre su schema de 5 cols — y excluir
las 8 filas Nov/Dic-2022 = WC2022 finals, #8.)

## 4. Oráculo (Fase 1 — pre-aprobado por JP ANTES de construir, D2; 5º archivo intocable)

`tests/test_penalty_oracle.py`. Respuestas analíticas; **no** se edita una vez aprobado.

| # | Test | Asserción |
|---|------|-----------|
| T1 | **Convolución a mano.** grid juguete: (0,0)=.5,(1,0)=.3,(0,1)=.2; `λ_h_ET=λ_a_ET=0.3` | `grid_120` celda a celda = valor computado a mano (la masa .5 de (0,0) se reparte; (1,0)/(0,1) intactas) |
| T2 | **Conservación de masa** | `Σ grid_120 = 1` (±1e-9 tras truncar a K=10) |
| T3 | **No-empate GANA masa** | `grid_120[1,0] = grid[1,0] + (empate (0,0) resuelto 1-0 en ET)` = valor a mano; `> grid[1,0]`. La diagonal de `grid_120` viene SOLO de empates-90' |
| T4 | **`f_ET=1` recupera el actual** (`c→0`) | `grid_120 == grid`; `optimize_match` da el pick y EV idénticos al baseline (regresión) |
| T5 | **`trace` = P(empate 120')** caso simétrico | `trace(grid_120)` = valor a mano; `f_ET = trace(grid_120)/trace(grid)` = valor a mano |
| T6 | **Monotonicidad** | `c` ↑ ⇒ `trace(grid_120)` ↓ (estricto); EV-del-pick-empate ↓ en `c` |
| T7 | **Grupos intactos** | `knockout=False` no construye `grid_120`; EV idéntico al optimizer actual en una grilla fija |
| T8 | **Regresión de flips** | sobre grids fijos (snapshot de Ivory Coast / Mexico): pick `c=⅓` = favorito / empate respectivamente |
| T9 | **Truncamiento** | masa perdida por truncar la convolución `< 1e-6` al K elegido |

**Edge eliminado (#4):** `f_ET=0` es inalcanzable (`Σ Pois·Pois ≥ e^−(λ) > 0`) — fuera. El ancla
`f_ET=1` (T4) + monotonicidad (T6) + flips (T8) fijan el comportamiento, no solo el extremo.

## 5. Fases

| Fase | Qué | Quién |
|------|-----|-------|
| 0 | Diseño v2 (este doc) | orquestador → **JP aprueba** |
| 1 | **Oráculo (§4) pre-aprobado (D2)** | orquestador redacta → **JP aprueba** (red-team opcional) → intocable |
| 2 | Build: `grid_120` (convolución) + integrar en `optimize_match(knockout=True)` | delegable a Sonnet, orquestador valida; suite verde **sin tocar los 4 oráculos** |
| 3 | Validación: oráculos verdes; **re-correr R32** (confirmar 5 flips, 2 empates); backtest KO held-out WC2018/14/10 (**N chico, confirmatorio**); **WC2022 virgen** | orquestador |
| 4 | Interpretación + D14 (log de la aprobación del oráculo + resultado) | orquestador |

## 6. Criterio de aceptación (coherente, #2 resuelto)

Gate = **corrección teórica + oráculo**, NO significancia EP. Razón: matchea el scoring de `§1.4`
(120') — es cierre de gap, no complejidad opcional como ρ/KN. **Ahora es consistente:** corrige el
gap COMPLETO (base + penales), no una mitad. El backtest KO es confirmatorio (N chico → poca
potencia), no decisorio.

## 7. Riesgos / decisiones cerradas

- **`c` / Poisson independiente** (#3,#9): incertidumbre acotada; ancla empírica ~50% gobierna; los
  flips se vieron robustos. La estructura (puntuar a 120') es correcta con independencia de `c` fino.
- **`(b)` dropeada** (#7): EV nulo confirmado; sin sklearn/statsmodels (sin dep nueva, D3).
- **`shootouts.csv`** (#8): no se ingiere en el build; si se usara, `validate_shootouts` + excluir WC2022.
- **N chico KO** → gate = corrección, no significancia.
- **O4 (D12):** suite aislada.
- **Blast radius** (#11): solo `test_backtest_oracle.py:237` llama `optimize_match(knockout=True)`;
  con `f_ET=1` default queda verde; `tournament.py` resuelve penales por sampling (path distinto) → intacto.
- **Over-engineering:** la opción A es el alcance mínimo COHERENTE; no hay "Nivel 2" pendiente (el gap se cierra entero acá).

## 8. Verificación pre-build (orquestador, read-only)

`scratchpad/overtime_check.py` (modelo formal, convolución completa) sobre los 15 grids R32
(`c=⅓`): **7/15 cambian** — **6 empates vuelcan a favorito** (Brazil, Netherlands, Ivory Coast,
Belgium, Switzerland, Australia), **solo Mexico sobrevive** (P(empate) 0.41, la más alta). Más
agresivo que el análisis aproximado (que dejaba Mexico+Australia) porque la convolución reasigna la
masa del ET al favorito (#70). **Flips de outcome robustos**; algunos marcadores de favorito salen
2-1 vs 1-0 (marginal, sensible a `c`). La carga R32 del prode se actualizó en consecuencia.
