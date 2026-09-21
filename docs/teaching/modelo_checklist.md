---
doc_type: log
purpose: Checklist viva de la sesión de enseñanza del modelo a JP. Metodología incremental — no se avanza de etapa sin dominio verificado de la actual.
audience: [agents, humans]
when_to_use:
  - Durante sesiones de teaching del modelo (actualizar checkboxes al verificar dominio)
  - Al retomar el teaching en sesión nueva (leer para saber dónde quedó)
last_verified: 2026-06-10
maintenance: living
entries_format: "checkbox por concepto, con fecha de verificación y evidencia (qué demostró JP)"
---

# Teaching — El modelo del Oráculo, de cero a dominio

Regla de la sesión: JP re-formula primero, el agente llena huecos después. Quiz por etapa (AskUserQuestion, orden de respuestas rotado, sin revelar hasta el submit). No se marca ✅ sin demostración.

## Etapa 1 — El problema (por qué existe esto)

- [ ] 1.1 Qué paga el prode: 12/5/2 + bonus penales — y por qué eso NO es un pool 1X2
- [ ] 1.2 Por qué "predecir el resultado más probable" es subóptimo: EV sobre la grilla vs modal
- [ ] 1.3 Por qué el motor debe producir la matriz completa P(h,a) y no solo P(gana/empata/pierde)
- [ ] 1.4 Las dos ramas del problema: motor de probabilidades (agnóstico al scoring) vs optimizador (depende 100% del scoring)

## Etapa 2 — El modelo base (Poisson)

- [ ] 2.1 Goles como conteos: por qué Poisson es el punto de partida natural
- [ ] 2.2 λ por equipo y partido: attack − defence + localía, en escala log
- [ ] 2.3 Qué significa "independiente": P(h,a) = P(h)·P(a), y qué supone eso del fútbol
- [ ] 2.4 La ventaja de localía γ y por qué neutral=True la apaga (WC2026: casi todo neutral salvo anfitriones)

## Etapa 3 — Dixon-Coles (el corazón)

- [ ] 3.1 El defecto empírico del Poisson independiente: sub-reporta 0-0, 1-0, 0-1, 1-1
- [ ] 3.2 La corrección τ y el parámetro ρ: qué hace celda por celda
- [ ] 3.3 Por qué ESAS celdas son exactamente las que pagan en NUESTRO prode (la conexión modelo↔scoring)
- [ ] 3.4 ρ̂ = −0.1285 en EPL 17/18: qué significa el signo y la magnitud

## Etapa 4 — Time-decay (el componente que más mueve)

- [ ] 4.1 El problema: 49k partidos desde 1872, pero Brasil 1970 no dice nada de Brasil 2026
- [ ] 4.2 Pesos exponenciales w = exp(−ξ·días): half-life, qué significa ξ=0.0018 (≈385 días)
- [ ] 4.3 Por qué decay mueve ~10× más que elegir el modelo (y el caveat: eso se midió en RPS de clubes)
- [ ] 4.4 El knob abierto: por qué Brasil-Marruecos sale parejo y qué haría Fase 3 al respecto

## Etapa 5 — El fit (MLE)

- [ ] 5.1 Qué significa "fitear": elegir los parámetros que hacen más probable lo observado
- [ ] 5.2 Verosimilitud ponderada: cómo entran los pesos del decay
- [ ] 5.3 Identificabilidad: por qué mean(attack)=0 y qué pasaría sin esa ancla
- [ ] 5.4 El clip de τ: el NaN de la 1 AM que el review predijo y el bug de gradiente que O7 cazó

## Etapa 6 — Del modelo a la decisión (el optimizador)

- [ ] 6.1 EV de una predicción: sumar match_points sobre toda la grilla, pesado por P
- [ ] 6.2 Por qué a veces elige NO-modal (Corea 1-0 sobre modal 1-1)
- [ ] 6.3 El option value del empate en knockouts (+5 solo accesible prediciendo empate)
- [ ] 6.4 EV-pure vs rank-dependent: por qué NO jugamos a ganar el prode (y cuándo cambiaría)

## Etapa 7 — Validación (cómo sabemos que no nos mentimos)

- [ ] 7.1 Por qué el examen se escribe ANTES del código (oracle-first) y qué clase de fallo previene
- [ ] 7.2 El oráculo: qué prueba cada familia de tests (acceptance / recovery / cross-fit / referencia externa / invariantes)
- [ ] 7.3 La historia del bug de gradiente: por qué los bloqueantes no lo vieron y el report-only sí
- [ ] 7.4 Lo que sigue sin validar: las magnitudes en expected points (Fase 3, WC2022 virgen)

## Registro de verificación

| Fecha | Etapa | Evidencia de dominio |
|-------|-------|----------------------|
| 2026-06-10 | Baseline (restatement inicial) | 1.1-1.3 intuición correcta sin mecanismo; 1.4 idk. Etapas 2-3-5-6 desde cero. **4.1 y 4.3 correctos** (decay = peso por recencia; varianza entre modelos < varianza por relevancia temporal). **7.1 correcto** (capturó la lección de proceso: reglas escritas ≠ enforcement). Pidió detalle de 4.4 + casos análogos → cubrir en Etapa 4 |
