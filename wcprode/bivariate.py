"""bivariate.py — Poisson bivariado de Karlis-Ntzoufras (2003), Fase 3.

Modelo: X = W1 + W3, Y = W2 + W3, con Wi ~ Poisson(λi) independientes.
  log λ1 = attack_h - defence_a + γ·(1-neutral)
  log λ2 = attack_a - defence_h
  λ3 = covarianza común, escalar, bound [0, λ3_max].  Cov(X,Y) = λ3.

pmf cerrada: P(x,y) = Σ_{k=0}^{min(x,y)} Pois(k;λ3)·Pois(x-k;λ1)·Pois(y-k;λ2)
  (derivación directa de la construcción; algebraicamente idéntica a la fórmula
  del paper pero sin el denominador λ1·λ2, que genera inestabilidad para λi chicos).

Caso límite λ3=0 ⇒ doble-Poisson independiente = DixonColesEngine(fit_rho=False).

API bajo contrato (tests/test_bivariate_oracle.py):
  bivariate_pmf_grid(lam1, lam2, lam3, max_goals) -> np.ndarray (RAW, sin normalizar)
  BivariatePoissonEngine(xi, max_goals, lambda3_bounds, fit_lambda3)
    .fit(df, base_date, fit_since) -> self
    .predict(home, away, neutral) -> ScorelineGrid
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from wcprode.engine import ScorelineGrid, dixon_coles_weights

LOG_MEAN_CLIP = 30.0  # mismo clip que engine.py para estabilidad MLE


# --------------------------------------------------------------------------- #
# pmf de la grilla bivariada (función de módulo)                               #
# --------------------------------------------------------------------------- #
def bivariate_pmf_grid(
    lam1: float, lam2: float, lam3: float, max_goals: int
) -> np.ndarray:
    """Grilla RAW (sin normalizar), forma (max_goals+1, max_goals+1).

    grid[x, y] = P(X=x, Y=y) con X=W1+W3, Y=W2+W3 (construcción KN).

    pmf por convolución directa:
        P(x,y) = Σ_{k=0}^{min(x,y)} Pois(k;λ3)·Pois(x-k;λ1)·Pois(y-k;λ2)

    Con λ3=0 el único término superviviente es k=0, que da exactamente
    Pois(x;λ1)·Pois(y;λ2) → outer product de dos Poisson independientes.
    """
    mg = max_goals
    xs = np.arange(mg + 1)
    # Precomputo pmf de cada distribución en todos los goles posibles
    p1 = poisson.pmf(xs, lam1)   # Pois(·; λ1), longitud mg+1
    p2 = poisson.pmf(xs, lam2)   # Pois(·; λ2), longitud mg+1
    p3 = poisson.pmf(xs, lam3)   # Pois(·; λ3), longitud mg+1

    grid = np.zeros((mg + 1, mg + 1), dtype=float)

    # Bucle sobre k (componente compartida). Para cada k que contribuye,
    # la masa es p3[k] * outer( p1[x-k], p2[y-k] ) para x>=k, y>=k.
    for k in range(mg + 1):
        if p3[k] == 0.0:
            continue
        # índices válidos: x de k..mg, y de k..mg
        slice_x = p1[: mg + 1 - k]   # p1[0..mg-k] = Pois(x-k; λ1) para x=k..mg
        slice_y = p2[: mg + 1 - k]   # p2[0..mg-k] = Pois(y-k; λ2) para y=k..mg
        grid[k:, k:] += p3[k] * np.outer(slice_x, slice_y)

    return grid


# --------------------------------------------------------------------------- #
# Engine                                                                        #
# --------------------------------------------------------------------------- #
class BivariatePoissonEngine:
    """Poisson bivariado de Karlis-Ntzoufras (2003) con time-decay.

    Misma API que DixonColesEngine; reemplaza fit_rho/rho_ por fit_lambda3/lambda3_.
    """

    def __init__(
        self,
        xi: float = 0.0018,
        max_goals: int = 15,
        lambda3_bounds: tuple = (0.0, 1.0),
        fit_lambda3: bool = True,
    ):
        self.xi = xi
        self.max_goals = max_goals
        self.lambda3_bounds = lambda3_bounds
        self.fit_lambda3 = fit_lambda3
        # fitted attrs (None hasta fit)
        self.attack_: Optional[dict] = None
        self.defence_: Optional[dict] = None
        self.home_adv_: Optional[float] = None
        self.lambda3_: Optional[float] = None
        self.loglik_: Optional[float] = None
        self.teams_: Optional[list] = None

    # ---- preparación de arrays -------------------------------------------- #
    def _prepare(self, df: pd.DataFrame, base_date, fit_since):
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        if fit_since is not None:
            df = df[df["date"] >= pd.Timestamp(fit_since)].copy()
        if base_date is None:
            base_date = df["date"].max()
        base_date = pd.Timestamp(base_date)

        teams = sorted(set(df["home_team"]) | set(df["away_team"]))
        idx = {t: i for i, t in enumerate(teams)}

        hi = df["home_team"].map(idx).to_numpy()
        ai = df["away_team"].map(idx).to_numpy()
        x = df["home_score"].to_numpy(dtype=int)
        y = df["away_score"].to_numpy(dtype=int)
        # neutral semantics: γ aplica SOLO si NOT neutral
        home_flag = (~df["neutral"].astype(bool)).to_numpy(dtype=float)
        w = dixon_coles_weights(df["date"], self.xi, base_date)

        return teams, idx, hi, ai, x, y, home_flag, w

    # ---- desempaquetado del vector de parámetros --------------------------- #
    def _unpack(self, p: np.ndarray, n_teams: int):
        """p = [attack_0..attack_{N-2}, defence_0..defence_{N-1}, gamma, (lambda3)].

        attack tiene N-1 libres; el último = -sum(libres)  → mean(attack)=0 por
        construcción.  defence con N libres.  gamma escalar.  lambda3 opcional al final.
        """
        a_free = p[: n_teams - 1]
        attack = np.empty(n_teams)
        attack[: n_teams - 1] = a_free
        attack[-1] = -a_free.sum()
        defence = p[n_teams - 1 : 2 * n_teams - 1]
        gamma = p[2 * n_teams - 1]
        if self.fit_lambda3:
            lambda3 = float(p[2 * n_teams])
        else:
            lambda3 = 0.0
        return attack, defence, gamma, lambda3

    # ---- log-lik negativa + GRADIENTE ANALÍTICO (ecuaciones EM de KN) ------- #
    def _negloglik_and_grad(self, p: np.ndarray, n_teams: int, hi, ai, x, y, home_flag, w):
        """Log-lik ponderada NEGATIVA por convolución + su gradiente analítico exacto.

        P(x_m, y_m) = Σ_{k=0}^{min(x_m,y_m)} Pois(k;λ3)·Pois(x_m-k;λ1_m)·Pois(y_m-k;λ2_m)

        Gradiente (Karlis-Ntzoufras, vía la esperanza condicional de la componente compartida
        E_m = E[W3 | X=x_m, Y=y_m] = (Σ_k k·término_k)/P_m):
          ∂logP/∂logλ1 = (x - E_m) - λ1   ;   ∂logP/∂logλ2 = (y - E_m) - λ2
          ∂logP/∂λ3    = (Σ_k [Pois(k-1;λ3)-Pois(k;λ3)]·Pois(x-k;λ1)Pois(y-k;λ2)) / P_m
        La forma de diferencias para λ3 es estable en λ3=0 (NO divide por λ3). Con λ3=0 ⇒
        E_m=0 ⇒ ∂logP/∂logλ1=(x-λ1): idéntico a DC-ρ0. Propagación a attack/defence/γ vía
        bincount (misma estructura que engine.py). El gradiente ANALÍTICO es el que escala a
        cientos de equipos; el numérico no converge en esa dimensión (DECISIONS D10).
        """
        attack, defence, gamma, lambda3 = self._unpack(p, n_teams)
        log_l1 = np.clip(attack[hi] - defence[ai] + gamma * home_flag, -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        log_l2 = np.clip(attack[ai] - defence[hi], -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        l1 = np.exp(log_l1)
        l2 = np.exp(log_l2)
        n = len(x)
        mn = np.minimum(x, y)
        max_k = int(mn.max()) if n > 0 else 0

        prob = np.zeros(n)   # P_m = Σ_k término_k
        num = np.zeros(n)    # Σ_k k·término_k  (numerador de E_m)
        dP3 = np.zeros(n)    # ∂P_m/∂λ3 (forma de diferencias, estable en λ3=0)
        for k in range(max_k + 1):
            mask = k <= mn
            if not mask.any():
                break
            p3k = poisson.pmf(k, lambda3)
            rest = poisson.pmf(x[mask] - k, l1[mask]) * poisson.pmf(y[mask] - k, l2[mask])
            term = p3k * rest
            prob[mask] += term
            if k >= 1:
                num[mask] += k * term
            if self.fit_lambda3:
                p3km1 = poisson.pmf(k - 1, lambda3) if k >= 1 else 0.0
                dP3[mask] += (p3km1 - p3k) * rest

        P = np.maximum(prob, 1e-300)
        neg_ll = -(w * np.log(P)).sum()

        E = num / P                       # E[W3 | x, y]
        wg1 = w * ((x - E) - l1)          # w · ∂logP/∂logλ1
        wg2 = w * ((y - E) - l2)          # w · ∂logP/∂logλ2
        grad_attack_full = (np.bincount(hi, weights=wg1, minlength=n_teams)
                            + np.bincount(ai, weights=wg2, minlength=n_teams))
        grad_defence = -(np.bincount(ai, weights=wg1, minlength=n_teams)
                         + np.bincount(hi, weights=wg2, minlength=n_teams))
        grad_gamma = float((wg1 * home_flag).sum())
        # gauge attack[-1] = -Σ attack_free  ->  regla de la cadena (igual que engine.py)
        grad_attack_free = grad_attack_full[: n_teams - 1] - grad_attack_full[-1]
        grad_L = np.concatenate([grad_attack_free, grad_defence, np.array([grad_gamma])])
        if self.fit_lambda3:
            grad_L = np.concatenate([grad_L, np.array([float((w * (dP3 / P)).sum())])])
        return float(neg_ll), -grad_L  # minimizamos neg_ll -> gradiente de neg_ll = -grad_L

    # ---- fit --------------------------------------------------------------- #
    def fit(self, df, base_date=None, fit_since=None) -> "BivariatePoissonEngine":
        teams, idx, hi, ai, x, y, home_flag, w = self._prepare(df, base_date, fit_since)
        n_teams = len(teams)

        # Inicialización: attacks/defences en 0, gamma pequeño, lambda3 pequeño
        n_free = (n_teams - 1) + n_teams + 1  # N-1 attacks + N defences + gamma
        p0 = np.zeros(n_free)
        p0[2 * n_teams - 1] = 0.1  # gamma
        bounds = [(None, None)] * n_free

        if self.fit_lambda3:
            p0 = np.concatenate([p0, np.array([0.1])])   # lambda3 init
            bounds = bounds + [self.lambda3_bounds]

        res = minimize(
            self._negloglik_and_grad,
            p0,
            args=(n_teams, hi, ai, x, y, home_flag, w),
            jac=True,           # GRADIENTE ANALÍTICO (escala a cientos de equipos; D10)
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8},
        )

        attack, defence, gamma, lambda3 = self._unpack(res.x, n_teams)

        self.teams_ = teams
        self.attack_ = {t: float(attack[i]) for t, i in idx.items()}
        self.defence_ = {t: float(defence[i]) for t, i in idx.items()}
        self.home_adv_ = float(gamma)
        self.lambda3_ = 0.0 if not self.fit_lambda3 else float(lambda3)
        self.loglik_ = float(-res.fun)
        return self

    # ---- predict ----------------------------------------------------------- #
    def predict(self, home: str, away: str, neutral: bool = True) -> ScorelineGrid:
        if self.attack_ is None:
            raise RuntimeError("engine no fitteado: llamar fit() antes de predict()")
        for t in (home, away):
            if t not in self.attack_:
                raise ValueError(f"equipo no visto en el fit: {t!r}")

        home_term = 0.0 if neutral else self.home_adv_
        lam1 = np.exp(np.clip(
            self.attack_[home] - self.defence_[away] + home_term,
            -LOG_MEAN_CLIP, LOG_MEAN_CLIP,
        ))
        lam2 = np.exp(np.clip(
            self.attack_[away] - self.defence_[home],
            -LOG_MEAN_CLIP, LOG_MEAN_CLIP,
        ))
        lam3 = self.lambda3_

        raw = bivariate_pmf_grid(lam1, lam2, lam3, self.max_goals)
        total = raw.sum()
        assert total >= 0.999, (
            f"masa pre-normalización {total:.6f} < 0.999 — lambda explota "
            f"(lam1={lam1:.3f} lam2={lam2:.3f}); fail loud (spec §3.2)"
        )
        return ScorelineGrid(raw / total)
