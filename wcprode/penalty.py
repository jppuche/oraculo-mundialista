"""penalty.py - modelo de alargue (ET) + penales: puntua el grid KO a 120'.

prode_rules §1.4 puntua el marcador KO al FINAL tras alargue (120'); un empate real = fue a
penales. El grid DC modela 90'. overtime_grid construye el marcador a 120': los no-empates
terminan a 90'; cada empate (k,k) pasa por el ET (30') = dos Poisson independientes con
lambda = c * lambda_marginal del partido. La masa de empate se redistribuye -> sigue empate
(penales) o se resuelve (favorito; el "offset al favorito").

f_ET = trace(grid_120)/trace(grid) EMERGE del modelo (no es un parametro). c=0 -> sin ET ->
grid_120 == grid (recupera el optimizer sin alargue).

Diseno + criterio: docs/penalty_model_design.md (D14). Oraculo: tests/test_penalty_oracle.py
(INTOCABLE). Integrado en optimizer.optimize_match(knockout=True).
"""
from __future__ import annotations

import numpy as np
from scipy.stats import poisson

# 30' de ET / 90' reglamentarios. Anclado a la fraccion empirica ~50% de empates-90' que van a
# penales (D14). NO bajar "por cautela": bajar c SUBE f_ET (corrige menos).
ET_TIME_SCALE = 1.0 / 3.0


def lam_marginals(grid: np.ndarray) -> tuple[float, float]:
    """Goles esperados por equipo = media de las marginales del grid.

    Opcion (c) del diseno: deriva lambda del grid mismo, sin tocar engine.py ni su oraculo.
    """
    H, A = grid.shape
    lam_h = float((grid.sum(axis=1) * np.arange(H)).sum())
    lam_a = float((grid.sum(axis=0) * np.arange(A)).sum())
    return lam_h, lam_a


def overtime_grid(grid: np.ndarray, c: float = ET_TIME_SCALE) -> np.ndarray:
    """Grid del marcador a 120' desde el grid a 90'.

    Los no-empates (h!=a) se preservan y ADEMAS reciben la masa de empates resueltos en ET.
    La diagonal de la salida proviene SOLO de empates-90'. Masa conservada salvo truncamiento
    en el borde del grid (< 1e-6 para grids realistas; ver oraculo T9).
    """
    H, A = grid.shape
    lam_h, lam_a = lam_marginals(grid)
    lh, la = c * lam_h, c * lam_a
    et_h = poisson.pmf(np.arange(H), lh)        # P(goles_home_ET = 0..H-1)
    et_a = poisson.pmf(np.arange(A), la)
    out = np.array(grid, dtype=float)
    K = min(H, A)
    for k in range(K):
        out[k, k] = 0.0                         # la diagonal se redistribuye por el ET
    for k in range(K):
        m = grid[k, k]
        if m <= 0.0:
            continue
        # empate (k,k) -> (k+i, k+j) con probabilidad m * P(i goles home ET) * P(j goles away ET)
        out[k:, k:] += m * np.outer(et_h[: H - k], et_a[: A - k])
    return out
