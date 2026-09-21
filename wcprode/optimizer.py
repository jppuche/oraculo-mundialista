"""optimizer.py — argmax de expected points sobre la grilla de marcadores.

Metrica de decision del proyecto (docs/prode_rules.md seccion 3): la prediccion
optima NO es "el 1X2 mas probable" sino el marcador (ph,pa) que maximiza el valor
esperado de match_points sobre TODA la grilla P(H,A). El credito parcial (exacto 12
/ resultado 5 / un equipo 2) hace que el argmax no sea trivial.

Se usa match_points VERBATIM (wcprode.scoring) como unica fuente de verdad del
puntaje, evaluado celda por celda sobre la grilla -> sin re-implementar la logica.
"""
from __future__ import annotations

import numpy as np

from .penalty import ET_TIME_SCALE, overtime_grid
from .scoring import match_points

DEFAULT_MAX_PRED = 6          # candidatos 0..6 por lado (prode_rules: mas que suficiente)
DEFAULT_PEN_WIN_PROB = 0.55   # P(acertar ganador de penales) si elijo al favorito (~50/50)


def expected_points(grid: np.ndarray, ph: int, pa: int, *,
                    knockout: bool = False,
                    pen_win_prob: float = DEFAULT_PEN_WIN_PROB) -> float:
    """E[match_points((ph,pa), (H,A))] sumando sobre toda la grilla P(H,A).

    knockout=True agrega el draw-option-value (+5 por penales): solo accesible
    prediciendo un empate, igual para todo empate -> 5 * P(empate real) * pen_win_prob.
    En grupos NO hay penales: knockout=False.
    """
    n_h, n_a = grid.shape
    ev = 0.0
    for h in range(n_h):
        row = grid[h]
        for a in range(n_a):
            p = row[a]
            if p > 0.0:
                ev += p * match_points((ph, pa), (h, a))
    if knockout and ph == pa:
        ev += 5.0 * float(np.trace(grid)) * pen_win_prob
    return ev


def rank_candidates(grid: np.ndarray, *, max_pred: int = DEFAULT_MAX_PRED,
                    knockout: bool = False,
                    pen_win_prob: float = DEFAULT_PEN_WIN_PROB) -> list[tuple[tuple[int, int], float]]:
    """Todos los candidatos (ph,pa) en 0..max_pred ordenados por EV descendente."""
    cands = [
        ((ph, pa), expected_points(grid, ph, pa, knockout=knockout, pen_win_prob=pen_win_prob))
        for ph in range(max_pred + 1)
        for pa in range(max_pred + 1)
    ]
    cands.sort(key=lambda kv: kv[1], reverse=True)
    return cands


def optimize_match(grid: np.ndarray, *, max_pred: int = DEFAULT_MAX_PRED,
                   knockout: bool = False,
                   pen_win_prob: float = DEFAULT_PEN_WIN_PROB,
                   c: float = ET_TIME_SCALE, top: int = 5) -> dict:
    """Prediccion optima + diagnostico para un partido. Listo para cargar en el prode.

    knockout=True puntua el grid a 120' (penalty.overtime_grid): el alargue redistribuye la masa
    de empate, corrigiendo el sobre-tilt del draw-option-value (el +5 de penales usa P(empate 120'),
    no P(empate 90'). c=0 -> sin ET (comportamiento sin alargue). Grupos (knockout=False) NO
    construyen grid_120: el path queda intacto.
    """
    eval_grid = overtime_grid(grid, c) if (knockout and c > 0.0) else grid
    ranking = rank_candidates(eval_grid, max_pred=max_pred, knockout=knockout, pen_win_prob=pen_win_prob)
    best, best_ev = ranking[0]
    return {
        "best": best,
        "best_ev": best_ev,
        "p_best_exact": float(eval_grid[best]) if best[0] < eval_grid.shape[0] and best[1] < eval_grid.shape[1] else 0.0,
        "p_home": float(np.tril(eval_grid, -1).sum()),
        "p_draw": float(np.trace(eval_grid)),
        "p_away": float(np.triu(eval_grid, 1).sum()),
        "ranking": ranking[:top],
        "modal_scoreline": tuple(int(i) for i in np.unravel_index(int(np.argmax(eval_grid)), eval_grid.shape)),
    }
