"""test_penalty_oracle.py - ORACULO del modelo de alargue (ET) + penales. INTOCABLE (D2).

5o oraculo del proyecto. Aprobado por JP 2026-06-29 (los 9 tests del design §4). T3 se
CORRIGIO pre-materializacion (el orquestador, al implementar, vio que la convolucion SUMA
masa a las no-empate -> "no-empate intacto" era falso; reconfirmado con JP, D14).

Valores computados INDEPENDIENTEMENTE del componente: poisson.pmf explicito + una convolucion
de referencia local (_ref) que NO llama a overtime_grid. expected_points (cadena base, ya
oraculizada por test_optimizer) sirve de referencia para los tests de regresion (T4/T7).
"""
import numpy as np
import pytest
from scipy.stats import poisson

from wcprode.optimizer import expected_points, optimize_match
from wcprode.penalty import ET_TIME_SCALE, lam_marginals, overtime_grid


def _ref(grid, c):
    """Convolucion de REFERENCIA (independiente de overtime_grid)."""
    H, A = grid.shape
    lam_h = sum(grid[h, a] * h for h in range(H) for a in range(A))
    lam_a = sum(grid[h, a] * a for h in range(H) for a in range(A))
    lh, la = c * lam_h, c * lam_a
    out = np.array(grid, float)
    K = min(H, A)
    for k in range(K):
        out[k, k] = 0.0
    for k in range(K):
        m = grid[k, k]
        for i in range(H - k):
            for j in range(A - k):
                out[k + i, k + j] += m * poisson.pmf(i, lh) * poisson.pmf(j, la)
    return out


def _poisson_grid(lh, la, K=16):
    g = np.outer(poisson.pmf(np.arange(K), lh), poisson.pmf(np.arange(K), la))
    return g / g.sum()


def _brute_argmax(g, *, knockout, pwp=0.55):
    return max(((ph, pa) for ph in range(7) for pa in range(7)),
               key=lambda p: expected_points(g, p[0], p[1], knockout=knockout, pen_win_prob=pwp))


def test_t1_convolution_by_hand():
    g = np.zeros((6, 6)); g[0, 0] = 0.5; g[1, 0] = 0.3; g[0, 1] = 0.2
    c = ET_TIME_SCALE
    lh, la = c * 0.3, c * 0.2                       # lam_h=0.3, lam_a=0.2
    g120 = overtime_grid(g, c)
    assert g120[0, 0] == pytest.approx(0.5 * poisson.pmf(0, lh) * poisson.pmf(0, la))
    assert g120[1, 0] == pytest.approx(0.3 + 0.5 * poisson.pmf(1, lh) * poisson.pmf(0, la))
    assert g120[0, 1] == pytest.approx(0.2 + 0.5 * poisson.pmf(0, lh) * poisson.pmf(1, la))
    assert np.allclose(g120, _ref(g, c))


def test_t2_mass_conserved():
    g = _poisson_grid(1.4, 1.1, K=16)
    assert overtime_grid(g, ET_TIME_SCALE).sum() == pytest.approx(1.0, abs=1e-9)


def test_t3_nondraw_gains_mass():
    g = np.zeros((6, 6)); g[0, 0] = 0.4; g[1, 0] = 0.2; g[0, 1] = 0.2; g[2, 1] = 0.2
    c = ET_TIME_SCALE
    lh, la = c * 0.6, c * 0.4                       # lam_h=0.6, lam_a=0.4
    g120 = overtime_grid(g, c)
    assert g120[1, 0] > g[1, 0]                     # la no-empate (1,0) GANA masa del empate 0-0 -> 1-0
    assert g120[1, 0] == pytest.approx(0.2 + 0.4 * poisson.pmf(1, lh) * poisson.pmf(0, la))
    assert np.allclose(g120, _ref(g, c))


def test_t4_c0_recovers_actual():
    g = _poisson_grid(1.5, 1.2)
    assert np.allclose(overtime_grid(g, 0.0), g)                       # c=0 -> sin ET -> grid_120 == grid
    assert optimize_match(g, knockout=True, pen_win_prob=0.55, c=0.0)["best"] == _brute_argmax(g, knockout=True)


def test_t5_trace_is_pdraw_120():
    g = _poisson_grid(1.3, 1.3)                                        # simetrico
    c = ET_TIME_SCALE
    g120 = overtime_grid(g, c)
    lh, la = c * lam_marginals(g)[0], c * lam_marginals(g)[1]
    f_et = np.trace(g120) / np.trace(g)
    expected = sum(poisson.pmf(d, lh) * poisson.pmf(d, la) for d in range(40))
    assert f_et == pytest.approx(expected)


def test_t6_monotonic_in_c():
    g = _poisson_grid(1.4, 1.2)
    traces = [float(np.trace(overtime_grid(g, c))) for c in (0.1, 0.2, 1 / 3, 0.5)]
    assert all(traces[i] > traces[i + 1] for i in range(len(traces) - 1))   # c sube -> P(empate 120') baja


def test_t7_groups_unchanged():
    g = _poisson_grid(1.5, 1.2)
    assert optimize_match(g, knockout=False, c=ET_TIME_SCALE)["best"] == _brute_argmax(g, knockout=False)
    assert optimize_match(g, knockout=False)["p_draw"] == pytest.approx(float(np.trace(g)))


def test_t8_overtime_flips_draw_to_favorite():
    g = _poisson_grid(1.3, 1.1)                                        # favorito-leve + empate competitivo (flip robusto)
    pick_no_et = optimize_match(g, knockout=True, pen_win_prob=0.55, c=0.0)["best"]
    pick_et = optimize_match(g, knockout=True, pen_win_prob=0.55, c=ET_TIME_SCALE)["best"]
    assert pick_no_et[0] == pick_no_et[1]          # sin ET: el draw-option-value inflado hace optimo el empate
    assert pick_et[0] != pick_et[1]                # con ET: el favorito recupera el argmax


def test_t9_truncation_negligible():
    g = _poisson_grid(1.6, 1.4, K=16)
    assert abs(float(overtime_grid(g, ET_TIME_SCALE).sum()) - 1.0) < 1e-6
