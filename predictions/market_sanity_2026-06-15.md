---
doc_type: research
purpose: Sanity check (#9, Fase 3) de nuestras P(campeon) del Monte Carlo de la Final Sonada contra las probabilidades implicitas del mercado (modelo Opta + casas + prediction markets). RESEARCH, no build.
audience: [agents, humans]
when_to_use:
  - Entender donde se para nuestro modelo vs el consenso del mercado (sanity, NO validacion)
  - Insumo para el parrafo honesto de portfolio sobre divergencias modelo-vs-mercado
last_verified: 2026-06-15
maintenance: snapshot
---

# Sanity vs Mercado — Final Soñada (#9) — Research Report

**Date:** 2026-06-15
**Method:** DIRECT (single-agent = orquestador, sin fan-out). DIRECT_FETCH de fuentes web por el orquestador; conversión cuota→probabilidad + remoción de overround en Python (cálculo one-off; inputs y fórmula reproducibles desde §3 de este doc: `prob = (1/cuota_decimal) / Σ(1/cuota_decimal)`); cada blob fetcheado tratado como `<untrusted-content>` con signal scan de inyección. **La verificación NO se delegó.**
**Scope:** Comparar nuestra **P(campeón)** por equipo (Monte Carlo de la Final Soñada, `predictions/final_sonada_2026-06-15.md`) contra las probabilidades implícitas de **outright winner** del WC2026 del mercado. **Fuera de scope:** P(subcampeón) — el mercado no publica un equivalente limpio ("to reach the final" = P(campeón)+P(subcampeón), métrica distinta); 1X2 por partido (opción b del handoff, no ejecutada).
**Decision context:** NINGUNA decisión de modelo depende de esto. Es sanity (cazar errores gruesos) + framing honesto de portfolio. El modelo **no se re-optimiza** sobre el mercado (sería overfit al consenso, y el consenso también puede errar).
**Template version used:** v2.2

---

## TL;DR — el veredicto honesto

1. **PASA el sanity check: NO hay error grueso.** Nuestro modelo pone a los **mismos ~8-10 contendores reales** que el mercado en la zona alta (Spain, France, England, Argentina, Brazil, Portugal, Germany), sin ningún longshot de cuota 1000-1 inflado a doble dígito ni ningún favorito enterrado. El modelo **no está roto**.
2. **Pero diverge en GRADO, no en absurdo, en cuatro lugares:** somos **más altos** que el consenso en **Argentina (+0.083 vs casas)** y **Morocco (+0.044)**; **más bajos** en **France (−0.078)**, **Portugal (−0.044)** y **England (−0.028)**. Traducido: nuestro modelo es más "Argentina + Morocco" y menos "establishment europeo" que el mercado.
3. **La divergencia es robusta como observación porque el mercado-modelo (Opta) y las casas COINCIDEN entre sí** y ambos discrepan de nosotros en Argentina/Morocco. No es "nosotros vs una fuente ruidosa": es "nosotros vs el consenso de dos tipos de mercado independientes".
4. **Y aun así NO prueba nada.** Convergencia donde coincidimos (Spain ≈ 0.14) no nos valida; divergencia donde nos separamos no nos refuta. Sin el torneo jugado, **no se decide quién acierta**. Ver §0.

---

## 0. El caveat que gobierna todo: "convergence ≠ evidence"

Esto es el corazón del ejercicio, no una nota al pie:

- **Convergencia NO valida.** Que nuestra Spain (0.141) caiga casi sobre la del mercado (BetMGM norm. 0.143, Opta 0.161) **no prueba que el modelo sea bueno** — prueba que comparte los priors del consenso. El consenso también puede estar equivocado de la misma forma (ambos pueden sobre/subvaluar al mismo equipo). Dos relojes rotos en hora no dan la hora.
- **Divergencia NO refuta.** Que sobrevaluemos a Argentina vs el mercado puede ser (a) el modelo leyendo forma reciente que el prestigio/regresión del mercado descuenta, o (b) un sesgo nuestro. **No se decide acá.** Se *anota*.
- **El uso legítimo, y único, de este documento:** (1) detectar **errores gruesos** (un underdog al 25% sería un bug — no lo hay) y (2) enmarcar honestamente **dónde nos paramos vs el mercado**. Nada más. Esto NO es una métrica de calidad del modelo; la métrica sigue siendo expected points held-out (Fase 3, #8/#10), out-of-sample, con WC2022 virgen.

---

## 1. Provenance & Confidence Taxonomy

**Provenance** (cómo llegó el dato): `DIRECT_FETCH` (orquestador fetcheó la URL y leyó el contenido) · `SEARCH_INDEX` (visible en snippet del buscador, página no fetcheada) · `AGGREGATOR` · `MODEL_KNOWLEDGE` · `INFERRED`.
**Confidence** (independiente de provenance): `HIGH` (fuente primaria + corroboración independiente) · `MEDIUM` (fuente razonable, no contradicha) · `LOW` (fuente única débil) · `CONTESTED`.
**Verdict** (solo en Verification Log): `CONFIRMED` / `DENIED` / `PARTIAL` / `UNVERIFIABLE`.

---

## 2. Qué comparamos (y la trampa temporal que hay que declarar)

- **Nuestro lado:** P(campeón) del Monte Carlo de bracket (50.000 sims, fit a 49.306 partidos, ξ=0.0018, ρ=−0.0662, γ=0.2108). Condicionamiento **PROVISIONAL al pin pre-torneo** (grupos sin jugar). Fuente: `predictions/final_sonada_2026-06-15.md`.
- **Mercado-modelo (la lente más limpia):** Opta supercomputer, probabilidades publicadas (sin overround), 25.000 sims, **Jun 1 2026, pre-torneo**.
- **Mercado-casas:** cuotas de outright winner. Canónica = **BetMGM** (lista completa de 48 equipos, vía Yahoo, Jun 15) para poder remover el overround con base principiada. Corroboran: DraftKings (vía ESPN), FanDuel (vía FOX), US books (vía Goal.com).
- **Prediction markets (color):** Kalshi/Polymarket, vía snippet (no fetcheado, 429).

### ⚠ Duda incorporada — desfase temporal (declarado, no escondido)

Hay un mismatch de timing que condiciona la lectura:

| Fuente | Fecha | ¿Ve la Fecha 1? |
|---|---|---|
| **Nuestro fit** | pin pre-torneo | **NO** |
| **Opta** | Jun 1 | **NO** |
| **Casas (BetMGM/DK/FanDuel)** | Jun 15 | **SÍ** (parcial) |

→ La comparación **manzanas-con-manzanas es nuestra-vs-Opta** (ambos pre-torneo). Las casas del Jun 15 ya movieron con resultados: confirmado textualmente — *"Spain dropped from +450 to +500 following a shocking 0-0 draw against Cape Verde"* (FanDuel), y France pasó a favorita sola. Por eso, donde nuestra divergencia con las casas coincide con la divergencia con Opta (Argentina, Morocco, France), **no es artefacto temporal**: el modelo pre-torneo de Opta también discrepa de nosotros.

---

## 3. La comparación (tabla principal)

P(campeón). "BetMGM norm." = cuota convertida a prob cruda (1/decimal) y normalizada removiendo el overround. Δ = nuestra − BetMGM norm.

| Equipo | **Nuestra P** | Opta (Jun 1) | BetMGM norm. (Jun 15) | **Δ (ns − BetMGM)** | Lectura |
|---|---|---|---|---|---|
| Argentina | **0.162** | 0.104 | 0.079 | **+0.083** | 🔴 nuestra mayor sobrevaluación; somos los únicos que la hacen favorita |
| Spain | 0.141 | 0.161 | 0.143 | −0.002 | 🟢 convergencia casi perfecta con casas |
| England | 0.070 | 0.112 | 0.098 | −0.028 | 🟡 subvaluamos |
| France | 0.065 | 0.130 | 0.143 | **−0.078** | 🔴 nuestra mayor subvaluación (y Opta pre-torneo ya la duplica) |
| Morocco | 0.063 | 0.019 | 0.019 | **+0.044** | 🔴 divergencia estructural: la ponemos ~3.3× el consenso |
| Brazil | 0.060 | 0.066 | 0.079 | −0.019 | 🟢 en línea |
| Portugal | 0.054 | 0.070 | 0.098 | −0.044 | 🟡 subvaluamos |
| Germany | 0.042 | 0.051 | 0.052 | −0.010 | 🟢 en línea |
| Japan | 0.038 | ~0.010 | 0.015 | +0.023 | 🟡 sobrevaluamos cola media |
| Colombia | 0.037 | 0.021 | 0.019 | +0.018 | 🟡 sobrevaluamos cola media |
| Netherlands | 0.034 | 0.036 | 0.041 | −0.007 | 🟢 en línea |
| Norway | 0.029 | 0.035 | 0.023 | +0.006 | 🟢 en línea |

**Overround declarado (calidad de la fuente de casas):** BetMGM Σ(1/cuota) sobre los 48 equipos = **1.2736 → overround 27.4%**. Es decir, las probabilidades crudas sin normalizar **sobreestiman ~27%** en promedio (factor de encogimiento 1/1.2736 = 0.785). Margen alto pero normal para un mercado outright de 48 corredores. Opta, al ser modelo, no tiene overround (suma ~100% de fábrica). Por eso la columna de casas va **normalizada**, no cruda.

**Coincidencias de escala que vale la pena notar (con el caveat §0 puesto):**
- El favorito vale ~16% en los tres: **nuestra Argentina 0.162 ≈ Opta Spain 0.161 ≈ Kalshi Spain 0.163**. Compartimos la *escala* del techo; discrepamos en la *identidad* del favorito.
- Tras remover overround, **BetMGM Morocco = 0.019 = Opta Morocco 0.019** (clavado). El consenso sobre Morocco es firme entre casas y modelo; el que se sale de la fila somos nosotros.

---

## 4. Lectura de las divergencias (se anota, no se decide)

**🔴 Argentina (somos +0.06 a +0.08 sobre el consenso).** Nuestro DC la hace favorita; Opta y las casas la ponen 5°-6°, detrás de Spain/France/England y a la par de Brazil. Hipótesis no resueltas: (a) el time-decay pondera resultados internacionales recientes donde Argentina (campeón defensor) ha sido dominante, y el mercado descuenta eso por edad del plantel/regresión a la media; (b) la ruta del bracket le es favorable en nuestras sims. **Cuál pesa más, no se decide acá.**

**🔴 Morocco (somos ~3.3× el consenso, 0.063 vs 0.019).** Es nuestra divergencia más estructural. **Ya investigada en D7:** el backtest multi-copa concluyó que "Morocco 5°" **no es un artefacto de ξ** (ξ=0.0018 está en un plateau plano; subirlo no lo corrige). Este sanity check **agrega** una capa independiente: el mercado *tampoco* comparte nuestra visión de Morocco. Lectura combinada: nuestra valuación alta de Morocco es (1) no atribuible al knob de calibración (D7) y (2) no compartida por el consenso → es una característica genuina de nuestros ratings DC desde resultados recientes (semifinalista 2022 + forma), que el mercado descuenta por prestigio. **Quién acierta: indecidible sin el torneo.**

**🔴 France (somos −0.078, la mayor subvaluación).** El mercado la tiene co-favorita/favorita; nosotros 4°. **Hay que separar dos capas:** (1) France-como-#1-sola en las casas del Jun 15 es **en parte** reacción temporal (Spain tropezó con Cape Verde); pero (2) Opta pre-torneo —mismo timing que nosotros— **ya tenía France 0.130, el doble que nuestro 0.065**. Conclusión honesta: subvaluamos a France vs el consenso de forma **independiente del timing**.

**🟡 Cola media (Japan +0.023, Colombia +0.018).** Repartimos un poco más de masa hacia equipos medios: nuestra suma top-12 = 0.795 vs Opta 0.829 → tenemos **cola más gorda** (0.205 fuera del top-12 vs ~0.171 de Opta). Coherente con un modelo algo menos concentrado en la elite que el consenso.

---

## 5. Findings — schema de claims auditable

Cada cuota/probabilidad fetcheada es una claim. (Nuestras P son output interno del Monte Carlo, no claim de research — son el baseline contra el que comparamos.)

### Mercado-modelo (Opta)

| # | Claim | Provenance | Confidence | Source | Accessed | Falsified by |
|---|-------|------------|------------|--------|----------|--------------|
| 1 | Opta P(campeón): Spain 16.1%, France 13.0%, England 11.2%, Argentina 10.4%, Portugal 7.0%, Brazil 6.6%, Germany 5.1% | DIRECT_FETCH | HIGH | [Opta — Who Will Win the 2026 World Cup](https://theanalyst.com/articles/who-will-win-2026-fifa-world-cup-predictions-opta-supercomputer) | 2026-06-15 | Un re-fetch del artículo mostrando otros % o fecha distinta a Jun 1 |
| 2 | Opta P(campeón) cola: Netherlands 3.6%, Norway 3.5%, Belgium 2.4%, Colombia 2.1%, Morocco 1.9%, Japan ~1.0% | DIRECT_FETCH | MEDIUM | [Opta](https://theanalyst.com/articles/who-will-win-2026-fifa-world-cup-predictions-opta-supercomputer) | 2026-06-15 | El fetch desordenó parte de la cola (Croatia/Ecuador fuera de orden); los top-7 (#1) son los confiables |
| 3 | Corrida Opta es pre-torneo (Jun 1 2026, "before the tournament kicks off on 11 June"), 25.000 sims | DIRECT_FETCH | HIGH | [Opta](https://theanalyst.com/articles/who-will-win-2026-fifa-world-cup-predictions-opta-supercomputer) | 2026-06-15 | Fecha distinta en el artículo |

### Mercado-casas (cuotas → prob normalizada)

| # | Claim | Provenance | Confidence | Source | Accessed | Falsified by |
|---|-------|------------|------------|--------|----------|--------------|
| 4 | BetMGM, lista completa 48 equipos. Top: Spain/France +450, England/Portugal +700, Argentina/Brazil +900, Germany 14-1, Netherlands 18-1, Morocco 40-1. Overround 27.4% | DIRECT_FETCH | HIGH | [Yahoo — odds for all 48 teams (BetMGM)](https://sports.yahoo.com/soccer/betting/article/2026-world-cup-betting-odds-for-all-48-teams-to-win-the-title-145427136.html) | 2026-06-15 | Re-fetch con cuotas materialmente distintas, o falla la suma 1.2736 |
| 5 | DraftKings: Spain/France +450, England +750, Portugal +800, Argentina 10-1, Brazil 11-1, Germany 14-1, Morocco 35-1 | DIRECT_FETCH | HIGH | [ESPN — championship odds (DraftKings)](https://www.espn.com/espn/betting/story/_/id/48386952/espn-soccer-futbol-world-cup-betting-odds-championship-groups) | 2026-06-15 | Re-fetch con cuotas distintas |
| 6 | FanDuel: France +430, Spain +500, England +700, Portugal +750, Argentina/Brazil +1000, Germany +1300, Morocco +4000. "Spain dropped to +500 after Cape Verde draw" | DIRECT_FETCH | HIGH | [FOX — champion odds (FanDuel)](https://www.foxsports.com/stories/soccer/world-cup-2026-champion-odds) | 2026-06-15 | Re-fetch con cuotas distintas |
| 7 | US books (Goal.com), Jun 11: Spain/France +450, England/Portugal +700, Argentina/Brazil +900, Norway +3300, Colombia +3900, Japan +4900 | DIRECT_FETCH | MEDIUM | [Goal.com — WC winner odds](https://www.goal.com/en-us/betting/world-cup/world-cup-winner-odds/A%3Ablt4b7e4ceb80cb6863) | 2026-06-15 | Casa no especificada; lista parcial (top-10) |

### Prediction markets + agregadores (color, menor provenance)

| # | Claim | Provenance | Confidence | Source | Accessed | Falsified by |
|---|-------|------------|------------|--------|----------|--------------|
| 8 | Kalshi/Polymarket: Spain 16.3% (+514), France 16.1% (+521), Portugal 10.9% (+818) | SEARCH_INDEX | MEDIUM | [DeFiRate — WC odds tracker](https://defirate.com/prediction-markets/world-cup-odds/) (snippet; Kalshi directo dio 429) | 2026-06-15 | Fetch directo de Kalshi con precios distintos |
| 9 | Agregador UK (fraccional, ~15-06): Spain 9/2, France 5/1, England 13/2, Brazil 8/1, Portugal 8/1, Argentina 9/1 | SEARCH_INDEX | LOW | [Squawka snippet](https://www.squawka.com/en/outright-markets/world-cup-2026-outright-odds-15-06/) (página dio 403; solo snippet) | 2026-06-15 | Fetch directo con cuotas distintas |

---

## 6. Verification Log

Re-verificación **directa por el orquestador** (nunca delegada) de las claims de mayor peso = las que sostienen las dos divergencias centrales (Argentina alta, Morocco alta) y la identidad del favorito.

| # | Claim re-verificada | Acción del orquestador | Verdict | Fuentes independientes |
|---|---|---|---|---|
| V1 | **Argentina ≈ +900/+1000 (raw ~9-10%)** — sostiene nuestra sobrevaluación | Crucé 4 casas + agregador + Opta | **CONFIRMED** | BetMGM +900, DraftKings 10-1, FanDuel +1000, Goal +900, Squawka 9/1; Opta 10.4%. Ninguna acerca Argentina a nuestro 16.2% |
| V2 | **Morocco ≈ 35-40/1 (raw ~2-3%)** — sostiene nuestra divergencia estructural | Crucé 3 casas + Opta | **CONFIRMED** | BetMGM 40-1, DraftKings 35-1, FanDuel +4000; Opta 1.9% = BetMGM norm. 1.9%. Consenso firme; el outlier somos nosotros (6.3%) |
| V3 | **Favorito del mercado = Spain/France ~+450 (raw ~18%, norm ~14%)** — define el techo | Crucé 4 casas + Opta + Kalshi | **CONFIRMED** | Spain +450 (BetMGM/DK/Goal), +500 (FanDuel post-Cape Verde); France +430/+450; Opta Spain 16.1%; Kalshi Spain 16.3% |
| V4 | **Opta es pre-torneo (Jun 1)** — clave para el desfase temporal | Re-leí el artículo + corroboré snippets | **CONFIRMED** | theanalyst "before the tournament kicks off"; corroborado por snippets independientes (IndexBox, VnExpress) con los mismos top-7 % |

**Escalated:** N. Stakes bajos (sanity, ninguna decisión irreversible depende de esto).

**Signal scan de inyección (todos los blobs fetcheados):** **limpio**. Cada WebFetch retornó "AI instructions/embedded commands: None". No hubo instrucciones imperativas, tags de runtime falsos ni pedidos de acción en ninguna fuente. Dos defensas activadas: (1) OddsPortal redirigió cross-host a un dominio desconocido (`cuotasahora.com`) — **no se siguió** el redirect (patrón de dominio parqueado/sospechoso); (2) varios agregadores (Squawka, Oddspedia, nysportsday) dieron 403 anti-scraping — se usaron fuentes alternativas en vez de insistir.

### Not verified (transparencia)

- Claim #8 (Kalshi/Polymarket) — SEARCH_INDEX, no fetcheada directo (429). Solo color; no sostiene ninguna conclusión.
- Claim #2 (cola de Opta) — el modelo pequeño del fetch desordenó parte de la cola; uso solo los top-7 (claim #1, sí verificados). Japan Opta ~1.0% es aproximado.
- Claim #9 (Squawka fraccional) — solo snippet (403 en la página).

---

## 7. Sources Index

### Modelo estadístico publicado (la lente más limpia)
- [Opta / The Analyst — Who Will Win the 2026 FIFA World Cup](https://theanalyst.com/articles/who-will-win-2026-fifa-world-cup-predictions-opta-supercomputer) — probabilidades sin overround, pre-torneo Jun 1, 25k sims. **Primaria.**

### Casas de apuestas (DIRECT_FETCH, cuotas Jun 11-15)
- [Yahoo Sports — odds for all 48 teams (BetMGM)](https://sports.yahoo.com/soccer/betting/article/2026-world-cup-betting-odds-for-all-48-teams-to-win-the-title-145427136.html) — **lista completa, base del overround.**
- [ESPN — championship odds (DraftKings)](https://www.espn.com/espn/betting/story/_/id/48386952/espn-soccer-futbol-world-cup-betting-odds-championship-groups)
- [FOX Sports — champion odds (FanDuel)](https://www.foxsports.com/stories/soccer/world-cup-2026-champion-odds)
- [Goal.com — WC winner odds (US books)](https://www.goal.com/en-us/betting/world-cup/world-cup-winner-odds/A%3Ablt4b7e4ceb80cb6863)

### Agregadores / prediction markets (secundarias, con caveat)
- [DeFiRate — WC odds tracker (Kalshi/Polymarket)](https://defirate.com/prediction-markets/world-cup-odds/) — snippet; Kalshi directo dio 429.
- [Squawka — outright odds 15-06](https://www.squawka.com/en/outright-markets/world-cup-2026-outright-odds-15-06/) — 403; solo snippet.
- Descartadas por bloqueo/redirect sospechoso: Oddspedia (403), nysportsday (403), OddsPortal (redirect cross-host a dominio desconocido).

---

## 8. Síntesis honesta (para portfolio)

> **Dónde nos paramos vs el mercado.** Nuestro modelo Dixon-Coles in-house comparte el mapa del consenso —los mismos ~8-10 contendores reales, sin absurdos— lo que descarta un bug grueso en el pipeline campeón. Difiere del mercado en cuatro lugares medibles: sobrevalúa a **Argentina** (la hace favorita; el mercado la pone 5°-6°) y a **Morocco** (~3.3× el consenso), y subvalúa a **France**, **Portugal** e **England**. La divergencia es robusta como *observación* porque dos mercados independientes —el modelo Opta y las casas— coinciden entre sí y discrepan de nosotros. **Pero coincidir no nos valida y divergir no nos refuta:** sin el torneo jugado, esto no decide quién acierta. Es sanity, no veredicto. La pregunta "¿el modelo es bueno?" la responde la calibración out-of-sample (expected points held-out, Fase 3), no el espejo del mercado.

**Conexión con decisiones vigentes:**
- La divergencia en **Morocco** es consistente con D7 (ξ=0.0018 está bien; Morocco-alto no es artefacto de calibración) y le **agrega** que el mercado tampoco la comparte. No reabre D7.
- Nada acá toca el modelo. **Anti-drift respetado:** es diagnóstico externo, no objetivo de optimización. El modelo NO se ajusta para parecerse al mercado.
- **Guard-rail formal (D9, 2026-06-15):** este documento —y cualquier otro diagnóstico— es **NO-VINCULANTE para el diseño**. El modelo se construye con metodología propia (expected points held-out + oráculos + WC2022 virgen), *"a nuestra manera, lo mejor que podamos"*. Las divergencias de §4 (Argentina/Morocco/France) **se anotan, no se actúan**: ninguna corrección de diseño sale de acá. El análisis comparativo serio es **POST-torneo** (postmortem corto post-grupos ~28 jun, profundo post-final ~19 jul; ambos N chico/N=1, no-vinculantes). Ver `docs/DECISIONS.md` D9 + STATUS pendiente #11.

## 9. Lo que NO sabemos (y este doc no puede saber)

- **Quién acierta en Argentina/Morocco/France.** Indecidible sin resultados. Lo sabremos —parcialmente— al final del torneo, y aun así N=1.
- **Si las casas del Jun 15 ya movieron tanto que la comparación se ensucia.** Mitigado usando Opta (pre-torneo) como lente principal, pero las casas tienen desfase.
- **El overround real por equipo.** Asumimos margen proporcional (normalización plana 1/Σ). Las casas cargan más vig en los longshots; la normalización plana puede sobreestimar levemente la prob de los favoritos. Para sanity, irrelevante.

---

*convergence ≠ evidence — el modelo no está roto, comparte el mapa del consenso, y diverge donde diverge sin que eso lo confirme ni lo condene. La validación vive en Fase 3 (expected points held-out), no acá.*
