# Backtest multi-copa — DC-full vs ρ0 (Fase 3, #8)

**Fecha:** 2026-06-15 · **Harness:** `wcprode/backtest.py` (`paired_model_comparison`, sobre el rolling-origin oraculizado D6) ·
**Comando:** `.venv/Scripts/python.exe scripts/backtest_models.py` (default ξ=0.0018; `--xi-grid 0.0 0.0018 0.003` para robustez; ventana 8a, bootstrap 2000 iter, seed 20260615).
**Validación del orquestador:** recálculo independiente (merge de pandas + bootstrap seed 777 + SE analítico) reprodujo dep y SE en todas las celdas. Suite 84/84 (71 intocables + 13 nuevos de regresión).

Pregunta: a nuestro punto de operación (ξ=0.0018), ¿la corrección ρ de Dixon-Coles se gana su lugar en **expected points held-out** contra selecciones? `fit_rho=False` ⇒ ρ=0 (Poisson independiente puro); la única diferencia con DC-full es la corrección τ en las 4 celdas bajas (0-0, 1-0, 0-1, 1-1). Semilla: **O7** (N=64, WC2018, report-only) ya había visto full ≈ ρ0+decay.

## Método — por qué SE *pareado*

Full y ρ0 comparten λ, μ y decay; difieren solo en 4 celdas. Sus puntos por partido están altísimamente correlacionados, así que **Δ_i = pts_full_i − pts_rho0_i** tiene varianza chica. El SE *pareado* (bootstrap sobre Δ) mide directamente la incertidumbre de la diferencia, cancelando la varianza común partido-a-partido. **Potencia real medida:** en WC2018, SE marginal de cada modo ≈ 0.46, pero **SE pareado de la diferencia = 0.18** (~2.5× más fino). Eso es lo que permite leer N=192 con sentido, donde el SE marginal del reporte de ξ (~0.27 agregado) nunca resolvería un efecto chico.

## Resultado

**Headline — ξ=0.0018 (punto de operación), N=192:**

| | EP_full | EP_ρ0 | ΔEP | SE pareado | z |
|------|---------|-------|------|-----------|-----|
| **Agregado (3 copas)** | 5.031 | 4.990 | **+0.042** | 0.073 | **+0.57** |

**Por copa (ξ=0.0018, 64 partidos c/u):**

| Copa | EP_full | EP_ρ0 | ΔEP | SE pareado | z | picks que ρ cambió |
|--------|---------|-------|------|-----------|------|----|
| WC2018 | 4.859 | 4.734 | +0.125 | 0.181 | +0.69 | 3 / 64 |
| WC2014 | 4.312 | 4.359 | −0.047 | 0.082 | −0.57 | 3 / 64 |
| WC2010 | 5.922 | 5.875 | +0.047 | 0.085 | +0.55 | 2 / 64 |

**Robustez en ξ (agregado, N=192):**

| ξ | ΔEP | SE pareado | z | nota |
|--------|------|-----------|------|------|
| 0.0000 | +0.005 | 0.075 | +0.07 | sin decay; full ≈ ρ0 |
| **0.0018** | **+0.042** | 0.073 | **+0.57** | operativo |
| 0.0030 | −0.141 | 0.082 | −1.71 | full tiende a **peor** (empujado por WC2014 −0.39) |

n_common = 64 por copa, n_skipped = 0 (cobertura total, ventana 8a). A ξ=0.003, WC2010 dio Δ=0 exacto (ρ no cambió ningún pick en los 64 → z=nan; caso degenerado, no error).

## Interpretación

1. **La corrección ρ NO se gana su lugar en EP held-out.** A ξ operativo, z=+0.57: la ventaja de +0.042 pts/partido es indistinguible de cero **incluso con el test más potente** (pareado, N=192). El efecto es chico por construcción: ρ solo cambia 2-3 picks de 64 por copa.
2. **Confirma y fortalece O7.** Aquel hallazgo N=1 (full ≈ ρ0+decay) se sostiene con 3× los datos y el SE correcto. Lo que Round 1 predijo: contra selecciones, la corrección de marcadores bajos aporta poco a la **decisión**.
3. **Signo inestable entre copas** (WC2018 +0.13, WC2014 −0.05, WC2010 +0.05), todos dentro de ~0.7 SE. Sin señal sistemática a favor ni en contra.
4. **En el plateau, ρ nunca ayuda; a ξ alto tiende a dañar** (ξ=0.003, z=−1.71). Consistente con D7: más memoria corta es lo peligroso, y sumarle ρ no lo rescata.

## Veredicto

**Para el prode (decisión EV/pick), DC-full no supera medible­mente a ρ0.** No hay caso empírico para confiar en la corrección ρ como fuente de puntos contra selecciones.

**NO cambiar el modelo de producción (mantener fit_rho=True).** Razones: (a) a ξ=0.0018 no daña (z=+0.57, lado positivo del cero); (b) es la base teórica que hace al modelo "Dixon-Coles" y está calibrado+oraculizado; (c) la ganancia de sacarlo sería nula. Es un hallazgo de validación tipo "medí, no asumí": **medimos que ρ no mueve la aguja**, igual que medimos ξ.

**Caveat de poder + puente a #10:** EP es **ciego a la calibración de la matriz** P(h,a) salvo por el pick óptimo. ρ podría mejorar la calibración de toda la grilla sin cambiar el pick — y EP no lo vería. El complemento natural es **#10 (log-loss sobre P(h,a))**: si ahí tampoco aparece, el caso "ρ no se gana su lugar" queda cerrado; si aparece, ρ calibra mejor aunque no cambie decisiones. Por eso este resultado **no** justifica sacar ρ, solo que no es fuente de EP.

**Pendiente de #8 — bivariado:** la otra mitad del item (Poisson bivariado con dependencia explícita, no solo la corrección τ) es **componente numérico nuevo** ⇒ oráculo pre-aprobado por JP ANTES de construir (D2). No abordado acá.
