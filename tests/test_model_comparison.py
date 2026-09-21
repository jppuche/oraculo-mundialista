"""test_model_comparison.py — tests de regresión para harness de comparación DC-full vs ρ0.

NO es oráculo (DECISIONS.md D2). Cubre:
  - Guardrail WC2022
  - _align_records (pareo por identidad)
  - _paired_bootstrap_se (bootstrap pareado)
  - paired_model_comparison (smoke end-to-end)
"""
import numpy as np
import pandas as pd
import pytest

from wcprode.backtest import (
    _align_records,
    _paired_bootstrap_se,
    assert_no_wc2022,
    paired_model_comparison,
    CUP_RANGES,
)

# ---- helpers de construcción de DataFrames sintéticos (patrón de test_backtest_oracle) ----
COLS = ["date", "home_team", "away_team", "home_score", "away_score", "neutral"]


def _df(rows):
    df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _held_df(rows):
    """held_out DataFrame con columna date (str) para assert_no_wc2022."""
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team"])
    df["date"] = pd.to_datetime(df["date"])
    return df


# =====================================================================
# Guardrail WC2022
# =====================================================================
def test_guardrail_wc2022_raises():
    # date dentro de la ventana WC2022 -> debe levantar AssertionError
    held = _held_df([("2022-11-25", "A", "B")])
    with pytest.raises(AssertionError, match="GUARDRAIL VIOLADO"):
        assert_no_wc2022(held, "WC2022_test")


def test_guardrail_wc2022_safe():
    # date fuera de la ventana WC2022 -> NO debe levantar
    held = _held_df([("2018-06-20", "A", "B")])
    assert_no_wc2022(held, "WC2018_test")  # no debe lanzar


def test_guardrail_wc2022_boundary_start():
    # Exactamente en WC2022_START -> contamina
    held = _held_df([("2022-11-20", "X", "Y")])
    with pytest.raises(AssertionError, match="GUARDRAIL VIOLADO"):
        assert_no_wc2022(held, "boundary_start")


def test_guardrail_wc2022_boundary_end():
    # Exactamente en WC2022_END -> contamina
    held = _held_df([("2022-12-18", "X", "Y")])
    with pytest.raises(AssertionError, match="GUARDRAIL VIOLADO"):
        assert_no_wc2022(held, "boundary_end")


# =====================================================================
# _paired_bootstrap_se
# =====================================================================
def test_paired_bootstrap_zero_variance():
    # delta constante -> media siempre igual -> SE = 0.0
    result = _paired_bootstrap_se(np.zeros(50), n_boot=500, seed=1)
    assert result == 0.0


def test_paired_bootstrap_reproducible():
    # Dos llamadas con mismo delta/seed dan resultado EXACTAMENTE idéntico
    delta = np.arange(100, dtype=float)
    se1 = _paired_bootstrap_se(delta, n_boot=200, seed=42)
    se2 = _paired_bootstrap_se(delta, n_boot=200, seed=42)
    assert se1 == se2


def test_paired_bootstrap_approx_clt():
    # Para delta con varianza conocida, SE bootstrap ≈ std(ddof=1)/sqrt(n), tolerancia 15%
    rng = np.random.default_rng(7)
    delta = rng.normal(0, 3.0, size=200)
    expected_se = float(delta.std(ddof=1)) / np.sqrt(len(delta))
    se_boot = _paired_bootstrap_se(delta, n_boot=2000, seed=20260615)
    assert abs(se_boot - expected_se) / expected_se < 0.15, (
        f"SE_boot={se_boot:.4f} demasiado lejos de expected={expected_se:.4f}"
    )


def test_paired_bootstrap_empty():
    # delta vacío -> nan
    result = _paired_bootstrap_se(np.array([]), n_boot=100, seed=1)
    assert np.isnan(result)


# =====================================================================
# _align_records
# =====================================================================
def _make_rec(date, home, away, pts):
    return {"date": date, "home": home, "away": away, "pts": pts, "neutral": False}


def test_align_identical():
    # Listas idénticas -> n_common=3, pts_a==pts_b, n_only_a=n_only_b=0
    recs = [
        _make_rec("2018-06-15", "A", "B", 5),
        _make_rec("2018-06-16", "C", "D", 2),
        _make_rec("2018-06-17", "E", "F", 0),
    ]
    common_keys, pts_a, pts_b, n_only_a, n_only_b = _align_records(recs, list(recs))
    assert len(common_keys) == 3
    assert np.array_equal(pts_a, pts_b)
    assert n_only_a == 0
    assert n_only_b == 0


def test_align_asymmetric_skip():
    # records_a = [m1,m2,m3], records_b = [m1,m2,m4] (falta m3, sobra m4)
    # -> n_common=2 (m1,m2), n_only_a=1 (m3), n_only_b=1 (m4)
    m1 = _make_rec("2018-06-15", "A", "B", 5)
    m2 = _make_rec("2018-06-16", "C", "D", 2)
    m3 = _make_rec("2018-06-17", "E", "F", 0)
    m4 = _make_rec("2018-06-18", "G", "H", 12)
    common_keys, pts_a, pts_b, n_only_a, n_only_b = _align_records(
        [m1, m2, m3], [m1, m2, m4]
    )
    assert len(common_keys) == 2
    assert pts_a.tolist() == [5.0, 2.0]
    assert pts_b.tolist() == [5.0, 2.0]
    assert n_only_a == 1
    assert n_only_b == 1


def test_align_preserves_order():
    # El orden en common_keys debe seguir el orden de records_a (temporal asc)
    recs_a = [
        _make_rec("2018-06-14", "A", "B", 2),
        _make_rec("2018-06-15", "C", "D", 5),
        _make_rec("2018-06-16", "E", "F", 0),
    ]
    # records_b tiene los mismos pero en orden diferente
    recs_b = [
        _make_rec("2018-06-16", "E", "F", 12),
        _make_rec("2018-06-14", "A", "B", 0),
        _make_rec("2018-06-15", "C", "D", 5),
    ]
    common_keys, pts_a, pts_b, _, _ = _align_records(recs_a, recs_b)
    # El orden de common_keys debe seguir al de recs_a
    assert common_keys[0][0] == pd.Timestamp("2018-06-14").isoformat()
    assert common_keys[1][0] == pd.Timestamp("2018-06-15").isoformat()
    assert common_keys[2][0] == pd.Timestamp("2018-06-16").isoformat()
    # pts_a vienen de records_a, pts_b de records_b (pueden diferir en valor)
    assert pts_a.tolist() == [2.0, 5.0, 0.0]
    assert pts_b.tolist() == [0.0, 5.0, 12.0]


def test_align_no_common():
    # Sin partidos en común -> common_keys vacío, n_only iguales a len de cada lista
    recs_a = [_make_rec("2018-06-14", "A", "B", 5)]
    recs_b = [_make_rec("2018-06-15", "C", "D", 2)]
    common_keys, pts_a, pts_b, n_only_a, n_only_b = _align_records(recs_a, recs_b)
    assert len(common_keys) == 0
    assert n_only_a == 1
    assert n_only_b == 1


# =====================================================================
# paired_model_comparison — smoke end-to-end
# =====================================================================
def _synth_played(n_hist=40, seed=99):
    """DataFrame sintético con ~n_hist partidos históricos + algunos held-out.

    Patrón de test_backtest_oracle: COLS estándar + columna 'played'=True.
    Equipos: A..F (6 equipos). tournament="FIFA World Cup" para algunos.
    """
    rng = np.random.default_rng(seed)
    teams = ["ARG", "BRA", "FRA", "ESP", "GER", "ENG"]
    rows = []
    base = pd.Timestamp("2010-01-10")
    for i in range(n_hist):
        date = base + pd.Timedelta(days=i * 7)
        h, a = rng.choice(len(teams), 2, replace=False)
        hs = int(rng.poisson(1.4))
        as_ = int(rng.poisson(1.0))
        # Algunos partidos como World Cup
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
    return pd.DataFrame(rows)


def test_end_to_end_smoke():
    """paired_model_comparison devuelve resultados sensatos sobre datos sintéticos."""
    played_full = _synth_played(n_hist=45, seed=42)
    played_full["date"] = pd.to_datetime(played_full["date"])

    # held_out: últimos 6 partidos (todos tienen datos de entrenamiento previos)
    held_out = played_full.tail(6).copy().reset_index(drop=True)

    pc = paired_model_comparison(
        played_full, held_out,
        xi=0.0018,
        window_years=8,
        n_boot=200,
        seed=20260615,
    )

    # Propiedades básicas
    assert pc.n_common >= 0
    assert len(pc.delta) == pc.n_common

    if pc.n_common > 0:
        assert np.isfinite(pc.dep)
        assert np.isfinite(pc.se_paired)
        assert np.isfinite(pc.ep_full)
        assert np.isfinite(pc.ep_rho0)
        # delta = pf - pr, media de delta = dep
        assert pc.dep == pytest.approx(pc.delta.mean())

    # Atributos de BacktestResult accesibles
    assert hasattr(pc.r_full, "records")
    assert hasattr(pc.r_rho0, "records")
    assert pc.r_full.fit_rho is True
    assert pc.r_rho0.fit_rho is False
    assert pc.xi == 0.0018
