---
doc_type: decision
purpose: Decision log del proyecto worldcup_prode (append-only, 1 entrada por decisión técnica con rationale y evidencia).
audience: [agents, humans]
when_to_use:
  - Antes de re-litigar una decisión técnica ya tomada
  - Al registrar una decisión nueva con impacto >= MEDIUM
last_verified: 2026-06-10
maintenance: append-only
related_docs:
  - data_security.md
  - tooling_and_methods.md
---

# Decisions — worldcup_prode

## D1 — 2026-06-05: Motor Dixon-Coles implementado in-house (numpy/scipy)

**Decisión:** implementar el motor estadístico in-house en vez de adoptar una librería externa o una capa sobre statsmodels.

| Opción | Score | Rationale resumido |
|--------|-------|--------------------|
| In-house (numpy/scipy) | **97/115** | Superficie mínima (3 deps fundacionales); modelo chico y publicado (Dixon & Coles 1997); control total del fit; oráculo de correctitud propio |
| statsmodels + capa DC propia | 87 | Menos superficie que una librería de dominio, pero agrega dep de runtime para ~150 líneas; la capa tau/decay había que escribirla igual |
| Librería externa de dominio (penaltyblog) | 61 | Árbol de ~75 deps transitivas con superficie innecesaria para este pipeline (scrapers, viz, Chrome headless, todo eager); adopción modesta verificada (171★, ~21k descargas/mes, maintainer único) |

**falsified_by:** que el build in-house no pase O4/O5 (oráculo independiente) tras esfuerzo razonable — reabriría statsmodels+capa (87).

## D2 — 2026-06-10: Oráculo de correctitud pre-aprobado en diseño; builders no lo tocan

**Decisión:** los tests del oráculo (O1-O7, ver `tests/test_engine_oracle.py`) se escriben y aprueban ANTES del build. Regla dura: builder que necesite modificar un test del oráculo se detiene y escala.

**Rationale:** una suite que solo valida su propia implementación produce tests verdes sin oráculo de correctitud independiente. Operacionaliza el principio 'executable gates over advisory rules'.

Log de ediciones del oráculo: 2026-06-11 — edición docstring-only por el orquestador (limpieza de referencias a docs internos archivados); cero cambios en tests.

**falsified_by:** un build donde la suite del oráculo pasa pero el motor produce probabilidades materialmente miscalibradas detectadas en Fase 3 — indicaría que el oráculo era débil, no que la regla sobra.

## D3 — 2026-06-10: dependency-gate a nivel proyecto, DENY-by-default con allowlist + audit docs

**Decisión:** hook PreToolUse sobre `pip install`/`uv add` en este proyecto. Allowlist mínimo (numpy/scipy/pandas/pytest); todo lo demás requiere `docs/dep_audits/<pkg>.md`.

**Rationale:** cubre el borde mecanizable de la introducción de dependencias: ninguna metodología escrita reemplaza a un hook que intercepta el install. Graduación machine-wide se evalúa post-torneo (patrón "standards not one-offs" — scope deliberadamente acotado ahora por deadline).

**falsified_by:** que una dependencia entre al proyecto sin pasar por el gate (bypass no contemplado en el matcher) — revisar matcher, no abandonar el gate.

## D4 — 2026-06-10: Consolidación post-review adversarial (11/11 findings aceptados) + escalera de modos para el día 1

**Decisión:** Se aceptaron los 11 findings de la review adversarial interna del diseño (2026-06-10, archivada localmente) y se consolidaron en la spec del build. Los 2 HIGH se cierran con tests nuevos en el oráculo (O8 recovery sintético para τ/ρ; O9 pesos de decay), entregados por el diseño en `tests/test_engine_oracle.py`.

**Decisión derivada — escalera de modos (reemplaza el safety valve Elo→Poisson):** el valve como código aparte queda obsoleto (era OTRO motor numérico sin oráculo construido la misma noche). Day-1 ladder: modo 1 = DC completo (requiere O8+O5 verdes) → modo 2 = mismo engine con `fit_rho=False` + decay (Poisson independiente ponderado, validado por O4+O9) → modo 3 = escalar a JP si O4 falla. Cutoff: 3 hrs antes del primer kickoff. Nunca se shipea modo 1 con O8 rojo.

**Nota de proceso:** el claim 4 del verification log del spec se degradó CONFIRMED → PARTIAL por F4 (las dos anclas de ρ eran temporadas distintas — "convergence ≠ evidence" aplicado al propio log del orquestador). O5 quedó anclado solo a dashee87 (dataset matched).

**falsified_by (escalera):** que el modo 2 produzca expected points held-out PEORES que un Elo→Poisson construido aparte en Fase 3 — reabriría el valve externo como peldaño.

## D5 — 2026-06-15: Final Soñada — Monte Carlo de torneo (2º optimizador) + su oráculo + datos del bracket

**Decisión:** segundo optimizador (Final Soñada, prode_rules §3.2) como Monte Carlo de torneo: `wcprode/tournament.py` simula el bracket WC2026 completo desde las probs del DixonColesEngine → marginales P(campeón)/P(subcampeón) → par óptimo A≠B (`final_sonada_pick`, fuerza bruta). Diseño completo: `docs/final_sonada_design.md`.

**Oráculo pre-aprobado (D2 aplicado al componente nuevo):** `tests/test_tournament_oracle.py` (15 tests, 4 tiers), aprobado por JP 2026-06-15 ANTES de construir. Oráculo de oro = mini-bracket de 4 equipos con forma cerrada (P(A campeón)=0.497 analítico vs MC dentro de 4·SE) + degenerado; invariantes de conteo (Σ marginales=1, campeón+subcampeón=llega-a-final); sub-componentes deterministas (desempates, 8 mejores terceros, slotting R32, pick, penales). Intocable como el del motor. Builder Sonnet implementó los cuerpos contra el oráculo; orquestador validó por su cuenta (57/57, oráculo no debilitado).

**Datos del bracket (DIRECT_FETCH 2026-06-15 por el orquestador; pineados en sources.lock.json):**
- Tabla Annex C de **495 combinaciones** (terceros→slot R32): Wikipedia template oldid=1357614390. Validación estructural dura (495 C(12,8) únicos, matching perfecto, elegibilidad por slot). Residual: no se alcanzó el PDF FIFA primario (render JS); confianza por estructura + provenance Wikipedia→regulations.
- Composición de grupos A-L: membresía derivada de martj42 (autoritativa) + etiquetas de Wikipedia ancladas por Pot 1; A-F cruzados con `data/actuals_2026-06-15.md`.
- Desempates de grupo: **head-to-head PRIMERO** (CAMBIO 2026 vs GD-global-primero de 2022; 3 fuentes). Yo lo había asumido al revés; corregido (duda incorporada).

**Knobs de modelado (decididos por JP, overruleando mis defaults):** tilt anfitrión por país de sede en knockouts (regla venue-country) [yo proponía neutral]; penales 0.55 al favorito [yo proponía 50/50]; N=50k + reporte con SE.

**Estado:** corrida PROVISIONAL al pin pre-torneo (`predictions/final_sonada_2026-06-15.md`): par óptimo **Argentina** (campeón 0.162±0.002) + **Spain** (subcampeón 0.087), EV 2.48/20. La definitiva es cerca del deadline 06-24 (re-pin martj42 Fechas 1-2 → re-fit → re-correr; el condicionamiento por resultados parciales ya está construido y testeado).

**falsified_by:** que el oráculo pase pero las marginales salgan materialmente miscalibradas en Fase 3 (vs resultado real o vs mercado) — indicaría oráculo débil. Señal temprana coherente con la Fecha 1: Morocco 5º y USA fuera del top-12 reflejan el sesgo ξ club-agresivo (mismo que dio USA perdiendo y ganó 4-1).

## D6 — 2026-06-15: Oráculo del backtest multi-copa (Fase 3) pre-aprobado + red-teamed

**Decisión:** harness de backtest rolling-origin multi-copa (`wcprode/backtest.py`, a construir) para validar el modelo out-of-sample por expected points y calibrar ξ. Oráculo (`tests/test_backtest_oracle.py`, 14 tests, 4 tiers) pre-aprobado por JP ANTES de construir (D2 aplicado al componente nuevo). Diseño + contrato de API: `docs/backtest_design.md`.

**Decisiones de diseño (JP):** (a) calibración de ξ **DIRECCIONAL** (estacionario→memoria larga, régimen→memoria corta; espíritu O9b), NO recovery puntual de un ξ KNOWN (frágil: número mágico sin ancla, EP no tiene forma cerrada); (b) set de copas **WC2018+WC2014+WC2010**, **WC2022 RESERVADA virgen** (guardrail en el script); (c) granularidad por-fecha, ventana `fit_since` 8a + decay, `on_predict_error=skip`.

**Validación pre-congelamiento (doble):** (1) SATISFACIBLE contra una referencia mínima e independiente del orquestador (14/14, análogo a `_loglik_ref`); (2) **red-team adversarial de 2 revisores en frío** (R1 poder, R2 cobertura). Aceptados → v2 (11→14 tests): **A6** (HIGH: `<= D` en el loop interno mete el target en su propio train; Tier 1 sólo prueba `build_train` aislado → `test_target_result_does_not_leak`), **H1** (HIGH: `xi_grid_search`, que produce el veredicto, sin test → `test_xi_grid_search`), **H2** (HIGH: denominador de `ep` ambiguo → fijado `points.sum()/n_predicted`), A4/A5/M1/M4. **Descartado A2/M2** (HIGH/MED, base_date): ambos revisores convergieron en un mecanismo ERRÓNEO ("cambia pesos relativos"); verificado empíricamente que base_date es ~invariante (los pesos relativos son `exp(-ξ·Δdate)`, indep. de base_date; diff base=D vs base=max(train) = 5e-3 = ruido de convergencia del MLE, consistente entre ξ → no contamina el argmax). `base_date=D` se fija por semántica, no se testea. "Convergence ≠ evidence" aplicado a la propia review.

**Costo (benchmark):** fit denso 4.7s (0.8s con ventana 8a, ρ̂/γ idénticos) → 3 copas × grid de ξ ≈ 10-45 min. El cómputo no es restricción.

**Estado:** oráculo CONGELADO (intocable; este commit es el ancla pre-build). `wcprode/backtest.py` + `scripts/backtest_multicup.py`: construcción delegada a Sonnet contra el oráculo; el orquestador valida (suite debe pasar de 57 a **71** sin tocar el oráculo). El experimento de ξ (¿USA/Brasil-Marruecos era señal o ruido?) corre después, sobre el harness validado.

**falsified_by:** que el oráculo pase pero la calibración de ξ salga materialmente miscalibrada vs datos reales held-out o vs el mercado en Fase 3 — indicaría oráculo débil pese a la doble validación.

## D7 — 2026-06-15: ξ=0.0018 confirmado (NO recalibrar) — backtest multi-copa

**Decisión:** NO recalibrar ξ; mantener **0.0018**. El backtest rolling-origin held-out (harness D6) sobre WC2018+WC2014+WC2010 muestra un **plateau plano** de EP en ξ∈[0.0005, 0.0030] (diferencias <0.5 SE) que CONTIENE a 0.0018. El argmax agregado (0.0010, EP 5.13 vs 5.03 de 0.0018) NO es significativamente mejor; mover ξ ahí sería sobreajustar al ruido del backtest.

**Evidencia:** `predictions/backtest_xi_2026-06-15.md` (tabla por copa + agregado, SE bootstrap). Lo único robusto: **ξ ≥ 0.005 degrada** el EP (2–3.4 SE). Heterogeneidad por copa fuerte (WC2010→0.0030, WC2018/2014→bajo); ninguna copa pone a 0.0018 significativamente lejos de su propio argmax.

**Cierra el knob #1** (CLAUDE.md "Known open items"): la hipótesis "ξ demasiado club-agresivo" del HANDOFF_fase3 **NO se confirma** — si lo fuera, ξ más bajo ganaría claramente, y no lo hace; si acaso, ξ alto es lo peligroso. **USA 4-1 (Fecha 1) y Morocco 5º (Final Soñada) eran ruido de muestra pequeña, no un sesgo sistemático de ξ.** "Measure, don't assume" aplicado: intuición razonable, falsada por los datos.

**Caveat (poder):** N=192, SE alto, EP escalonado (poco sensible a ξ dentro del plateau). La decisión es robusta (no tocar ξ; evitar ξ≥0.005), no una afirmación de óptimo exacto.

**falsified_by:** que un diagnóstico log-loss sobre P(h,a) (#10) o más copas (2006/2002) revelen que ξ < 0.0018 gana significativamente en EP held-out — reabriría la calibración hacia memoria más larga.

## D8 — 2026-06-15: DC-full vs ρ0 — la corrección ρ no se gana su lugar en EP; mantener fit_rho=True

**Decisión:** **Mantener `fit_rho=True`** (modelo de producción sin cambios). El backtest pareado (harness D6, `paired_model_comparison`) sobre WC2018+2014+2010 muestra que DC-full **NO supera** a ρ0 (Poisson independiente) en EP held-out: a ξ=0.0018, **ΔEP = +0.042 ± 0.073 (SE pareado), z=+0.57, N=192**. Indistinguible de cero con el test más potente disponible. Confirma+fortalece **O7** (N=64→192). NO sacar ρ: a ξ operativo no daña (lado positivo del cero), es la base teórica DC y está oraculizado; la ganancia de removerlo sería nula. Hallazgo "measure, don't assume": medimos que ρ no mueve la aguja de la **decisión**.

**Método (por qué pareado):** full y ρ0 comparten λ,μ,decay; difieren solo en la corrección τ de 4 celdas bajas → Δ_i tiene varianza chica. SE pareado mide la diferencia cancelando varianza común: en WC2018, SE marginal ≈0.46 vs **SE pareado 0.18** (~2.5× más fino). Robustez en ξ: ξ=0 z=+0.07; ξ=0.0018 z=+0.57; ξ=0.003 z=−1.71 (full tiende a **peor**, no mejor). Validado por el orquestador: recálculo independiente (merge + bootstrap seed 777 + SE analítico) reprodujo todas las celdas; suite **84/84** (13 tests de regresión nuevos, NO oráculo D2).

**Evidencia:** `predictions/backtest_models_2026-06-15.md`. Harness: `wcprode/backtest.py` (`paired_model_comparison`); script `scripts/backtest_models.py`; guardrail WC2022 movido a API pública (`assert_no_wc2022`).

**Alcance:** cubre solo **DC-full vs ρ0** (la corrección τ). El **bivariado** (dependencia explícita, no solo τ) queda pendiente: es componente numérico nuevo ⇒ oráculo pre-aprobado por JP ANTES de construir (D2).

**Caveat (poder + alcance de la métrica):** EP es **ciego a la calibración de la matriz** P(h,a) salvo por el pick óptimo; ρ mueve solo 2–3 picks de 64 por copa. Por eso esto **no** justifica remover ρ, solo que no es fuente de EP.

**falsified_by:** que **#10 (log-loss sobre P(h,a))** revele que ρ mejora significativamente la calibración de la grilla (aunque no cambie el pick) — sería evidencia de que ρ se gana su lugar en precisión aunque no en EP; o que el bivariado, una vez construido, supere a DC-full en EP held-out.

**ADDENDUM #10 (2026-06-15) — log-loss corrido, falsified_by NO se cumplió:** el diagnóstico de calibración sobre P(h,a) (`paired_logloss_comparison`, mismo held-out que #8) da **Δlog-loss = +0.0042 ± 0.0029 (SE pareado), z=+1.47, N=192** con convención "menor=mejor" → ρ tiende a calibrar **PEOR**, no mejor (consistente en las 3 copas; NO significativo a 0.05). El log-loss es ~25× más sensible que el EP (SE 0.0029 vs 0.073) y aun así no rescata a ρ. **Conclusión combinada: ρ no se gana su lugar en NINGUNA métrica** (decisión EP ni calibración log-loss). **D8 se sostiene estrictamente** (evidencia contra ρ no significativa + base teórica DC oraculizada), **pero #10 inclina hacia ρ0**: si se quisiera simplificar el modelo de producción (Occam), ρ0 tiene respaldo empírico. **DECISIÓN DE JP (2026-06-15): NO reabrir ahora — esperar más evidencia** (más copas / WC2022 virgen) antes de simplificar a ρ0; la evidencia contra ρ no es significativa, así que se mantiene `fit_rho=True` y se revisita con más datos. Evidencia: `predictions/backtest_logloss_2026-06-15.md`. Anti-drift: log-loss es DIAGNÓSTICO, el modelo NO se re-optimiza sobre él.

## D9 — 2026-06-15: Ningún diagnóstico externo (mercado incluido) sesga el diseño; postmortems comparativos son POST-torneo

**Decisión (JP):** las decisiones de diseño del modelo **NO se sesgan por el sanity vs mercado (#9) ni por ningún otro documento diagnóstico** (log-loss #10, RPS/Brier, comparaciones con Opta/casas/prediction markets, ni futuros). El diseño se rige **exclusivamente** por la metodología propia: **expected points held-out** (rolling-origin, out-of-sample), **oráculos intocables** (D2), **WC2022 reservada virgen**. El mercado y demás diagnósticos son **espejos**, no objetivos de optimización: informan, no deciden. *"We do it our way, the best we can."*

**Postmortem modelo-vs-mercado — agendado, con timing duro (no antes):**
- **(corto) post fase de grupos (~28 jun):** chequeo intermedio de calibración de lo jugado (1X2 de grupos realizados vs nuestras P y vs el mercado; deriva de las P de campeón Jun-1→fin-grupos). **N chico, NO concluyente** — el campeón no se resuelve en grupos.
- **(profundo) post-torneo (~19 jul):** análisis completo modelo-vs-mercado-vs-resultado. Aun así **N=1 a nivel torneo**: no es veredicto robusto, es evidencia anecdótica enmarcada honestamente.
- **Ninguno retroalimenta el diseño durante el torneo.** Son lectura, no recalibración.

**Rationale:** re-optimizar el modelo para parecerse al mercado sería **overfit al consenso** (que también puede errar — "convergence ≠ evidence"); hacerlo durante el torneo, con N chico, sería ruido elevado a señal. El principio ya operaba puntualmente (D8 addendum: "log-loss es diagnóstico, el modelo NO se re-optimiza sobre él"); **D9 lo eleva a regla general para TODO diagnóstico externo**. Generaliza "measure, don't assume" + anti-drift. NB: la divergencia Argentina/Morocco del #9 es exactamente el tipo de observación que NO se actúa ahora — se anota y se juzga después.

**falsified_by:** que un análisis **POST-torneo** (no antes), con evidencia **robusta y acumulada** (idealmente multi-copa, no solo WC2026 N=1), muestre un sesgo **sistemático y reproducible** del modelo que el mercado no tiene — recién ahí una corrección de diseño estaría justificada, y pasaría por su propio oráculo (D2). Divergencias puntuales (Argentina, Morocco) NO califican: son observaciones sin resolver, no sesgos demostrados.

## D10 — 2026-06-16: Poisson bivariado (KN) medido — no se gana su lugar (no significativo); mantener fit_rho=True

**Decisión:** **Mantener `fit_rho=True` (DC-full) en producción.** El Poisson bivariado de
Karlis-Ntzoufras (dependencia explícita `λ3≥0`, componente numérico nuevo con oráculo
pre-aprobado, `tests/test_bivariate_oracle.py`) **NO supera significativamente** a DC-full ni a
ρ0 en EP held-out (backtest pareado WC2018/14/10, N=192): **bivF vs ρ0 ΔEP=+0.120±0.069, z=1.73;
bivF vs DC-full ΔEP=+0.078±0.062, z=1.25** (ninguno cruza z=1.96). En log-loss, empate o un pelín
peor (z=0.52 vs ρ0). Cierra, con #8/#10, la pregunta "¿alguna forma de dependencia goles-goles
aporta EP contra selecciones?": **señal débil, no concluyente.** El bivariado queda como
componente **medido** (portfolio "measure, don't assume"), no de producción.

**Matiz (no se actúa, pero se anota):** contrario a la predicción "colapsa a ρ0", el bivariado
estima `λ3≈0.04-0.08` (positivo, consistente) y su señal de EP es **positiva** (z=1.73), **más
fuerte que la de ρ en #8** (z=0.57). Si alguna dependencia tuviera chance, sería la positiva
explícita (KN), no la τ de DC — pero N=192 no alcanza. Evidencia: `predictions/backtest_bivariado_2026-06-16.md`.

**Episodio del optimizador (lección dura — el oráculo tenía un blindspot de dimensionalidad):**
el build delegado (Sonnet) usó **gradiente numérico**; pasaba el oráculo (8 equipos) pero **no
convergía con ~300 equipos reales** (Δlog-lik≈43 del óptimo, λ3=0 espurio, bivariado PEOR que ρ0
— **la conclusión OPUESTA**). El orquestador lo detectó **dudando del λ3=0** (duda incorporada) y
verificando la convergencia contra DC-ρ0 (mismo modelo). Corrección: **gradiente analítico**
(ecuaciones EM de KN vía `E[W3|x,y]`, forma de diferencias para ∂P/∂λ3 estable en λ3=0), validado
con check de gradiente (vs `approx_fprime`, ~1e-5) + convergencia real (Δlog-lik vs DC-ρ0 pasó de
−43 a +0.0006; fit 58s→5s). **Validación metodológica:** `bivI vs rho0` = Δ=0.0000 exacto en las
3 copas (sin confound de optimizador).

**Edición del oráculo por el orquestador (D2 lo permite, aquí logueado):** se agregó
`test_t1c_convergence_at_scale` al oráculo congelado — exige que `biv(λ3=0)` CONVERJA a la log-lik
de DC-ρ0 sobre el universo REAL (~300 equipos ralos, datos pineados como O4/O5). Los demás tests
usaban 8 equipos densos, donde cualquier optimizador converge: ese era el blindspot. Suite **113/113**
(96 + 17 del oráculo bivariado v3). Harness D6 generalizado backward-compatible (`engine_factory`
opcional, default DC → `test_backtest_oracle` intacto); `rolling_origin_combined` (1 fit/fecha →
EP+log-loss) reproduce las funciones separadas bit a bit.

**falsified_by:** que más copas (2006/2002) o WC2022 (post-validación) lleven la señal de EP de λ3
a **z>1.96 sostenido** — reabriría adoptar el bivariado; pasaría por su oráculo (ya existe) y un
re-fit de producción. O que el oráculo `t1c` pase pero el modelo salga miscalibrado a escala —
indicaría que el guard-rail de convergencia aún es débil.

## D11 — 2026-06-24: Refresh Fecha 2→3 + overlay FotMob provisional (4 partidos del 06-23 con lag en martj42)

**Contexto:** al refrescar para Fecha 3 (re-pin → score F2 → predecir F3 → Final Soñada lock 06-24), el commit más reciente de martj42 (`8ce6c2d`, **09:36 UTC del 23**) es **previo** a los 4 partidos del 06-23, que figuran `NA-NA`. martj42 actualiza la mañana del día N con los resultados del N−1 → el dato del 23 llegaría recién el 24. JP optó por **no esperar** (deadline: F3 editable hasta cada kickoff + lock de Final Soñada al inicio de F3).

**Decisión:** re-pin `bc442cef`→`8ce6c2d` (trae los **20** de F2 06-18..06-22, NA→score; diff limpio: 0 filas ±, **0 scores históricos alterados**, gate 49477/49477). Los **4 del 06-23** (Colombia 1-0 DR Congo, Portugal 5-0 Uzbekistan, England 0-0 Ghana, Panama 0-1 Croatia, de **FotMob**/screenshot JP) se incorporan vía **overlay auditado** para (a) score F2 24/24 y (b) condicionamiento de la Final Soñada — **sin tocar el CSV pineado** (queda martj42 puro, hash-verificado). El overlay vive en `data/derived/` (gitignored); los actuals lo marcan `PROVISIONAL`.

**Por qué no rompe la metodología (regla dura hash-pin):** meter los 4 a mano en `results.csv` rompería el hash y haría fallar el gate en cada corrida → en su lugar, fuente pineada intacta + intervención manual **aislada, auditada y reconciliable**. **Measure-don't-assume:** se midió que los 4 del 23 **no cambian** las predicciones F3 (fit 44 vs 48: Δρ=−0.0001, Δγ=+0.0015; 5/6 picks del 24 idénticos, el 6º mismo outcome) **ni** el par óptimo de la Final Soñada (Argentina+Spain idéntico con 44 o 48 condicionados, N=30k). El overlay se usó en la FS por fidelidad a "Fecha 2 completa", no porque cambie el lock.

**Resultados:** F2 scoreada **139/24 = 5.792, +11.8% vs EV** (vs F1 −21.1%; N chico, no concluyente). F3: `predictions/fecha3_full_2026-06-24.txt`. Final Soñada lock: **Argentina (camp 0.253) + Spain (subcamp 0.094), EV 3.47** (`predictions/final_sonada_2026-06-24.md`).

**Mejoras de pipeline (scripts no-oráculo):** `predict_final_sonada.py` ganó `--results` (overlay, verify=False) + `--out` (default derivado de `pinned_at`, antes hardcodeado a 06-15) + nota ξ corregida (D7). `score_matchday.py` ganó `--label` + notas "dolió/salió" data-driven (antes prosa hardcodeada de F1).

**Plan de reconciliación (PENDIENTE):** cuando martj42 publique el commit del 24 con el 06-23 → re-pin → **verificar que los 4 marcadores coincidan con FotMob** → si coinciden: descartar overlay (el pin puro ya cubre F2 24/24), regenerar actuals sin la marca `PROVISIONAL`; si difieren: re-scorear F2 + re-evaluar el par óptimo de la FS.

**falsified_by:** que martj42 publique marcadores distintos a FotMob para esos 4 → invalida el score F2 provisional (re-scorear). El lock de la Final Soñada ya cerró al inicio de F3, así que un cambio solo afectaría el **registro**, no la jugada (y el par óptimo se midió estable).

**RECONCILIADO (2026-06-26):** ejecutado el plan, opción reconciliación pura. Re-pin `8ce6c2d`→`211a4c8` (commit canónico martj42 del 24, **48 jugados hasta el 23** — reproduce el estado del lock, no avanza estado). Los 4 del 06-23 **COINCIDEN exactos** con martj42 (Colombia 1-0, Portugal 5-0, England 0-0, Panama 0-1 → el criterio "martj42 sube scores incorrectos" queda descartado). Diff vs `8ce6c2d`: 4 NA→score (solo el 23), 0 filas ±, **0 scores históricos alterados**, gate 49477/49477. Score F2 reproducido **139/24=5.792 (+11.8%)** hash-puro (sin marca PROVISIONAL). Final Soñada reproducida desde fuente pura: **Argentina 0.253 + Spain 0.094 idéntico** (fit 49453, ρ/γ idénticos → el overlay fue fiel, no alteró el lock). Overlay `data/derived/` descartado. **Repo 100% hash-puro; lock reproducible desde el pin.** (El próximo refresh — score F3 / knockouts — re-pinea al commit más reciente.)

## D12 — 2026-06-26: O4 falso positivo raro (params frágiles bajo carga BLAS) — no arreglar ahora; umbral de acción = frecuencia

**Decisión (JP):** dejar `test_o4_crossfit_statsmodels` como está (D2 intocable). **NO** aplicar fix de hilos ni tocar la aserción **mientras el falso positivo no supere su frecuencia actual.**

**Diagnóstico:** O4 falló 1 vez (un parámetro >5e-3) durante la suite con una Final Soñada (Monte Carlo 50k) corriendo en paralelo. **NO es bug del engine:** determinista, log-lik engine-vs-statsmodels a 1.5e-11, params a 4.28e-05 (umbral 5e-3, dos órdenes de margen); pasa ~6/7 corridas limpias + **2/2 bajo carga deliberada**. Causa: la aserción **secundaria** de params es frágil en direcciones planas mal-condicionadas (el comentario del propio test lo admite); BLAS multi-hilo no es bit-reproducible y, bajo contención de CPU, el orden de reducción de sumas cambió el redondeo lo justo para cruzar el umbral. El criterio **primario** (log-lik, robusto a direcciones planas) nunca falló → la correctitud del engine no está en duda.

**Frecuencia base (la línea que gatilla acción):** ~1/7, **solo bajo carga concurrente.** **falsified_by / gatillo:** que reaparezca SIN carga, o con frecuencia > base → aplicar **(A)** `OMP_NUM_THREADS=1` (+ vars BLAS) en el entorno de tests — mata el síntoma; cuesta una dep nueva (`pytest-env`, pasa por el gate D3) y suite ~46s→~1.5-2min; o **(C)** degradar la aserción de params dejando la log-lik como único bloqueante — toca el oráculo, pasa por red-team y se loguea como edición del orquestador (igual que `t1c` en D10).

**Mitigación operativa (gratis, vigente):** no correr `pytest tests/` con `predict_final_sonada` de N grande en paralelo. **Reservado:** revisar (A)/(C) junto con el oráculo del modelo de penales (knockouts), donde ya habrá un cambio numérico que justifique abrir el oráculo con calma.

## D13 — 2026-06-28: Refresh de KO (re-pin + score F3) + cableado de R32 (predict_knockouts) + draw-option-value medido

**Contexto:** arranque de eliminatorias. Re-pin martj42 `211a4c8`→`d5fe0956` (commit del 28, 07:53 UTC) con quarantine+diff: 24 NA→score (grupos 06-24..06-27 → grupos **72/72**), +16 fixtures R32 (NA-NA), **0 scores históricos alterados**, gate 49493/49493. Fecha 3 scoreada: **132/24 = 5.500, +15.0% vs EV** (N chico, no concluyente; tracking grupos F1 −21.1% · F2 +11.8% · F3 +15.0%).

**Decisión (cableado, NO numérica nueva):** R32 se predice con `scripts/predict_knockouts.py` (nuevo) + `wcprode.ingest.wc2026_knockout_fixtures` (nuevo). Reusa el optimizer YA oraculizado (`optimize_match(knockout=True, pen_win_prob=0.55)`, draw-option-value coded+tested) → es I/O + orquestación, NO cambia el engine → **no requiere oráculo nuevo (D2 aplica a numérica del engine)**. Suite **113/113** sin tocar oráculos. `predict_matchday` queda grupos-only.

**Hallazgo — draw-option-value:** **7/15 picks de R32 son empate**. El +5 de penales solo es accesible prediciendo empate → `expected_points` suma `5·P(empate)·pen_win_prob` a la diagonal → el óptimo se vuelca al empate cuando la masa de empate es competitiva (esperado, prode_rules §1.4; **NO bug**). **Sensibilidad medida** (pen_win_prob ∈ [0.45, 0.65]): **11/15 robustos** (4 empates de P(emp) alta + 7 favoritos claros), **4/15 cambian** (Ivory Coast–Norway, Belgium–Senegal, England–DR Congo, Switzerland–Algeria). Como son casos límite (EV(empate)≈EV(favorito)), el EV en juego es chico → **el modelo de penales (Paso 3) sigue NO bloqueante en EV**, aunque mueva el pick visible en 1/4 de los cruces.

**SA-Canada (R32 del 28):** martj42 va un día atrás → figura NA-NA en `d5fe0956`; entra hash-puro en el commit del 29. JP optó por **esperar** (no overlay): ya jugado, no se predice, mueve marginal el fit, y D11 dejó el repo 100% hash-puro. Los picks de hoy son los **15 cruces del 29-jun al 3-jul**.

**Revisión adversarial AGENDADA (no ejecutada en esta sesión):** prompt en `docs/REVIEW_r32_prompt_2026-06-28.md` para lanzar en sesión nueva — validation gate de 3 agentes (data scientist + adversarial + metodología) sobre el draw-option-value, la calibración y los guard-rails, usando **Agent Orchestration v0.5** (private orchestration playbook `agent-orchestration.md`, last_verified 2026-06-26). Diagnóstico, no rediseño (D9).

**falsified_by:** que el commit martj42 del 29 traiga marcadores de grupos 06-24..06-27 distintos a los scoreados → re-scorear F3. (El re-pin verificó 0 históricos alterados → riesgo nulo para lo ya jugado.)

## D14 — 2026-06-29: Modelo de alargue (ET) + penales — oráculo aprobado + construido (puntúa el grid KO a 120')

**Decisión (JP aprobó el oráculo, D2):** construido el modelo que puntúa el grid KO a **120'** (opción A de la revisión pre-build `REVIEW_penalty_design_2026-06-29.md`). Cierra el gap diseño-implementación: el optimizer usaba P(empate 90')=`trace(grid)` tanto en el crédito-base de empate como en el término de penales, pero el marcador KO se puntúa a 120' (prode_rules §1.4).

**Modelo:** `wcprode/penalty.py::overtime_grid(grid, c)` construye el marcador a 120' por **convolución** — los no-empates terminan a 90'; cada empate (k,k) pasa por el ET (30') = dos Poisson independientes con λ=c·λ_marginal. `f_ET = trace(grid_120)/trace(grid)` **emerge** (no es parámetro). `c=⅓` (`ET_TIME_SCALE`), anclado a ~50% empírico. λ por marginales del grid (opción c, NO toca engine.py). Integrado en `optimize_match(knockout=True)` (c=⅓ default; c=0 recupera el comportamiento sin alargue); grupos intactos.

**Oráculo (5º intocable):** `tests/test_penalty_oracle.py`, 9 tests, valores independientes (poisson.pmf + convolución de referencia). Suite **122/122** (113+9) **sin tocar los 4 oráculos** (blast radius: solo `test_backtest_oracle:237`, tautología de consistencia → verde).

**Corrección de T3 (orquestador, D2):** al implementar, el oráculo esbozado tenía T3 "no-empate intacto (==)" — semánticamente FALSO: la convolución SUMA masa a las no-empate (empates resueltos en ET → favorito; el "offset" del #70). Corregido a "no-empate gana masa" y reconfirmado con JP antes de materializar (mismo patrón que `t1c` en D10: bug del oráculo arreglado por el orquestador, logueado).

**Decisiones del review aplicadas:** parte (b) pen_win_prob-por-matchup **DROPEADA** (base-rate 0.54 verificado, EV nulo, evita over-engineering + dep nueva); `c` anclado a ⅓; sin deps nuevas (D3 limpio); `shootouts.csv` no se ingiere.

**Resultado R32:** el modelo formal vuelca **6/7 empates a favorito** (solo Mexico sobrevive, P(empate 120')=0.27) + algunos marcadores de favorito a 2-1. Más agresivo que el análisis aproximado (5 flips) porque la convolución reasigna la masa del ET al favorito. `predictions/r32_full_2026-06-29.txt`. Carga del prode actualizada.

**Backtest KO (confirmatorio, EJECUTADO):** N=48 KO held-out WC2018/14/10 (últimos 16/WC, 10 a penales), rolling-origin, scoring KO completo (marcador 120' + penales de `shootouts.csv`), pareado `c=0` vs `c=⅓`. **EP 4.479 → 5.208, ΔEP=+0.729, SE 0.571, z=+1.28 (NO significativo, N chico — esperado).** La dirección **apoya** el modelo a 120': gana en los KO resueltos (el viejo malgastaba empates), pierde en los ~10 a penales (el viejo cobraba el +5; peor caso Paraguay-Japan 0-0: 17 vs 2); neto positivo. Consistente con el gate teórico (corrección + oráculo). `predictions/backtest_knockouts_2026-06-29.md` + `scripts/backtest_knockouts.py`. **WC2022 virgen.**

## D15 — 2026-07-04: Refresh R16 (re-pin + score R32 parcial + predicción R16) — hash-puro, esperar el lag (D13)

**Contexto:** cerrada la R32 en cancha (28-jun..03-jul), toca R16. Re-pin martj42 `0006be80`→`4a0e4ce6` (commit del 03-jul, 05:06 UTC) con quarantine+diff. Diff **limpio y esperado**: 12 NA→score (R32 del 29-jun..02-jul), +6 filas = fixtures R16 (04-06 jul, NA-NA), +2 shootouts (Germany 1-1 Paraguay→pen Paraguay; Netherlands 1-1 Morocco→pen Morocco), **0 scores históricos alterados**, gate **49499/49499**, suite **122/122**.

**Decisión (operativa, NO numérica nueva):** re-pin + `score_matchday` (R32) + `predict_knockouts --from 2026-07-04` (R16). Reusa engine + optimizer + penales YA oraculizados (D14) → I/O + orquestación, sin oráculo nuevo (D2 aplica a numérica del engine).

**Lag de martj42 (esperar, no overlay — coherente con D13):** el commit del 03-jul trae los R32 hasta el 02-jul; los **3 R32 del 03-jul (Australia-Egypt, Argentina-Cape Verde, Colombia-Ghana)** figuran NA y entran en el commit del 04. **JP-precedente (D13): esperar, repo 100% hash-puro** (no overlay FotMob). Consecuencia: R32 se scorea **12 de 15** (los 3 del 03 quedan pendientes) y R16 se predice **6 de 8 cruces** (los 2 restantes — Switzerland + ganadores del 03 — se definen con el commit del 04). Los 6 cruces predichos cubren los kickoffs inminentes (Canada-Morocco y Paraguay-France son el 04). Impacto en el fit de los 3 faltantes: marginal (favoritos claros, 3 de ~49k con decay).

**Resultado R32 (12/15):** **64 pts, media 5.333, +12.1% vs EV** (`predictions/scored_r32_2026-07-04.md`). Portugal 2-1 Croatia EXACTO (12); 9/12 outcomes. Dolieron los 2 que fueron a penales (predijimos que el favorito resolvía en 120': Germany 1-0 Paraguay→1-1, 2 pts; Netherlands 0-1 Morocco→1-1, 2 pts) y Mexico 0-0→2-0 (el draw-option-value nos jugó en contra, 2 pts). Tracking: F1 −21.1% · F2 +11.8% · F3 +15.0% · R32(parcial) +12.1% (N chico, no concluyente; veredicto serio = Fase 3, ya cerrada).

**Resultado R16 (6/8):** `predictions/r16_full_2026-07-04.txt` (fit 49490, ρ=-0.0875, γ=0.2077, grid@120'). **0 empates** — el modelo a 120' (D14) reasigna la masa de empate al favorito en los 6. Picks: Canada 0-1 **Morocco**, Paraguay 0-1 **France**, **Brazil** 2-1 Norway, Mexico 0-1 **England**, Portugal 0-1 **Spain**, USA 1-2 **Belgium**. Mexico y USA (locales) dados perdedores; Spain (pick Final Soñada) favorita sobre Portugal.

**Nota de scorer (latente, no bloqueante):** `score_matchday.py` llama `match_points` sin `pen_pred/pen_actual` → NO puntúa el +5 de penales. Irrelevante en R32 (nuestro único pick de empate, Mexico, no fue a penales), pero **en R16+ un pick de empate que vaya a penales quedaría mal scoreado**. Como el modelo a 120' vuelca (casi) todo a favorito, el riesgo es bajo; a considerar si algún pick de empate sobrevive. **→ CERRADO en D17 (2026-07-11):** la review R16/QF (M1) lo elevó de nota latente a fix; el scorer ahora cobra el +5 (`penalty_pred_actual` + `actuals_from_csv` con `shootouts.csv`).

**falsified_by:** que el commit del 04 traiga marcadores de R32 (29-jun..02-jul) distintos a los scoreados → re-scorear (el diff verificó 0 históricos alterados → riesgo nulo). Backups `0006be80` en `_quarantine/`.

**ADDENDUM (2026-07-04, 2do re-pin del día — R16 COMPLETO):** apareció el commit martj42 del 04-jul (`25e30198`, 06:32 UTC) antes del 1er kickoff R16. Re-pin `4a0e4ce6`→`25e30198` con quarantine+diff: 3 NA→score (R32 del 03-jul: **Australia 1-1 Egypt** [pen Egypt], **Argentina 3-2 Cape Verde**, **Colombia 1-0 Ghana**), +2 fixtures R16 (**Argentina-Egypt**, **Switzerland-Colombia**), +1 shootout (Egypt), **0 históricos alterados**, gate **49501/49501**, suite **122/122**. **R32 CERRADO 15/15 = 78 pts, 5.200, +4.1% vs EV** (cae del +12.1% parcial: Argentina 3-2 vs EV 7.30 y Australia a penales decepcionaron; el diff verificó que los 12 ya scoreados no cambiaron). **R16 re-predicho COMPLETO 8/8** (fit 49493, los 6 previos idénticos en pick, +Argentina 1-0 Egypt EV 6.45, +Switzerland 0-1 Colombia EV 4.05 [Colombia favorito]). Confirma el enfoque hash-puro de D13: esperar el commit rindió el estado completo sin overlay. Backups `4a0e4ce6` en `_quarantine/`.

## D16 — 2026-07-08: Refresh R16→QF (re-pin + score R16 + predicción QF) — reprogramación de fecha detectada en el diff

**Contexto:** R16 jugada en cancha (04-07 jul). Re-pin martj42 `25e30198`→`273c731` (commit del 07-jul, 23:01 UTC) con quarantine+diff.

**Reprogramación de fecha (no corrupción):** el quarantine marcó 2 "removidas" — Argentina-Egypt y Switzerland-Colombia con fecha **06-jul**. Reaparecen agregadas con fecha **07-jul** y score (Argentina 3-2 Egypt, Switzerland 0-0 Colombia [pen]): martj42 **reprogramó** esos 2 R16 del 06 al 07. Mismo matchup, **0 scores históricos alterados** (score→score = 0). El scorer matchea por (home, away) → el cambio de fecha no rompe el join. Diff neto: 6 NA→score (R16 04-06 jul) + 2 reprogramados = R16 **8/8**; +4 fixtures QF (France-Morocco 09, Spain-Belgium 10, Norway-England 11, Argentina-Switzerland 11); +1 shootout (Switzerland). Gate **49505/49505**, suite **122/122**.

**Resultado R16 (8/8): 50 pts, 6.250, +27.8% vs EV** (`scored_r16_2026-07-08.md`). 7/8 outcomes; exactos Paraguay 0-1 France y Portugal 0-1 Spain (12 c/u). Única caída: **Brazil 2-1→1-2 Norway (0 pts, el batacazo)**. Switzerland-Colombia fue a penales (0-0); predijimos Colombia (no empate) → 2 pts, sin +5 (correcto; la nota del scorer de D15 no aplica sin pick de empate). Tracking KO: R32 +4.1% · R16 +27.8% (N chico, no concluyente).

**QF PREDICHO (4/4):** `predictions/qf_full_2026-07-08.txt` (fit 49501, grid@120'). France 1-0 Morocco, Spain 1-0 Belgium, Argentina 1-0 Switzerland, Norway 1-2 England. Todos favoritos, 0 empates. **Ambos de la Final Soñada vivos y favoritos** (Argentina camp vs Switzerland, Spain subcamp vs Belgium).

**Operativo, NO numérica nueva:** reusa engine + optimizer + penales oraculizados (D14). Sin oráculo nuevo (D2). **falsified_by:** que el commit siguiente traiga R16 distintos → re-scorear (0 históricos alterados → riesgo nulo). Backups `25e30198` en `_quarantine/`.

**Nota §1.6 (agregada 2026-07-11, review R16/QF L1):** `prode_rules §1.6` dice que un partido **reprogramado a fecha posterior** cuenta solo para el **ranking General**, no para la ronda/premios de la fecha original. Los 2 R16 movidos 06→07-jul (Argentina-Egypt, Switzerland-Colombia) *podrían* caer bajo esa regla EN LA PLATAFORMA del prode — si así fuera, el score de la **fecha** R16 sería 43 (no 50), aunque los 7 pts igual cuentan para el General. **Sin impacto en la métrica del proyecto:** §1.6 es explícito *"No optimizer impact"* → los 8 partidos son señal de calibración válida (objetivo #1). Dudoso además que un corrimiento **intra-ronda de 1 día** (R16 sigue abierta, editable por-kickoff) califique como "reprogramación a fecha posterior". Depende de un ASSUMED no observable read-only (¿el prode reprogramó igual que martj42?). **Se anota, no se actúa** — a confirmar con la plataforma si importa el ranking de fecha.

## D17 — 2026-07-11: Cableado del +5 de penales en el scorer (semántica EV↔score = el scorer cobra) — fix M1 de la review R16/QF

**Contexto:** la revisión adversarial R16→QF (`docs/REVIEW_r16_qf_findings_2026-07-08.md`, finding M1, convergencia 4/4) detectó una **asimetría**: el optimizer suma `5·P(empate 120')·0.55` al EV de un pick de empate (`optimizer.py:39-40`), pero el scorer llamaba `match_points` **sin** `pen_pred/pen_actual` (`score_matchday.py`) → nunca acreditaba el +5 realizado, y `actuals_from_csv.py` ni propagaba el ganador de la tanda. Un pick de empate que fuera a penales quedaría (a) sub-scoreado 5 pts y (b) comparado contra un EV que ya incluyó el +5 → doble sesgo en `Pts−EV`/`ratio real/EV`, la métrica de calibración (objetivo #1). INERTE en R16/QF (0 picks de empate) pero vivo en semis/final (el modelo a 120' NO garantiza 0 empates — Mexico sobrevivió en R32).

**Decisión de semántica EV↔score (la parte con juicio): el SCORER COBRA el +5 (opción A), NO se quita del EV (opción B).** Rationale: el +5 son **puntos reales del prode**; el optimizer elige el pick contándolos correctamente (es EV-óptimo bajo el scoring real, `match_points` VERBATIM). Quitar el +5 del EV rompería la optimalidad del optimizer = **rediseño del modelo, prohibido (D9)**. Alinear el scorer con `match_points` COMPLETO (con `pen_pred/pen_actual`) es lo correcto y **no toca el modelo** — el EV ya estaba bien; lo que faltaba era que el scorer cobrara lo mismo que el optimizer optimiza.

**Implementación (I/O + cableado, NO numérica del engine → sin oráculo nuevo, D2):**
- `wcprode/ingest.py`: `load_shootouts()` nueva (carga `shootouts.csv` pineado, hash-verificado; mismo pin que `results.csv`).
- `scripts/actuals_from_csv.py`: emite `pen: <ganador>` en la columna Nota para partidos que fueron a la tanda (lookup `(date,home,away)→winner` desde `shootouts.csv`).
- `scripts/score_matchday.py`: parsea las probs `[H D A]` de la predicción (`PROB_RE`) + el `pen: X` del actuals; `penalty_pred_actual()` (función pura, testeada) deriva `pen_pred` = favorito de la tanda (mayor P a 120') y `pen_actual` = ganador real (H/A); se pasan a `match_points`. Solo un pick de EMPATE accede al +5 (para no-empate devuelve None,None).
- `tests/test_score_matchday.py`: **8 tests de cableado NO-oráculo** (parseo de probs/pen + los 4 caminos de `penalty_pred_actual`). `match_points` en sí sigue oraculizado en `test_match_points`. **Suite 122→130.**

**Higiene incluida (misma review):** `score_matchday` ahora emite **descomposición jackpot** data-driven (M2: "sin los N exactos: X%") y **warning de preds-sin-actual** (M3: no aborta, pero avisa — el loop itera sobre actuals, una predicción reprogramada fuera de la ventana `--to` quedaría fuera en silencio). **Helper de re-pin (L3):** `scripts/diff_repin.py` (nuevo, standalone) clasifica el diff quarantine↔actual — NA→score / reprogramación / altas vs ⚠️ **score→score alterado** (exit 1) — codificando la aserción antes manual "0 históricos alterados". Validado contra `25e30198→273c731` (8 NA→score, 2 reprogramados, 4 altas, 0 alterados).

**Verificación:** R16 re-scoreado (actuals regenerado con `pen: Switzerland`) = **50 pts / +27.8% IDÉNTICO** (retrocompat: los 8 picks son no-empate → el +5 no aplica; Switzerland-Colombia 0-1 sigue 2 pts). Casos sintéticos del camino del +5: empate+acierto de tanda → +5; empate+error → sin +5; no-empate con tanda → sin +5; empate sin tanda → sin +5. Suite **130/130** (0 oráculos tocados; `git diff` de los 5 `*_oracle.py` vacío). Actuals R16 y `scored_r16` regenerados hash-puro.

**Cierra:** M1 + L4 (el gap del +5 estaba solo en el decision-log, no en el backlog de STATUS; ahora arreglado, no diferido). El fix queda **listo y ejercitado ANTES** de que aparezca el primer pick de empate KO (semis/final), como pedía el gate de la review.

**falsified_by:** que el scorer acredite el +5 a un pick NO-empate (violaría prode_rules §1.4 "solo si predecís empate") — cubierto por `test_pen_pick_no_empate_no_accede_al_5`; o que regenerar `scored_r16` cambie el total 50 (violaría retrocompat) — verificado que NO.
