"""Tests del optimizer: consistencia del EV (brute-force vs decompose analitico),
seleccion sobre grillas sinteticas, y el draw-option-value de knockouts.
"""
import numpy as np

from wcprode.optimizer import expected_points, optimize_match, rank_candidates


def _ev_decompose(grid: np.ndarray, ph: int, pa: int) -> float:
    """Referencia independiente (docs/prode_rules.md seccion 3): descompone el EV en
    12*P(exacto) + 5*P(mismo resultado, no exacto) + 2*P(un equipo, no exacto).
    Debe coincidir con el brute-force que usa match_points."""
    H, A = np.indices(grid.shape)
    exact = (H == ph) & (A == pa)
    p_exact = grid[exact].sum()
    out = (np.sign(H - A) == np.sign(ph - pa)) & ~exact
    p_out = grid[out].sum()
    one = ((H == ph) | (A == pa)) & ~exact
    p_one = grid[one].sum()
    return 12 * p_exact + 5 * p_out + 2 * p_one


def test_brute_force_matches_decompose():
    rng = np.random.default_rng(0)
    g = rng.random((7, 7))
    g /= g.sum()
    for ph in range(7):
        for pa in range(7):
            assert abs(expected_points(g, ph, pa) - _ev_decompose(g, ph, pa)) < 1e-9


def test_concentrated_grid_picks_that_scoreline():
    g = np.zeros((7, 7))
    g[2, 1] = 0.85
    g[0, 0] = 0.15
    assert optimize_match(g)["best"] == (2, 1)


def test_optimal_can_differ_from_modal():
    # Resultado mas probable = victoria local, pero el marcador modal es empate.
    # El optimizer debe preferir un marcador del outcome mas probable, no el modal.
    g = np.zeros((7, 7))
    g[1, 1] = 0.22          # modal: empate
    g[1, 0] = 0.20
    g[2, 0] = 0.18
    g[2, 1] = 0.16          # masa de victoria local repartida
    g[0, 1] = 0.12
    g[0, 0] = 0.12
    r = optimize_match(g)
    modal = r["modal_scoreline"]
    assert modal == (1, 1)
    assert r["best"][0] > r["best"][1]   # el optimo predice victoria local, no empate


def test_candidates_bounded_by_max_pred():
    g = np.full((10, 10), 1 / 100)
    ranking = rank_candidates(g, max_pred=6)
    assert len(ranking) == 49
    assert all(0 <= ph <= 6 and 0 <= pa <= 6 for (ph, pa), _ in ranking)


def test_knockout_draw_option_value():
    g = np.zeros((7, 7))
    g[0, 0] = g[1, 1] = 0.3
    g[1, 0] = g[0, 1] = 0.2
    ev_no = expected_points(g, 1, 1, knockout=False)
    ev_ko = expected_points(g, 1, 1, knockout=True, pen_win_prob=0.55)
    assert ev_ko > ev_no                                   # el empate gana option value
    # un candidato no-empate no cambia con knockout
    assert expected_points(g, 1, 0, knockout=True) == expected_points(g, 1, 0, knockout=False)
