---
doc_type: review
purpose: Resultado de la revisión adversarial (validation gate de 3 agentes + verificación del orquestador) sobre el trabajo de la sesión KO del 2026-06-28 (R32 predicho, Fecha 3 scoreada, cableado predict_knockouts). Diagnóstico, NO rediseño.
audience: [agents, humans]
when_to_use:
  - Entender qué se auditó de la sesión R32 y con qué resultado
  - Antes de decidir si construir el modelo de penales (el único finding accionable apunta ahí)
last_verified: 2026-06-28
maintenance: snapshot
related_docs:
  - REVIEW_r32_prompt_2026-06-28.md
  - DECISIONS.md
---

# Revisión adversarial R32 — Findings

**Prompt de la revisión:** `docs/REVIEW_r32_prompt_2026-06-28.md`.
**Gate:** 2×2 = Error MEDIUM-HIGH × Synthesis COMPLEX → FULL SYSTEM. 3 agentes Opus frescos read-only en paralelo (Data Scientist / Adversarial / Metodología), cold con prompt autocontenido. Consolidación + verificación DIRECTA del orquestador sobre los findings que mueven la conclusión (convergence ≠ evidence).

## Veredicto

El trabajo de la sesión es **fiel y metodológicamente sólido**: los números reproducen al centavo, los guard-rails están intactos (oráculos sin tocar, hash-pin verificado, WC2022 virgen, EV-pure/D9), y la métrica de decisión (argmax EV sobre la grilla con `match_points` verbatim) es la correcta. **Sin findings CRITICAL ni discrepancias numéricas.**

El único finding sustantivo (HIGH) es un **sesgo en el draw-option-value**: el término `5·trace(grid)·pen_win_prob` usa P(empate en tiempo reglamentario) como proxy de P(va a penales), sobrestimándola ~2× al ignorar que el alargue resuelve ~la mitad de los empates. Eso vuelca ~3 picks de R32 hacia el empate sobre favoritos claros. **Es diagnóstico, no orden de rediseño** — cae dentro del modelo de penales ya agendado (D2, oráculo pre-aprobado antes de construir), no bloqueante, decisión de JP.

## Findings consolidados

| # | Sev | Finding | Locator | Provenance | Conf | Falsified_by |
|---|-----|---------|---------|-----------|------|--------------|
| 1 | **HIGH** | Draw-option-value infla P(penales) ~2×. `5·trace(grid)·pen_win_prob` usa P(empate reglamentario); el +5 solo se cobra si el partido sigue empatado tras 120'. El grid es DC puro sin modelo de ET → sobre-tilt sistemático a empates. | `optimizer.py:39`; `engine.py:74-110,333-344`; `prode_rules.md:144` | VERIFIED (fórmula+grid) + INFERRED (factor 2×) | 0.8 | Que el grid ya represente resultado-a-120' (no lo hace), o que ET rompa <15% de los empates (improbable). |
| 2 | **HIGH** | El sesgo flipea favoritos, no solo parejos. 3 empates con P(empate) < P(favorito): Ivory Coast (D0.30<A0.44), Belgium (D0.27<H0.46), Switzerland (D0.27<H0.45). Un empate solo le gana a un favorito 0.45 por el término de penales → si se descuenta ET (~mitad), revierten al favorito. Son 3 de los 4 que la sesión marcó pen-sensibles. | `r32_full_2026-06-28.txt:8,10,15`; `DECISIONS.md` D13 | VERIFIED_IN_ARTIFACT (picks) + INFERRED (flip) | 0.85 | Que el 1-0 favorito siga perdiendo el argmax con el término corregido por ET. |
| 3 | **MEDIUM** | +15% de F3 es ruido de cola, no señal. Recálculo del orquestador: t=0.88 (p≈0.39); sacando 2 resultados 0-0 cae a +0.9%, sacando los 5 exactos a −19.5%. El reporte dice "no concluyente" (honesto), pero el titular +15% repetido en STATUS invita a sobre-leerlo. | `scored_fecha3_2026-06-28.md:48`; `STATUS.md:16,37`; recálculo | VERIFIED (recálculo del orquestador) | 0.95 | Nada con N=24; la no-significancia ES la conclusión. |
| 4 | MEDIUM | ~27% de picks gobernados por un knob no calibrado. `pen_win_prob=0.55` puesto a mano; 4/15 cambian en [0.45,0.65]; `shootouts.csv` sin usar. | `optimizer.py:18`; `predict_knockouts.py:11-14` | VERIFIED_IN_ARTIFACT | 0.75 | Que `shootouts.csv` calibrado dé ≈0.55 y los 4 no se muevan. |
| 5 | LOW | Tensión belief↔bet (se desarma). El pick "1-1" en Brazil-Japan no es la creencia modal (Brasil 0.38). PERO la calibración se mide sobre P(h,a) (RPS/log-loss), NO sobre los picks (prode_rules §3.3) → no contamina la métrica. Vale aclararlo explícito. | `r32_full_2026-06-28.txt:4`; `prode_rules.md:160-164` | VERIFIED_IN_ARTIFACT | 0.6 | Confirmar que ningún diagnóstico de calibración consume los picks-empate. |
| 6 | LOW✓ | Fidelidad numérica perfecta. 132 / 5.500 / 114.83 / 4.785 / +15.0% reproducen exactos. `match_points` byte-idéntico a §2, 0 mismatches en 24 filas. | `scored_fecha3_2026-06-28.md`; `scoring.py` | VERIFIED (recálculo) | 0.98 | Cualquier celda distinta. |
| 7 | LOW✓ | Guard-rails respetados. Pin=`d5fe0956`; oráculos sin tocar (git diff limpio); WC2022 virgen (0 hits); EV-pure/D9 OK; SA-Canada excluido por ventana; neutral/anfitriones (Mexico+USA LOCAL, 13 neutral) correcto; cableado solo I/O. | `sources.lock.json`; git; `ingest.py`; `optimizer.py` | VERIFIED_IN_ARTIFACT | 0.9 | Diff en oráculo / pin distinto. |

## Verificación DIRECTA del orquestador (no re-leyendo agentes)

- **#3 — recálculo propio** de los 24 pares pts/EV: media diff +0.715, SE 0.815, **t=0.877 (p≈0.39)**. Leave-out: +15.0% → **+0.9%** sacando 2 resultados 0-0; → **−19.5%** sacando los 5 exactos. El "+15%" no sobrevive sacar dos jackpots 0-0.
- **#1 — lectura propia del engine** (`engine.py:74-110,333-344`): `dc_scoreline_grid` = Poisson·Poisson·τ normalizado; `predict()` no tiene ningún término de ET/penales. `trace(grid)` = P(empate reglamentario), punto.
- **#2 — lógica + artefacto:** un empate solo le gana el argmax a un outcome estrictamente más probable (favorito 0.45) gracias al +5; sin ese término el `5·ΔP` favorece al favorito por ~0.9. Confirmado que los 3 picks SON empates-sobre-favorito leyendo `r32_full`.
- **Matiz que agrega el orquestador:** el sesgo no vive solo en el término de penales. El crédito-base de resultado del pick-empate también se computa sobre el grid reglamentario, y como el ET solo modifica la región de empate (los no-empates a 90' son finales), corregir por ET **reduciría los empates aún más** que el "halve the pen term" estimado por los agentes.

## [UNVERIFIED] cerrados después (a pedido de JP)

- **Suite 113/113 — VERIFIED.** Corrida por el orquestador: `113 passed in 39.76s`. Reproducción en sandbox Linux con **numpy 2.2.6 / scipy 1.15.3 / pandas 2.3.3 / Python 3.10** (≠ `.venv` canónico Windows/3.14/numpy 2.4.6/pandas 3.0.3) y aun así verde → confirma además que los oráculos numéricos no son frágiles a drift de versión; O4 no flakeó serial.
- **Integridad del CSV pineado — VERIFIED.** sha256 bit-idénticos al lock: `results.csv a30f5a34…` (49494 filas), `shootouts.csv e52e503b…`.

## Lo que NO se pudo verificar (requiere red)

- Que el commit `d5fe0956` coincida con el historial real de martj42 en GitHub.
- La afirmación "diff vs 211a4c8: 0 históricos alterados" (necesita el commit viejo para diffear).
- La integridad archivo-local-vs-lock está sólida; lock-vs-upstream y el diff histórico siguen apoyados en el `_repin_note`.

## Guard-rail (recordatorio duro)

Diagnóstico, **no** rediseño. Nada acá manda re-optimizar el modelo ni tocar la numérica oraculizada (D2/D9). El veredicto de Fase 3 ("ninguna dependencia goles-goles se gana su lugar, `fit_rho=True`") no se toca. El único finding accionable (#1/#2) eleva el modelo de penales de "~0.06 pts/partido, nice-to-have" a "corrige un sesgo direccional que vuelca ~3 picks", pero sigue **no bloqueante**; los picks son editables hasta cada kickoff (overlay cualitativo cubre los 3 casos límite mientras tanto). *We do it our way.*

## Posible round 2 (a criterio de JP, ya sería construir, no auditar)

Cuantificar el factor de inflación con un modelo de supervivencia en ET y testear si los 3 flips (Ivory Coast / Belgium / Switzerland) revierten al favorito con el término corregido. Componente numérico → oráculo pre-aprobado antes de construir (D2).

## Verificación cruzada del orquestador de la sesión original (2026-06-29)

La sesión que produjo el trabajo auditado verificó el finding HIGH de forma independiente y cerró 2 de los 3 gaps "requiere red" (tenía el contexto que el agente cold no):

- **#1/#2 CONFIRMADO empíricamente.** Corrida del optimizer con `pen_win_prob=0.275` (= 0.55 × ½, emula el descuento por alargue; cota superior de empates): los **3 flips revierten al favorito** — Ivory Coast→`0-1 Norway`, Belgium→`1-0`, Switzerland→`1-0`. **Robusto** a la incertidumbre del factor: sus umbrales de reversión eran `pwp≥0.50`, muy por encima del rango plausible del factor ET (~0.22–0.33) → caen aunque el alargue resuelva 40% o 60% de los empates. Los otros 4 empates (P(emp) 0.30–0.41) aguantan → genuinos. **Neto: 7 empates → 4.**
- **Gaps cerrados:** *0 históricos alterados* verificado por el diff de cuarentena `d5fe0956` vs backup `_quarantine/results_OLD_211a4c8.csv`; *d5fe0956 ∈ martj42* verificado por `gh api` (historial) + `download_pinned` (sha256 vs lock).

**Carga R32 resultante (overlay, NO toca código — D2):** los 15 picks de `r32_full_2026-06-28.txt`, con **3 flips a favorito** (arriba); los otros 12 sin cambio (8 favoritos + 4 empates genuinos: Brazil, Netherlands, Mexico, Australia). El modelo de penales/ET queda agendado (no bloqueante; **aplica a todas las rondas restantes**, rinde más en las parejas → encarar antes de R16).
