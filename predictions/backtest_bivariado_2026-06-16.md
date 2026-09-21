---
doc_type: evidence
purpose: Resultado del backtest pareado bivariado (Karlis-Ntzoufras) vs DC-full vs ρ0 (Fase 3, "otra mitad de #8").
audience: [agents, humans]
when_to_use:
  - Antes de re-litigar si la dependencia explícita (bivariado) se gana su lugar
  - Para entender por qué el gradiente analítico fue indispensable (el numérico daba la conclusión OPUESTA)
last_verified: 2026-06-16
maintenance: snapshot
related_docs:
  - bivariate_design.md
  - backtest_models_2026-06-15.md
  - DECISIONS.md
---

# Backtest bivariado (KN) vs DC-full vs ρ0 — evidencia (Fase 3)

## Pregunta y método

¿Una dependencia goles-goles **explícita y global** (Poisson bivariado de Karlis-Ntzoufras,
`X=W1+W3, Y=W2+W3`, `λ3≥0`) se gana su lugar en **EP held-out** contra DC-full (corrección τ)
y ρ0 (Poisson independiente)? Es la **otra mitad de #8** (que midió que la corrección ρ de DC
no aporta). Rolling-origin held-out WC2018+2014+2010, **WC2022 virgen**, ξ=0.0018, ventana 8a,
SE **pareado** (bootstrap seed 20260615), N=192. Un solo fit por fecha (combinado EP+log-loss).

Cuatro modelos, mismo ξ/ventana/decay: **bivF** (λ3 libre), **bivI** (λ3=0, mismo optimizador),
**full** (DC-full), **rho0** (DC ρ0). La comparación PRIMARIA `bivF vs bivI` aísla el efecto
NETO de λ3 **intra-engine** (sin confound de optimizador).

## Episodio del optimizador (crítico — sin esto la conclusión se invierte)

El build inicial (gradiente NUMÉRICO) pasaba el oráculo con 8 equipos pero **no convergía con
los ~300 equipos reales** (ralos, desbalanceados): se quedaba a **Δlog-lik≈43** del óptimo, con
ratings errados por ~5 en log-escala, y reportaba **λ3=0 espurio** + bivariado PEOR que ρ0. Se
reemplazó por **gradiente analítico** (ecuaciones EM de KN, `E[W3|x,y]`), validado con check de
gradiente (vs numérico de scipy, ~1e-5, estable en λ3=0) y oráculo reforzado (`t1c`, convergencia
sobre el universo real). Tras el fix: Δlog-lik vs DC-ρ0 = **+0.0006**, λ3 real ≈ **0.04-0.08**,
y la conclusión de EP se **invirtió de signo**. Detalle: DECISIONS.md **D10**.

**Validación metodológica (en las 3 copas):** `bivI vs rho0` da **Δ=0.0000 exacto** — el
gradiente analítico converge al MISMO punto que DC-ρ0 (mismo modelo). La comparación es limpia.

## Resultados

`λ3` muestreado (última fecha de cada copa): **WC2018=0.040, WC2014=0.076, WC2010=0.037** —
chico, positivo, consistente. **NO colapsa a 0** (a diferencia de lo que predijo el diseño y de
lo que reportaba el optimizador numérico roto).

### Agregado N=192 (SE pareado; verificado: SE analítico = bootstrap seed20260615 = seed777)

| Comparación | métrica | Δ | SE | z | veredicto |
|---|---|---|---|---|---|
| **bivF vs bivI** (λ3 neto) | EP | **+0.120** | 0.069 | **+1.73** | λ3 ayuda, NO significativo (z<1.96) |
| bivF vs DC-full | EP | +0.078 | 0.062 | +1.25 | bivariado ≥ producción, NO significativo |
| bivF vs DC-rho0 | EP | +0.120 | 0.069 | +1.73 | (= vs bivI, porque bivI≡rho0) |
| bivF vs bivI (λ3 neto) | log-loss | +0.0028 | 0.0053 | +0.52 | λ3 calibra un pelín PEOR, no sig |
| bivF vs DC-full | log-loss | −0.0015 | 0.0061 | −0.24 | empate |
| bivF vs DC-rho0 | log-loss | +0.0028 | 0.0053 | +0.52 | empate / pelín peor |

Convención: EP Δ>0 ⇒ bivF mejor; log-loss Δ<0 ⇒ bivF mejor.

### Por copa (EP, bivF vs bivI = efecto λ3)

| Copa | Δ EP | z | λ3 | nota |
|---|---|---|---|---|
| WC2018 | +0.344 | 1.72 | 0.040 | λ3 mueve picks a favor |
| WC2014 | +0.000 | — | 0.076 | λ3>0 pero no cambia ningún pick óptimo |
| WC2010 | +0.016 | 0.28 | 0.037 | casi nulo |

## Veredicto (orquestador)

1. **EP held-out (métrica de decisión): el bivariado NO se gana su lugar de forma
   significativa.** Ni vs ρ0 (z=1.73) ni vs DC-full (z=1.25) cruza z=1.96 con N=192. **Mantener
   `fit_rho=True` (DC-full) en producción** — el bivariado no justifica el cambio.

2. **Matiz honesto (interesante para el portfolio):** a diferencia de la predicción "colapsa a
   ρ0", el bivariado SÍ encuentra una dependencia positiva leve (λ3≈0.05) y la señal de EP es
   **positiva y consistente** (z=1.73), **más fuerte que la de ρ en #8** (z=0.57). Lectura: si
   alguna forma de dependencia tuviera chance contra selecciones, sería la **positiva explícita**
   (KN), no la τ de Dixon-Coles — pero ninguna alcanza significancia. Cierra, junto a #8/#10, la
   pregunta "¿alguna forma de dependencia goles-goles aporta EP?": **señal débil, no concluyente.**

3. **log-loss (diagnóstico, D9): no rescata al bivariado** (empate o un pelín peor). Consistente
   con que λ3 mueve pocos picks. NO se re-optimiza el modelo sobre esto.

## Caveats

- **N=192, z<1.96:** todo es no significativo. La señal positiva en EP es real en dirección pero
  no en magnitud robusta. No sobre-leer.
- **WC2022 sigue virgen** — más copas podrían afilar el z (en cualquier dirección).
- KN solo captura correlación **positiva**: que λ3≈0.05>0 dice que en selecciones hay una
  dependencia positiva leve (contrario al ρ<0 que estimó DC sobre 4 celdas — son cosas distintas:
  τ de DC pondera 4 marcadores bajos, λ3 es covarianza global).
- El resultado depende del gradiente analítico (D10): con el numérico la conclusión era opuesta.
