"""test_logloss.py — tests de regresión para el harness de log-loss (Fase 3, #10).

NO es oráculo (DECISIONS.md D2). Cubre:
  - log_loss_grid (valor exacto sobre grids conocidos + clip de cola)
  - rolling_origin_logloss CONSISTENCIA con rolling_origin_points (mismo conjunto predicho/saltado)
  - _align_records(..., value_key="ll")
  - paired_logloss_comparison (reproducible + smoke end-to-end)
"""
import numpy as np
import pandas as pd
import pytest

from wcprode.backtest import (
    log_loss_grid,
    rolling_origin_logloss,
    rolling_origin_points,
    paired_logloss_comparison,
    _align_records,
)

COLS = ["date", "home_team", "away_team", "home_score", "away_score", "neutral"]


def _df(rows):
    df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    return df


# =====================================================================
# log_loss_grid — valor exacto
# =====================================================================
def test_log_loss_grid_uniform():
    # Grid uniforme 4x4 (cada celda = 1/16) -> -log(1/16) para CUALQUIER marcador
    grid = np.full((4, 4), 1.0 / 16.0)
    expected = -np.log(1.0 / 16.0)
    for actual in [(0, 0), (1, 2), (3, 3), (2, 0)]:
        assert log_loss_grid(grid, actual) == pytest.approx(expected)


def test_log_loss_grid_known_peak():
    # Grid con un pico conocido en (1,1): valor correcto en el pico y en otra celda
    grid = np.full((4, 4), 0.01)
    grid[1, 1] = 1.0 - 0.01 * 15  # masa redistribuida; suma = 1
    assert log_loss_grid(grid, (1, 1)) == pytest.approx(-np.log(grid[1, 1]))
    assert log_loss_grid(grid, (0, 0)) == pytest.approx(-np.log(0.01))


# =====================================================================
# log_loss_grid — clip de cola (marcadores imposibles no crashean)
# =====================================================================
def test_log_loss_grid_tail_clip():
    # Grid 16x16 (como engine, max_goals=15) con actual=(20,0) -> clipa a (15,0)
    grid = np.full((16, 16), 1.0 / (16 * 16))
    val = log_loss_grid(grid, (20, 0))
    assert np.isfinite(val)
    # Debe coincidir con el valor en la celda clipeada (15, 0)
    assert val == pytest.approx(log_loss_grid(grid, (15, 0)))


def test_log_loss_grid_negative_clip():
    # Marcador negativo (no debería pasar, pero el clip lo cubre) -> celda 0
    grid = np.full((4, 4), 1.0 / 16.0)
    assert np.isfinite(log_loss_grid(grid, (-3, 1)))


def test_log_loss_grid_zero_prob_inf():
    # P=0 en la celda -> inf (no crashea con log(0))
    grid = np.zeros((4, 4))
    grid[0, 0] = 1.0
    assert log_loss_grid(grid, (2, 2)) == float("inf")


# =====================================================================
# Generador sintético (patrón de test_model_comparison._synth_played)
# =====================================================================
def _synth_played(n_hist=45, seed=99):
    """DataFrame sintético con ~n_hist partidos. COLS estándar + tournament + played."""
    rng = np.random.default_rng(seed)
    teams = ["ARG", "BRA", "FRA", "ESP", "GER", "ENG"]
    rows = []
    base = pd.Timestamp("2010-01-10")
    for i in range(n_hist):
        date = base + pd.Timedelta(days=i * 7)
        h, a = rng.choice(len(teams), 2, replace=False)
        hs = int(rng.poisson(1.4))
        as_ = int(rng.poisson(1.0))
        tourn = "FIFA World Cup" if i % 5 == 0 else "Friendly"
        rows.append({
            "date": date,
            "home_team": teams[h],
            "away_team": teams[a],
            "home_score": hs,
            "away_score": as_,
            "neutral": False,
            "tournament": tourn,
            "played": True,
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# =====================================================================
# rolling_origin_logloss — CONSISTENCIA con rolling_origin_points
# =====================================================================
def test_logloss_consistent_with_points():
    # CRÍTICO: rolling_origin_logloss predice/salta EXACTAMENTE el mismo conjunto de
    # partidos que rolling_origin_points sobre el mismo input.
    played = _synth_played(n_hist=45, seed=42)
    held = played.tail(8).copy().reset_index(drop=True)

    kw = dict(xi=0.0018, fit_rho=False, window_years=8)
    r_pts = rolling_origin_points(played, held, **kw)
    r_ll = rolling_origin_logloss(played, held, **kw)

    assert r_ll.n_predicted == r_pts.n_predicted
    assert r_ll.n_skipped == r_pts.n_skipped
    # Mismos partidos en records (date/home/away), en el mismo orden
    keys_pts = [(rec["date"], rec["home"], rec["away"]) for rec in r_pts.records]
    keys_ll = [(rec["date"], rec["home"], rec["away"]) for rec in r_ll.records]
    assert keys_ll == keys_pts


def test_logloss_skip_unseen_team():
    # Equipo no visto -> skip (mismo manejo que rolling_origin_points)
    df = _df([
        ("2020-01-01", "A", "B", 1, 0, False),
        ("2020-02-01", "A", "B", 2, 1, False),
        ("2020-06-01", "A", "Z", 1, 0, False),   # Z nunca visto
    ])
    held = df[df["date"] == "2020-06-01"]
    r = rolling_origin_logloss(df, held, xi=0.0, fit_rho=False, window_years=None, on_predict_error="skip")
    assert r.n_skipped == 1 and r.n_predicted == 0
    with pytest.raises((ValueError, AssertionError)):
        rolling_origin_logloss(df, held, xi=0.0, fit_rho=False, window_years=None, on_predict_error="raise")


def test_logloss_records_aligned_and_finite():
    # records[i] alinea con log_losses[i]; valores finitos; orden temporal asc
    played = _synth_played(n_hist=45, seed=7)
    held = played.tail(8).copy().reset_index(drop=True)
    r = rolling_origin_logloss(played, held, xi=0.001, fit_rho=False, window_years=8)
    assert len(r.records) == len(r.log_losses) == r.n_predicted
    assert all(r.records[i]["ll"] == r.log_losses[i] for i in range(len(r.log_losses)))
    dates = [rec["date"] for rec in r.records]
    assert dates == sorted(dates)
    if r.n_predicted > 0:
        assert np.isfinite(r.log_losses).all()
        assert r.mean_ll > 0  # -log p con p<1 es positivo


def test_logloss_deterministic():
    played = _synth_played(n_hist=45, seed=3)
    held = played.tail(8).copy().reset_index(drop=True)
    kw = dict(xi=0.001, fit_rho=False, window_years=8)
    r1 = rolling_origin_logloss(played, held, **kw)
    r2 = rolling_origin_logloss(played, held, **kw)
    assert np.array_equal(r1.log_losses, r2.log_losses)
    assert r1.mean_ll == r2.mean_ll and r1.se == r2.se


# =====================================================================
# _align_records con value_key="ll"
# =====================================================================
def _make_rec(date, home, away, ll):
    return {"date": date, "home": home, "away": away, "ll": ll, "neutral": False}


def test_align_records_value_key_ll():
    recs_a = [
        _make_rec("2018-06-15", "A", "B", 2.5),
        _make_rec("2018-06-16", "C", "D", 1.1),
        _make_rec("2018-06-17", "E", "F", 3.3),
    ]
    recs_b = [
        _make_rec("2018-06-15", "A", "B", 2.0),
        _make_rec("2018-06-16", "C", "D", 1.5),
    ]  # falta m3
    common_keys, va, vb, n_only_a, n_only_b = _align_records(recs_a, recs_b, value_key="ll")
    assert len(common_keys) == 2
    assert va.tolist() == [2.5, 1.1]
    assert vb.tolist() == [2.0, 1.5]
    assert n_only_a == 1
    assert n_only_b == 0


# =====================================================================
# paired_logloss_comparison — reproducible + smoke end-to-end
# =====================================================================
def test_paired_logloss_reproducible():
    played = _synth_played(n_hist=45, seed=11)
    held = played.tail(6).copy().reset_index(drop=True)
    kw = dict(xi=0.0018, window_years=8, n_boot=200, seed=20260615)
    pc1 = paired_logloss_comparison(played, held, **kw)
    pc2 = paired_logloss_comparison(played, held, **kw)
    assert pc1.d_ll == pc2.d_ll
    assert pc1.se_paired == pc2.se_paired
    assert np.array_equal(pc1.delta, pc2.delta)


def test_paired_logloss_smoke():
    played = _synth_played(n_hist=45, seed=21)
    held = played.tail(6).copy().reset_index(drop=True)
    pc = paired_logloss_comparison(played, held, xi=0.0018, window_years=8, n_boot=200, seed=20260615)

    assert pc.n_common >= 0
    assert len(pc.delta) == pc.n_common

    if pc.n_common > 0:
        assert np.isfinite(pc.d_ll)
        assert np.isfinite(pc.se_paired)
        assert np.isfinite(pc.mean_ll_full)
        assert np.isfinite(pc.mean_ll_rho0)
        # d_ll = mean(ll_full - ll_rho0)
        assert pc.d_ll == pytest.approx(pc.delta.mean())
        # delta = ll_full - ll_rho0 (convención de signo)
        assert pc.d_ll == pytest.approx(pc.mean_ll_full - pc.mean_ll_rho0)

    assert pc.r_full.fit_rho is True
    assert pc.r_rho0.fit_rho is False
    assert pc.xi == 0.0018
