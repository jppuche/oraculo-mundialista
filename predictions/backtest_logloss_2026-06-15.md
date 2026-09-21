# Backtest multi-copa — log-loss sobre la grilla P(h,a) (Fase 3, #10)

**Fecha:** 2026-06-15 · **Harness:** `wcprode/backtest.py` (`paired_logloss_comparison`, sobre `rolling_origin_logloss`) ·
**Comando:** `.venv/Scripts/python.exe scripts/backtest_logloss.py` (default ξ=0.0018, ventana 8a, bootstrap 2000, seed 20260615).
**Validación del orquestador:** (1) recálculo del valor `−log P[actual]` desde `engine.predict` SIN `log_loss_grid` → **diferencia 0.00e+00** sobre 64 partidos; (2) d_ll agregado por vía independiente (merge + bootstrap seed 777) → reprodujo todas las celdas; (3) **held-out idéntico al de #8/EP** (mismas 192 identidades de partido). Suite **96/96** (84 previos + 12 de regresión).

Pregunta: ¿la corrección ρ mejora la **calibración de la matriz P(h,a) completa** — lo que el EP (#8) no puede ver, porque solo mira el pick óptimo? Métrica: log-loss held-out = −log P[marcador real]. **DIAGNÓSTICO, no la métrica de decisión: el modelo NO se re-optimiza sobre log-loss** (intención EP-pure del proyecto).

## Por qué log-loss ve lo que EP no ve

EP solo evalúa el **pick** (el argmax EV); es ciego a cómo el modelo reparte la probabilidad en el resto de la grilla. El prode paga el `12` por el marcador exacto, así que la calibración de toda la matriz importa. Log-loss la mide. Y es **continuo** (no escalonado como los puntos), así que su SE pareado es **~25× más fino** que el de EP (0.0029 vs 0.073): detecta señales que el EP no puede resolver.

## Resultado

**Headline — ξ=0.0018, N=192. Convención: menor log-loss = mejor; d_ll = LL_full − LL_ρ0 > 0 ⇒ full calibra PEOR.**

| | LL_full | LL_ρ0 | Δlog-loss | SE pareado | z |
|---|---|---|---|---|---|
| **Agregado (3 copas)** | 2.8305 | 2.8263 | **+0.0042** | 0.0029 | **+1.47** |

**Por copa (ξ=0.0018, 64 partidos c/u):**

| Copa | LL_full | LL_ρ0 | Δlog-loss | SE pareado | z |
|--------|---------|-------|------|-----------|------|
| WC2018 | 2.8298 | 2.8203 | +0.0095 | 0.0052 | +1.85 |
| WC2014 | 2.9833 | 2.9813 | +0.0019 | 0.0061 | +0.32 |
| WC2010 | 2.6785 | 2.6772 | +0.0013 | 0.0024 | +0.53 |

n_common = 64 por copa, n_skipped = 0 (mismo conjunto que #8, verificado).

## Interpretación

1. **ρ tiende a calibrar PEOR la matriz, no mejor.** d_ll = +0.0042 > 0 en el agregado y en **las 3 copas** (signo consistente), z=+1.47. NO significativo a 0.05 (necesitaría |z|≥1.96), pero la **dirección es clara y consistente**: la corrección τ de Dixon-Coles no aporta calibración contra selecciones, y si acaso la degrada un poquito.
2. **El log-loss resolvió lo que el EP no podía.** #8 (EP) dio z=+0.57 (ruido alrededor de cero); #10 (log-loss) da z=+1.47 con el mismo signo. La métrica continua y de matriz completa ve una tendencia que el pick discreto no puede. Es el "diagnóstico más suave" que el handoff anticipaba.
3. **Combinado con #8, el caso de ρ se cierra:** ρ **no se gana su lugar en la decisión** (#8, EP: z=+0.57) **ni en la calibración** (#10, log-loss: z=+1.47, tendencia a empeorar). Ninguna métrica favorece a ρ; ambas apuntan a neutro-o-contra. Es "measure, don't assume" llevado al final: la corrección que es la razón de ser de Dixon-Coles no compra nada contra selecciones (lo que Round 1 anticipó en otra métrica).

## Veredicto

**ρ no se gana su lugar en NINGUNA métrica medida.** La decisión D8 (mantener `fit_rho=True`) **se sostiene** estrictamente — la evidencia contra ρ NO es significativa (z=+1.47 < 1.96) y ρ es la base teórica DC ya oraculizada. **Pero #10 inclina la balanza hacia ρ0:** si se buscara simplificar el modelo de producción (Occam), ρ0 (Poisson independiente) ahora tiene respaldo empírico — no pierde EP y tiende a calibrar marginalmente mejor. **Reabrir D8 hacia ρ0 es una decisión de JP** (cambio de producción: re-fit, re-predict, re-validar); este reporte la documenta como informada, no la toma. **Resolución de JP (2026-06-15): esperar más evidencia** (más copas / WC2022 virgen) antes de simplificar a ρ0 — la evidencia contra ρ no es significativa, así que `fit_rho=True` se mantiene y se revisita con más datos.

**Caveat (anti-drift + poder):** log-loss es DIAGNÓSTICO; **no re-optimizar el modelo sobre él** (cambiaría la intención EP-pure). El efecto es chico (0.004 nats) y no significativo; suficiente para decir "ρ no ayuda", no para "ρ daña". WC2022 sigue **virgen** (este leg usó WC2018/14/10).
