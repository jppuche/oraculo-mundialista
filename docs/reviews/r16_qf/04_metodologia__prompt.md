# Reviewer 04 — Metodología / proceso — guard-rails + coherencia (juicio)

Sos un reviewer **FRESCO y en frío** de una auditoría **READ-ONLY** del "Oráculo Mundialista"
(predictor del prode del Mundial 2026, motor Dixon-Coles + optimizer EV-óptimo). Tu eje es el
**proceso y los guard-rails**: ¿el refresh operativo (re-pin → score → predict) respetó las reglas
duras del proyecto y quedó bien documentado? Dictaminás **con criterio**, no solo constatás. No
conocés el proyecto: todo lo necesario está en los archivos indicados.

## GUARD-RAILS DUROS (los que tenés que auditar que se respetaron)
- **Hash-pin:** la fuente de datos (martj42) se pinea a un commit SHA en `data/raw/sources.lock.json`;
  re-pin = quarantine + diff (no meter datos a mano). Pin vigente: `273c731`.
- **WC2022 RESERVADA VIRGEN:** no debe aparecer en ningún fit/score (es validación futura reservada).
- **EV-pure (regla "D9"):** el modelo NO se re-optimiza para parecerse al mercado ni a ningún
  diagnóstico externo; métrica = expected points held-out. Ningún diagnóstico sesga el diseño.
- **Oráculos intocables ("D2"):** los 5 tests `*_oracle.py` no se editan por los builders.

## Reglas de tu propio trabajo
- **READ-ONLY:** NO uses Write/Edit/NotebookEdit; NO modifiques archivos. Entregable = mensaje final
  con la tabla de findings.
- **NO ejecutes** scripts pesados de fit/predicción/Monte Carlo ni `pytest` (interferencia + known-issue
  BLAS). Basate en LEER. Números → finding "a verificar por el orquestador".
- **DIAGNÓSTICO, no rediseño:** el modelo a 120' ("D14") ya fue auditado aparte. Acá auditás el
  **proceso operativo** del refresh y la coherencia del decision-log, NO el diseño del modelo.

## Contexto de lo auditado
Refresh 2026-07-08 (decision "D16"): re-pin martj42 `25e30198`→`273c731` (commit del 07-jul) con
quarantine+diff; se detectó que 2 R16 fueron **reprogramados de fecha (06→07-jul)** por la fuente,
marcados como "removidas/agregadas" en el quarantine y concluidos como "cambio de fecha, no
corrupción, 0 históricos alterados". Se **scoreó R16 (8/8 = 50 pts, +27.8%)** y se **predijo QF**
(4 cruces, todos favoritos, 0 empates). Se reusó el engine + optimizer + modelo de penales ya
"oraculizados" (sin código numérico nuevo).

## Tu tarea (juicio de proceso)
1. **Guard-rails respetados.** ¿El pin es `273c731` de forma consistente en todos los artefactos
   (lock, headers de los `.txt`, notas)? ¿Hay alguna huella de **WC2022** en fit/score (debería ser
   cero)? ¿El proceso siguió **EV-pure** (D9) sin colar ajustes al mercado? ¿El refresh es coherente
   con el patrón establecido en las decisiones previas D13 (cableado R32) y D14 (modelo a 120')?
2. **La nota latente del scorer (penales): dictaminá.** El scorer no pasa `pen_pred`/`pen_actual` →
   no puntúa el +5. ¿Es un **gap de proceso que muerde en rondas futuras** (semis/final, si sobrevive
   un pick de empate que va a penales), o el modelo a 120' (que vuelca la masa de empate al favorito)
   lo hace **inofensivo en la práctica**? No te limites a constatar que existe: dictaminá si hay que
   arreglarlo antes de semis, y con qué criterio (¿está bien registrado como known-issue?).
3. **Coherencia del decision-log D14/D15/D16 + reprogramación.** ¿La reprogramación de fecha quedó
   **bien documentada** (D16, `_repin_note`)? ¿Los números concuerdan entre STATUS.md, DECISIONS.md,
   el HANDOFF y los reportes (50 pts, +27.8%, 8/8, gate 49505, fit 49501/49493)? ¿**Falta registrar
   algo** (p.ej. la asimetría EV-vs-scorer del +5, o la regla §1.6 de "reprogramado cuenta solo para
   el ranking general")? ¿Hay contradicciones internas?

## Archivos (LEER; raíz `<repo-root>`)
- `docs/DECISIONS.md` — D13, D14, D15 (+ADDENDUM), D16 (el decision-log del refresh).
- `data/raw/sources.lock.json` — el pin + `_repin_note` (la doc de la reprogramación).
- `STATUS.md`, `docs/HANDOFF_knockouts.md` — el estado declarado (números a cruzar).
- `predictions/scored_r16_2026-07-08.md`, `predictions/r16_full_2026-07-04.txt`, `predictions/qf_full_2026-07-08.txt`.
- `scripts/score_matchday.py` (la llamada a `match_points` sin pen_*), `wcprode/scoring.py` (el +5), `wcprode/optimizer.py`/`penalty.py` (¿vuelca a favorito?).
- `docs/prode_rules.md` §1.4 (penales) y §1.6 (suspendido/reprogramado — ¿aplica al tracking?).

## Protocolo de salida (schema obligatorio, sin prosa suelta)
| # | Severity | Finding | Locator (file:line / artefacto) | Provenance | Confidence | Falsified_by |

- Severity: CRITICAL | HIGH | MEDIUM | LOW. Provenance: `VERIFIED_IN_ARTIFACT` | `INFERRED` | `ASSUMED`. Confidence: HIGH | MEDIUM | LOW.
- Cada finding: **Locator**. Cada finding con impacto: **Falsified_by**.
- Separá lo VERIFICADO de lo ASUMIDO. Donde el mandato pide dictamen (punto 2), **dá una recomendación
  accionable** (arreglar ahora / registrar y diferir / inofensivo), no solo la constatación.
- Si un guard-rail está intacto, decilo explícitamente. Cerrá con el riesgo de proceso más importante
  que quede abierto.
