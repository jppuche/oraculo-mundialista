---
doc_type: design-proposal
purpose: Diseño del segundo optimizador (Final Soñada) — tournament Monte Carlo → marginales P(campeón)/P(subcampeón) → mejor par A≠B. Incluye la suite de oráculo a pre-aprobar (regla D2) ANTES de construir.
audience: [agents, humans]
when_to_use:
  - Aprobar el oráculo del Monte Carlo de torneo (gate D2) antes de construir
  - Construir wcprode/tournament.py + scripts/predict_final_sonada.py
status: CONSTRUIDO 2026-06-15 (oráculo 15/15, suite 71/71, datos verificados+pineados). Corrida provisional al pin pre-torneo; definitiva cerca de 06-24. Ver DECISIONS D5
last_verified: 2026-06-15
related_docs:
  - prode_rules.md   # §1.7 + §3.2 (objetivo) + §3.3 (EV-pure)
  - DECISIONS.md     # D2 (oráculo intocable)
---

# Final Soñada — diseño + oráculo (PROPUESTA, gate D2)

**Deadline duro: 2026-06-24** (comienzo de Fecha 3, abre Switzerland–Canada). Obra de cero.
Por D2: **nada se construye hasta que JP apruebe la suite de oráculo de §5.**

## 1. Objetivo (de prode_rules §3.2, no re-litigar)

```
max  10 · P(A = campeón) + 10 · P(B = subcampeón)   sobre pares con A ≠ B
```

- `campeón` = gana la final. `subcampeón` = llega a la final y la pierde.
- Matiz ya documentado: **P(subcampeón) NO la maximiza el favorito** sino el fuerte-pero-no-dominante (el favorito suele ganar la final, no perderla). El par óptimo NO es mecánicamente "top-2 favoritos"; lo deciden las dos marginales.
- El optimizador de asignación es trivial (48×47 pares, fuerza bruta). El trabajo real es producir las marginales `P(campeón)` y `P(subcampeón)` con un **Monte Carlo de torneo**.

## 2. Arquitectura

Nuevo módulo `wcprode/tournament.py`. Script `scripts/predict_final_sonada.py`.

Flujo:
```
re-pin martj42 (Fechas 1-2 jugadas) → re-fit DixonColesEngine (peso decay máximo)
   → TournamentSimulator(prob_provider, bracket_template, played_results, seed)
   → N simulaciones → marginales {team: P(campeón)}, {team: P(subcampeón)}
   → final_sonada_pick(marginales) → par (A=campeón, B=subcampeón), A≠B
```

### 2.1 Inyección del proveedor de probabilidades (clave para el oráculo)
El simulador NO instancia `DixonColesEngine`. Recibe un **proveedor** inyectado:

```
prob_provider(home, away, neutral) -> grid  # matriz P(h,a) normalizada (numpy)
```

- En producción: `lambda h, a, n: eng.predict(h, a, neutral=n).grid`.
- En tests: un **stub determinista** con probabilidades fijas por matchup → permite comparar el MC contra una fórmula cerrada (§5, Tier 2). Sin esta inyección, el core estocástico no es oraculizable.
- **Cache:** precomputar el grid (y su CDF aplanada) por matchup ordenado que pueda ocurrir (≈ a lo sumo 48×48, en la práctica muchos menos). Sampleo por búsqueda en CDF. ~55 partidos/sim × 50k sims ≈ 2.75M samples → segundos en Python puro. Vectorizar después si hace falta.

### 2.2 Qué samplea cada etapa
- **Grupos (restantes):** se samplea el **marcador** (no solo W/D/A) — necesario para goal difference y goals for de los desempates. Partidos ya jugados (Fechas 1-2) entran FIJOS.
- **Knockouts:** se samplea el marcador; si es empate sobre 90/120, se resuelve por **penales** (§4.2). El ganador avanza. No se simula el partido por el 3er puesto (irrelevante para las marginales).

## 3. Reglas de torneo WC2026 — qué hay que verificar (DIRECT_FETCH antes de construir)

**Formato (confianza alta, anunciado por FIFA desde 2023):** 48 equipos, 12 grupos de 4. Avanzan **1° y 2° de cada grupo (24) + los 8 mejores terceros = 32** a una Ronda de 32. Luego R16, QF, SF, Final (single-elimination).

### 3.1 VERIFICADO por DIRECT_FETCH (2026-06-15, orquestador)

**Desempates de fase de grupos — ⚠ CAMBIO 2026: head-to-head va PRIMERO** (yo había asumido GD global primero, como en 2022; me equivoqué — duda incorporada, corregido). Orden oficial:
1. Puntos head-to-head (entre los empatados)
2. Diferencia de gol head-to-head
3. Goles a favor head-to-head  *(se reaplican 1-3 si queda un subconjunto empatado)*
4. Diferencia de gol global
5. Goles a favor global
6. Fair play / conducta
7. Ranking FIFA  *(8. sorteo, fallback final)*

Corroborado por 3 fuentes (resumen de búsqueda + ESPN + Yahoo concuerdan; Yahoo lo titula explícitamente "nuevo para 2026"). Implica que `group_standings` necesita una mini-tabla head-to-head entre empatados ANTES de mirar GD global. El test `test_group_tiebreak` codifica este orden.

**8 mejores terceros:** ranking por puntos → GD global → goles global → fair play (→ ranking FIFA). 8 de 12 avanzan.

**⚠ Asignación de terceros = tabla de 495 combinaciones (Annex C de FIFA).** C(12,8)=495 escenarios: para cada combinación de qué 8 grupos aportan tercero clasificado, una fila dice qué tercero (por letra de grupo) ocupa qué slot del R32 (notación "3E", "3J", etc.). NO es un algoritmo simple, es lookup. La tabla completa está en la página de Wikipedia del knockout stage. **Necesita ingesta como dato pineado** (ver §6).

**Bracket R32 (matches 73-88) + sedes — VERIFICADO (Wikipedia):**

| M | Local-slot | Visitante-slot | Sede | País |
|---|---|---|---|---|
| 73 | 2°A | 2°B | SoFi, Inglewood | USA |
| 74 | 1°E | 3° (A/B/C/D/F) | Gillette, Foxborough | USA |
| 75 | 1°F | 2°C | Estadio BBVA, Guadalupe | **MEX** |
| 76 | 1°C | 2°F | NRG, Houston | USA |
| 77 | 1°I | 3° (C/D/F/G/H) | MetLife, East Rutherford | USA |
| 78 | 2°E | 2°I | AT&T, Arlington | USA |
| 79 | 1°A | 3° (C/E/F/H/I) | Estadio Azteca, CDMX | **MEX** |
| 80 | 1°L | 3° (E/H/I/J/K) | Mercedes-Benz, Atlanta | USA |
| 81 | 1°D | 3° (B/E/F/I/J) | Levi's, Santa Clara | USA |
| 82 | 1°G | 3° (A/E/H/I/J) | Lumen, Seattle | USA |
| 83 | 2°K | 2°L | BMO Field, Toronto | **CAN** |
| 84 | 1°H | 2°J | SoFi, Inglewood | USA |
| 85 | 1°B | 3° (E/F/G/I/J) | BC Place, Vancouver | **CAN** |
| 86 | 1°J | 2°H | Hard Rock, Miami Gardens | USA |
| 87 | 1°K | 3° (D/E/I/J/L) | Arrowhead, Kansas City | USA |
| 88 | 2°D | 2°G | AT&T, Arlington | USA |

**Flujo (R16):** (73-75), (74-77), (76-78), (79-80), (83-84), (81-82), (86-88), (85-87). R16 en sedes mayormente USA + CDMX (**MEX**) y Vancouver (**CAN**). **QF/SF/Final: todas USA** (Foxborough/Inglewood/Miami/KC; Arlington/Atlanta; Final MetLife 07-19).

**Mapa sede→país para el tilt anfitrión (§4.1):** las únicas sedes NO-USA en knockouts son MEX (Guadalupe M75, CDMX M79 + R16) y CAN (Toronto M83, Vancouver M85 + R16). De QF en adelante todo es USA. Implicación: MEX/CAN solo pueden ser local en R32/R16; USA puede ser local en cualquier ronda donde juegue (casi todas). El tilt se aplica por slot: la sede del slot es fija, el equipo es local si es el anfitrión de ese país.

**Provenance:** Wikipedia `2026_FIFA_World_Cup_knockout_stage` (bracket+sedes), ESPN + Yahoo + resumen de búsqueda (desempates). FIFA oficial intentada (render JS vacío) → corroboración por triangulación de secundarias reputadas. Confianza: ALTA en formato/desempates/bracket/sedes; la tabla de 495 filas requiere ingesta verificada. Contenido tratado como `<untrusted-content>`, sin instrucciones embebidas detectadas.

**Membresía de grupos:** derivable de los fixtures (`ingest.wc2026_group_fixtures`); confirmar columna `group` o derivar por co-ocurrencia. Detalle de build.

## 4. Decisiones de modelado (defaults propuestos + knobs)

### 4.1 Ventaja de localía en knockouts — DECIDIDO: tilt anfitrión (JP 2026-06-15)
Regla: en un knockout se aplica gamma a un anfitrión (USA/MEX/CAN) **si y solo si la sede del partido está en su país**. La sede por slot del bracket sale del calendario oficial WC2026 (DIRECT_FETCH, §3). A lo sumo un lado es local (las sedes son de un solo país); si ninguno es anfitrión-en-casa, neutral. Maneja bien los casos límite (Canada en Kansas City NO es local; USA en la final de MetLife SÍ). En grupos se respeta el flag `neutral` de martj42 (como ya hace `predict_matchday`). **Fallback** si el mapeo sede→país resultara inviable de verificar: documentar una aproximación explícita (p.ej. anfitrión local hasta cierta ronda) y declararla en el reporte.

### 4.2 Resolución de penales en knockouts — DECIDIDO: 0.55 al favorito (JP 2026-06-15)
Cuando un knockout termina empatado sobre 90/120, el ganador del shootout se sortea con **P=0.55 al favorito pre-partido** (el de mayor P(victoria) en 90/120 según el grid) y 0.45 al otro. Consistente con `DEFAULT_PEN_WIN_PROB` del optimizador per-match. Se implementa como función pura `resolve_penalties(fav, dog, rng, p=0.55)` (testeable, ver Tier 1 #6b). Knob futuro: modelo calibrado con `shootouts.csv` (componente nuevo → su propio oráculo).

### 4.3 Número de simulaciones
Default propuesto: **N=50.000**, seed fijo. Reportar el **error estándar de Monte Carlo** de cada marginal del top (SE ≈ sqrt(p(1-p)/N)). Las marginales que importan (top ~6) convergen rápido; las de cola son ruidosas y no afectan el pick. El reporte declara el SE (no se esconde el ruido).

### 4.4 Condicionamiento en resultados parciales
El simulador acepta `played_results` (Fechas 1-2 al momento del deadline) y los fija; simula solo lo no jugado. El motor se re-fitea incluyendo esos partidos (peso decay máximo) antes de correr. Construir el simulador para aceptar resultados parciales desde el día 1, no solo priors pre-torneo.

## 5. SUITE DE ORÁCULO (esto es lo que JP aprueba — gate D2)

Vive en `tests/test_tournament_oracle.py`. Una vez aprobada, **intocable** (D2): los builders no la editan; solo el orquestador, logueado en DECISIONS. `match_points` y el engine ya tienen sus oráculos; esto cubre el componente NUEVO.

### Tier 1 — Sub-componentes deterministas (aserción exacta, sin RNG)
1. **`test_group_table_basic`** — grupo con 6 resultados fijos → (puntos, GD, GF) y ranking exactos.
2. **`test_group_tiebreak`** — caso de empate en puntos resuelto por GD y luego GF (orden VERIFICADO en §3.1) → orden exacto.
3. **`test_best_thirds_selection`** — 12 terceros con records fijos → los 8 elegidos coinciden con un set calculado a mano, incluida la frontera 8°-vs-9°.
4. **`test_bracket_slotting`** — plantilla verificada + set clasificado fijo → emparejamientos R32 exactos.
5. **`test_pick_distinct`** — marginales donde argmax(campeón) ≠ argmax(subcampeón) → elige cada uno.
6. **`test_pick_conflict`** — marginales donde argmax(campeón) == argmax(subcampeón) == T → devuelve el de mayor total entre {T-campeón + 2°-subcampeón} y {2°-campeón + T-subcampeón}. Calculado a mano.
6b. **`test_penalty_resolution`** — `resolve_penalties(fav, dog, rng, p=0.55)`: con valores de rng forzados a ambos lados del umbral 0.55 devuelve el pick determinista correcto (fija el knob 4.2). Aislado, exacto.

### Tier 2 — Core estocástico vs forma cerrada (oráculo de oro)
7. **`test_mini_bracket_analytic`** — bracket de 4 equipos (SF: A-B, C-D; final entre ganadores), stub determinista con P(victoria) fijas por par, SIN empates. P(A campeón) y P(A subcampeón) derivadas a mano:
   - `P(A campeón) = P(A>B) · [P(C>D)·P(A>C) + P(D>C)·P(A>D)]`
   - `P(A subcampeón) = P(A>B) · [P(C>D)·P(C>A) + P(D>C)·P(D>A)]`
   El MC (seed fijo, N grande p.ej. 200k) debe coincidir dentro de tolerancia (`|MC − analítico| < 4·SE`).
8. **`test_degenerate_dominant`** — stub donde el equipo X gana TODO con P=1 → `P(X campeón) == 1.0` exacto (plomería end-to-end a través del bracket real, determinista).

### Tier 3 — Invariantes de conteo (exactas en cualquier corrida)
9. **`test_champion_marginals_sum_to_one`** — Σ P(campeón) == 1.0 y Σ P(subcampeón) == 1.0 (cada sim tiene exactamente un campeón y un subcampeón).
10. **`test_reach_final_decomposition`** — para todo equipo: `P(campeón) + P(subcampeón) == P(llega a la final)` (identidad de conteo).
11. **`test_reproducible_seed`** — mismo seed → marginales idénticas.

### Tier 4 — Condicionamiento (exacto/estructural)
12. **`test_fixed_group_no_sim`** — grupo completamente jugado → standings deterministas, independientes del RNG.
13. **`test_eliminated_team_zero`** — equipo matemáticamente eliminado en grupos → `P(campeón) == 0` y `P(subcampeón) == 0`.

**Falsado por:** cualquier aserción de Tier 1/3/4 que no se reproduzca exacto, o Tier 2 fuera de tolerancia. El oráculo de oro es #7 (forma cerrada para el core estocástico, igual que ρ̂ exacto fue el del engine).

## 6. Plan de construcción

1. ✅ **DIRECT_FETCH** del bracket WC2026 — hecho (§3.1).
2. **Ingerir la tabla de 495 combinaciones** (Annex C) como dato pineado: fuente primaria FIFA regs (PDF Annex C) si es parseable, con Wikipedia (pin por `oldid` de revisión, análogo al SHA-pin de martj42) como respaldo; **cross-validar ambas** en ≥3 escenarios spot-check. Guardar CSV/JSON en `data/raw/`, quarantine+diff, provenance (data_security P2). NO pickle. Validación: checksum de cantidad de filas (=495) + spot-check.
3. Escribir `tests/test_tournament_oracle.py` (la suite aprobada de §5). `test_bracket_slotting` usa UN escenario verificado (una fila), no las 495.
4. Delegar a Sonnet la construcción de `wcprode/tournament.py` contra el oráculo (builders construyen, orquestador valida).
5. `scripts/predict_final_sonada.py` → marginales + par óptimo + SE, versionado en `predictions/`.
6. Loguear en DECISIONS.md (componente numérico nuevo + su oráculo + nueva fuente de datos: tabla Annex C).

## 7. Decisiones (cerradas 2026-06-15)

- **Oráculo §5** (gate D2): **APROBADO por JP tal cual** + se agrega `test_penalty_resolution` (6b) por el knob 4.2.
- **Knob 4.1** (localía en knockouts): **tilt anfitrión** (regla venue-country, §4.1).
- **Knob 4.2** (penales): **0.55 al favorito** (§4.2).
- **N=50k** y reporte con SE: aprobado.
