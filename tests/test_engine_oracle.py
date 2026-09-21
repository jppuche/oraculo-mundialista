"""Oraculo de correctitud del engine (O3-O6, O8, O9) — PRE-APROBADO POR DISENO + REVIEW 2026-06-10.

REGLA DURA (DECISIONS.md D2): los builders NO modifican este archivo.
Si un test parece incorrecto, el builder SE DETIENE Y ESCALA al orquestador; solo el
orquestador lo edita y el cambio queda logueado en DECISIONS.md. Ancla de inmutabilidad:
commit pre-build.

Cobertura: O3 reduccion Poisson | O4 cross-fit statsmodels (xi=0 y xi>0) | O5 referencia
externa dashee87 EPL 17/18 | O6 invariantes | O8 recovery sintetico (tau/rho/gamma) |
O9 pesos de decay. O1/O2 viven en los tests restaurados del
backup. O7 es script report-only del orquestador (spec §4), no pytest.

API bajo contrato (spec §3.2): wcprode.engine.{dixon_coles_weights, dc_scoreline_grid,
DixonColesEngine(xi, max_goals, rho_bounds, fit_rho).fit(df, base_date).predict(h, a, neutral)}
con fitted attrs .attack_ .defence_ .home_adv_ .rho_ .loglik_
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from wcprode.engine import DixonColesEngine, dc_scoreline_grid, dixon_coles_weights

DATA_RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
RNG_SEED = 20260610

# =====================================================================
# Generador de REFERENCIA — implementado del paper Dixon & Coles (1997),
# independiente del codigo bajo test. NO importa nada de wcprode.
# =====================================================================

def _tau_ref(h: int, a: int, lam: float, mu: float, rho: float) -> float:
    if h == 0 and a == 0:
        return 1.0 - lam * mu * rho
    if h == 1 and a == 0:
        return 1.0 + mu * rho
    if h == 0 and a == 1:
        return 1.0 + lam * rho
    if h == 1 and a == 1:
        return 1.0 - rho
    return 1.0


def _grid_ref(lam: float, mu: float, rho: float, max_goals: int = 12) -> np.ndarray:
    """Grilla RAW de referencia: outer de Poisson pmfs con tau en las 4 celdas."""
    gh = poisson.pmf(np.arange(max_goals + 1), lam)
    ga = poisson.pmf(np.arange(max_goals + 1), mu)
    g = np.outer(gh, ga)
    g[0, 0] *= 1.0 - lam * mu * rho
    g[1, 0] *= 1.0 + mu * rho
    g[0, 1] *= 1.0 + lam * rho
    g[1, 1] *= 1.0 - rho
    return g


def _loglik_ref(df: pd.DataFrame, attack: dict, defence: dict, gamma: float,
                rho: float, weights: np.ndarray) -> float:
    """Log-lik ponderada de referencia (sin terminos constantes log(y!))."""
    ll = 0.0
    for w, (_, r) in zip(weights, df.iterrows()):
        lam = np.exp(attack[r.home_team] - defence[r.away_team]
                     + (0.0 if r.neutral else gamma))
        mu = np.exp(attack[r.away_team] - defence[r.home_team])
        h, a = int(r.home_score), int(r.away_score)
        tau = max(_tau_ref(h, a, lam, mu, rho), 1e-10)
        ll += w * (np.log(tau) + h * np.log(lam) - lam + a * np.log(mu) - mu)
    return ll


def _make_synthetic(rng, attack: dict, defence: dict, gamma: float, rho: float,
                    n_home_rounds: int, n_neutral_rounds: int, date: str,
                    max_goals: int = 12) -> pd.DataFrame:
    """Partidos sinteticos muestreados de la pmf DC de referencia.
    Por par ordenado (i, j): n_home_rounds con localia + n_neutral_rounds neutrales."""
    teams = list(attack)
    rows = []
    cells = [(h, a) for h in range(max_goals + 1) for a in range(max_goals + 1)]
    for home in teams:
        for away in teams:
            if home == away:
                continue
            for neutral, n in ((False, n_home_rounds), (True, n_neutral_rounds)):
                if n == 0:
                    continue
                lam = np.exp(attack[home] - defence[away] + (0.0 if neutral else gamma))
                mu = np.exp(attack[away] - defence[home])
                g = _grid_ref(lam, mu, rho, max_goals)
                p = (g / g.sum()).ravel()
                counts = rng.multinomial(n, p)
                for idx in np.nonzero(counts)[0]:
                    h, a = cells[idx]
                    rows.extend([{
                        "date": date, "home_team": home, "away_team": away,
                        "home_score": h, "away_score": a, "neutral": neutral,
                    }] * counts[idx])
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _true_params(n_teams: int = 8):
    teams = [f"T{i}" for i in range(n_teams)]
    att = np.linspace(-0.4, 0.4, n_teams)
    att -= att.mean()
    dfc = np.linspace(0.35, -0.35, n_teams)
    dfc -= dfc.mean()
    attack = dict(zip(teams, att))
    defence = dict(zip(teams, dfc))
    return teams, attack, defence


# =====================================================================
# O3 — dc_scoreline_grid(rho=0) == outer product de Poisson pmfs
# =====================================================================

def test_o3_rho_zero_reduces_to_independent_poisson():
    lam, mu, mg = 1.45, 1.10, 15
    g = dc_scoreline_grid(lam, mu, 0.0, mg)
    expected = np.outer(poisson.pmf(np.arange(mg + 1), lam),
                        poisson.pmf(np.arange(mg + 1), mu))
    np.testing.assert_allclose(g, expected, rtol=1e-10)


# =====================================================================
# O6 — invariantes de la grilla y del fit
# =====================================================================

def test_o6_raw_grid_mass_tau_preserves_total():
    # La correccion tau preserva masa total exactamente; solo se pierde truncamiento.
    for lam, mu, rho in [(2.5, 1.8, -0.12), (0.9, 0.7, -0.12), (3.5, 0.5, -0.05)]:
        s = dc_scoreline_grid(lam, mu, rho, 15).sum()
        assert 0.999 <= s < 1.0 + 1e-12, f"masa {s} fuera de rango para {(lam, mu, rho)}"
        assert (dc_scoreline_grid(lam, mu, rho, 15) >= 0).all()


@pytest.fixture(scope="module")
def fitted_synthetic():
    """Fixture compartida O6/O8: engine fitted sobre sinteticos con params conocidos."""
    teams, attack, defence = _true_params()
    gamma, rho = 0.25, -0.12
    rng = np.random.default_rng(RNG_SEED)
    df = _make_synthetic(rng, attack, defence, gamma, rho,
                         n_home_rounds=320, n_neutral_rounds=80, date="2026-01-01")
    eng = DixonColesEngine(xi=0.0, fit_rho=True).fit(df, base_date=pd.Timestamp("2026-01-01"))
    return eng, df, attack, defence, gamma, rho


def test_o6_fit_directional_invariants(fitted_synthetic):
    eng, _, attack, _, _, _ = fitted_synthetic
    strong = max(attack, key=attack.get)
    weak = min(attack, key=attack.get)
    # Mas fuerte gana mas seguido (cancha neutral)
    assert eng.predict(strong, weak, neutral=True).p_home_win() > \
           eng.predict(weak, strong, neutral=True).p_home_win()
    # Localia sube P(home win) del mismo par
    assert eng.predict(strong, weak, neutral=False).p_home_win() > \
           eng.predict(strong, weak, neutral=True).p_home_win()
    # Grilla normalizada y no-negativa
    g = eng.predict(strong, weak, neutral=True).grid
    assert abs(g.sum() - 1.0) < 1e-9 and (g >= 0).all()


def test_o6_unknown_team_raises(fitted_synthetic):
    eng, *_ = fitted_synthetic
    with pytest.raises(ValueError):
        eng.predict("EQUIPO_INEXISTENTE", "T0", neutral=True)


# =====================================================================
# O8 — RECOVERY sobre sinteticos (cierra F1: el MLE completo CON tau)
# Un swap lambda/mu en tau, un signo en rho o una celda equivocada
# NO recuperan rho=-0.12 ni sobreviven al discriminador de log-lik.
# =====================================================================

def test_o8_parameter_recovery(fitted_synthetic):
    eng, df, attack, defence, gamma, rho = fitted_synthetic
    # ~22k partidos -> tolerancias holgadas vs error de muestreo (F3: no fallar espurio)
    assert abs(eng.rho_ - rho) < 0.04, f"rho no recuperado: {eng.rho_} vs {rho}"
    assert abs(eng.home_adv_ - gamma) < 0.05, f"gamma no recuperado: {eng.home_adv_} vs {gamma}"
    for t in attack:
        assert abs(eng.attack_[t] - attack[t]) < 0.08, f"attack[{t}]: {eng.attack_[t]} vs {attack[t]}"
        assert abs(eng.defence_[t] - defence[t]) < 0.08, f"defence[{t}]: {eng.defence_[t]} vs {defence[t]}"


def test_o8_loglik_discriminator(fitted_synthetic):
    """Afilado: bajo la log-lik de REFERENCIA, los params fitted deben puntuar >= que
    los TRUE (el MLE correcto maximiza esta funcion; un engine que maximiza una
    likelihood equivocada produce un argmax suboptimo aca y FALLA)."""
    eng, df, attack, defence, gamma, rho = fitted_synthetic
    w = np.ones(len(df))
    ll_fitted = _loglik_ref(df, eng.attack_, eng.defence_, eng.home_adv_, eng.rho_, w)
    ll_true = _loglik_ref(df, attack, defence, gamma, rho, w)
    assert ll_fitted >= ll_true - 1e-6 * abs(ll_true), \
        f"params fitted suboptimos bajo la likelihood de referencia: {ll_fitted} < {ll_true}"


# =====================================================================
# O9 — pesos de time-decay (cierra F2: el componente ~10x sin oraculo)
# =====================================================================

def test_o9a_weights_unit():
    base = pd.Timestamp("2026-06-10")
    ages = [0, 30, 385, 1500, 5000]
    dates = pd.to_datetime([base - pd.Timedelta(days=d) for d in ages])
    w = dixon_coles_weights(dates, xi=0.0018, base_date=base)
    assert abs(w[0] - 1.0) < 1e-12, "w(hoy) debe ser 1"
    assert all(w[i] > w[i + 1] for i in range(len(w) - 1)), \
        "pesos deben decrecer estrictamente con la edad del partido"
    # half-life = ln(2)/xi ~= 385.1 dias para xi=0.0018
    assert abs(w[2] - 0.5) < 0.01, f"w(385d) ~= 0.5, dio {w[2]}"


def test_o9b_two_eras_decay_direction():
    """Equipo X fuerte en era vieja, debil en la reciente. Con decay, el fit debe
    verlo debil. Una inversion de signo del exponente o de la direccion de
    Delta-dias pondera 2010 mas que 2025 y rompe este test."""
    teams, attack, defence = _true_params()
    x = teams[0]
    rng = np.random.default_rng(RNG_SEED + 1)
    att_old = dict(attack, **{x: 0.5})
    att_new = dict(attack, **{x: -0.5})
    df_old = _make_synthetic(rng, att_old, defence, 0.25, 0.0, 100, 0, "2010-06-01")
    df_new = _make_synthetic(rng, att_new, defence, 0.25, 0.0, 100, 0, "2025-06-01")
    df = pd.concat([df_old, df_new], ignore_index=True)
    base = pd.Timestamp("2026-06-10")
    flat = DixonColesEngine(xi=0.0, fit_rho=False).fit(df, base_date=base)
    decay = DixonColesEngine(xi=0.0018, fit_rho=False).fit(df, base_date=base)
    # peso era vieja ~ e^-10 ~ 5e-5 -> attack_X(decay) ~ -0.5; flat ~ promedio ~ 0
    assert decay.attack_[x] < flat.attack_[x] - 0.3, (
        f"decay no pondera lo reciente: attack_X flat={flat.attack_[x]:.3f} "
        f"decay={decay.attack_[x]:.3f}")


# =====================================================================
# O4 — cross-fit vs statsmodels Poisson GLM (rho=0; xi=0 y xi=0.0018)
# Universo definido por el TEST (F3): denso, sin separacion.
# =====================================================================

def _load_martj42_dense() -> pd.DataFrame:
    path = DATA_RAW / "results.csv"
    if not path.exists():
        pytest.fail("data/raw/results.csv ausente — T2a debe restaurarlo del backup y "
                    "verificar SHA contra sources.lock.json ANTES de correr O4 (spec P5).")
    df = pd.read_csv(path)
    df = df.dropna(subset=["home_score", "away_score"])
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= "2015-01-01"].copy()
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    # filtro a clausura: >=30 partidos por equipo DENTRO del universo final
    while True:
        counts = pd.concat([df.home_team, df.away_team]).value_counts()
        ok = set(counts[counts >= 30].index)
        keep = df.home_team.isin(ok) & df.away_team.isin(ok)
        if keep.all():
            break
        df = df[keep].copy()
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    return df.reset_index(drop=True)


def _statsmodels_fit(df: pd.DataFrame, weights: np.ndarray):
    try:
        import statsmodels.api as sm
    except ImportError:
        pytest.fail("statsmodels no instalado — dev-dep del oraculo O4. Instalarla VIA el "
                    "dependency-gate con su audit doc (spec §5); no esta en el allowlist a proposito.")
    teams = sorted(set(df.home_team) | set(df.away_team))
    t_idx = {t: i for i, t in enumerate(teams)}
    n_t = len(teams)
    n = len(df)
    # 2 filas por partido (goles del que ataca). Columnas: attack_t (+1 al anotador),
    # defence_t (-1 al que concede, gauge: defence del ultimo equipo fijada a 0), home.
    X = np.zeros((2 * n, n_t + (n_t - 1) + 1))
    y = np.empty(2 * n)
    w2 = np.repeat(weights, 2)
    for k, (_, r) in enumerate(df.iterrows()):
        hi, ai = t_idx[r.home_team], t_idx[r.away_team]
        rh, ra = 2 * k, 2 * k + 1
        y[rh], y[ra] = r.home_score, r.away_score
        X[rh, hi] = 1.0
        if ai < n_t - 1:
            X[rh, n_t + ai] = -1.0
        if not r.neutral:
            X[rh, -1] = 1.0
        X[ra, ai] = 1.0
        if hi < n_t - 1:
            X[ra, n_t + hi] = -1.0
    res = sm.GLM(y, X, family=sm.families.Poisson(), freq_weights=w2).fit()
    att = dict(zip(teams, res.params[:n_t]))
    dfc = {t: (res.params[n_t + t_idx[t]] if t_idx[t] < n_t - 1 else 0.0) for t in teams}
    gamma = res.params[-1]
    # alinear al gauge del engine: mean(attack)=0 (shift conjunto attack/defence)
    shift = np.mean(list(att.values()))
    att = {t: v - shift for t, v in att.items()}
    dfc = {t: v - shift for t, v in dfc.items()}
    return att, dfc, gamma


@pytest.mark.parametrize("xi", [0.0, 0.0018], ids=["xi0", "xi0018"])
def test_o4_crossfit_statsmodels(xi):
    df = _load_martj42_dense()
    base = df["date"].max()
    w = dixon_coles_weights(df["date"], xi=xi, base_date=base) if xi > 0 else np.ones(len(df))
    eng = DixonColesEngine(xi=xi, fit_rho=False).fit(df, base_date=base)
    att_sm, dfc_sm, gamma_sm = _statsmodels_fit(df, w)
    # Criterio robusto (F3): la log-lik de referencia de ambos sets debe coincidir
    # en rel 1e-6 (inmune a direcciones planas del parametro)
    ll_eng = _loglik_ref(df, eng.attack_, eng.defence_, eng.home_adv_, 0.0, w)
    ll_sm = _loglik_ref(df, att_sm, dfc_sm, gamma_sm, 0.0, w)
    assert abs(ll_eng - ll_sm) <= 1e-6 * abs(ll_sm), f"log-lik difiere: {ll_eng} vs {ll_sm}"
    assert ll_eng >= ll_sm - 1e-6 * abs(ll_sm), "el engine alcanzo peor maximo que statsmodels"
    # Params: atol 5e-3 (holgura por gtol de L-BFGS-B en direcciones planas; el
    # criterio primario es la log-lik de arriba)
    assert abs(eng.home_adv_ - gamma_sm) < 5e-3
    for t in att_sm:
        assert abs(eng.attack_[t] - att_sm[t]) < 5e-3, f"attack[{t}]"
        assert abs(eng.defence_[t] - dfc_sm[t]) < 5e-3, f"defence[{t}]"


# =====================================================================
# O5 — referencia externa: EPL 2017/18, ancla UNICA dashee87 (rho=-0.1285,
# fit sin decay). Banda heuristica +/-0.02. Bloqueante con escape declarado.
# =====================================================================

def test_o5_dashee87_epl_1718_reference():
    if os.environ.get("WCPRODE_WAIVE_O5") == "1":
        pytest.skip("O5 WAIVED explicitamente por JP (WCPRODE_WAIVE_O5=1) — queda logueado "
                    "como pendiente declarado; el veredicto de correctitud lo sostienen O4+O8.")
    path = DATA_RAW / "E0_1718.csv"
    if not path.exists():
        pytest.fail(
            "E0_1718.csv ausente. ESCALAR A JP (no pasar en silencio — spec §4 O5): "
            "fetch https://www.football-data.co.uk/mmz4281/1718/E0.csv -> data/raw/E0_1718.csv, "
            "registrar SHA256 en sources.lock.json (test_fixtures). "
            "Waiver solo via WCPRODE_WAIVE_O5=1 con OK explicito de JP.")
    raw = pd.read_csv(path)
    df = pd.DataFrame({
        "date": pd.to_datetime(raw["Date"], dayfirst=True),
        "home_team": raw["HomeTeam"], "away_team": raw["AwayTeam"],
        "home_score": raw["FTHG"].astype(int), "away_score": raw["FTAG"].astype(int),
        "neutral": False,
    })
    assert len(df) == 380, f"EPL 17/18 debe tener 380 partidos, hay {len(df)}"
    eng = DixonColesEngine(xi=0.0, fit_rho=True).fit(df, base_date=df["date"].max())
    assert -0.15 <= eng.rho_ <= -0.11, (
        f"rho={eng.rho_:.4f} fuera de la banda dashee87 [-0.15, -0.11] "
        f"(referencia -0.1285, mismo dataset, sin decay)")
