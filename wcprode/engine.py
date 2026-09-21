"""engine.py — Dixon-Coles + time-decay, in-house (numpy/scipy puro).

Modelo (Dixon & Coles 1997, implementacion in-house §3.1):
  log lambda_home = attack_i - defence_j + gamma * (1 - neutral)
  log mu_away     = attack_j - defence_i
  tau (Dixon & Coles 1997) sobre las 4 celdas de baja puntuacion:
    tau(0,0)=1-lam*mu*rho  tau(1,0)=1+mu*rho  tau(0,1)=1+lam*rho  tau(1,1)=1-rho
  log-lik ponderada: sum_m w_m [log tau_m + x_m log lam_m - lam_m + y_m log mu_m - mu_m]
  pesos w_m = exp(-xi * dias(base_date - date_m))

Identificabilidad: el unico gauge es el shift conjunto (attack+c, defence+c), que deja
lambda/mu invariantes. Se fija con mean(attack)=0 (una sola constraint basta). En el
optimizador se reparametriza: N-1 attacks libres + el ultimo reconstruido como -sum(otros),
de modo que mean(attack)=0 se cumple por construccion. defence queda con N libres.

Performance (spec): log-lik vectorizada (numpy sobre arrays de partidos) + GRADIENTE
ANALITICO para attacks/defences/gamma (derivada Poisson estandar + correccion tau, 4
celdas). rho se trata con gradiente numerico (1-D, barato) para mantener L-BFGS-B rapido
sobre el universo denso de O4 (cientos de equipos).

Clip de tau DENTRO de la log-lik: tau = max(tau, 1e-10). Sin esto L-BFGS-B
produce NaN mid-optimizacion con 0-0 observados entre rivales dispares; el bound de caja
rho in [-0.2, 0.2] NO alcanza. El clip es obligatorio: el bound de caja no mantiene la likelihood finita.

API bajo contrato (tests/test_engine_oracle.py):
  dixon_coles_weights(dates, xi, base_date) -> np.ndarray
  dc_scoreline_grid(lam, mu, rho, max_goals) -> np.ndarray (RAW, sin normalizar)
  DixonColesEngine(xi, max_goals, rho_bounds, fit_rho).fit(df, base_date, fit_since)
    -> attrs .attack_ .defence_ .home_adv_ .rho_ .loglik_
  .predict(home, away, neutral) -> ScorelineGrid(.grid, p_home_win/p_draw/p_away_win)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

TAU_FLOOR = 1e-10
# Clip de los log-means antes de exp: estabilidad numerica del MLE Poisson.
# El optimizador puede explorar puntos transitorios con attack-defence+gamma grande
# (overflow -> lam=inf -> neg_ll=nan -> gradiente corrupto que descarrila L-BFGS-B,
# convergencia suboptima vista en el fit pre-2018 del backtest O7). El optimo real de
# datos de futbol tiene log-means < ~3, asi que clipear a +/-30 (lam ~ 1e13) NO altera
# el optimo, solo evita el inf/nan en la exploracion. Estandar en implementaciones MLE.
LOG_MEAN_CLIP = 30.0


# --------------------------------------------------------------------------- #
# Funciones de modulo                                                          #
# --------------------------------------------------------------------------- #
def dixon_coles_weights(dates, xi: float, base_date) -> np.ndarray:
    """w_m = exp(-xi * dias(base_date - date_m)).

    w(base_date) = 1, decreciente estrictamente hacia el pasado. dias se mide en
    timedeltas reales (no aritmetica entera) sobre la diferencia base_date - date.
    """
    d = pd.to_datetime(pd.Series(list(dates)).values)
    base = pd.Timestamp(base_date)
    age_days = (base - d) / np.timedelta64(1, "D")
    return np.exp(-xi * np.asarray(age_days, dtype=float))


def _tau_grid_correction(lam: float, mu: float, rho: float):
    """Multiplicadores tau para las 4 celdas (0,0),(1,0),(0,1),(1,1)."""
    return (
        1.0 - lam * mu * rho,   # (0,0)
        1.0 + mu * rho,         # (1,0)
        1.0 + lam * rho,        # (0,1)
        1.0 - rho,              # (1,1)
    )


def dc_scoreline_grid(lam: float, mu: float, rho: float, max_goals: int) -> np.ndarray:
    """Grilla RAW (sin normalizar): outer de Poisson pmfs con tau en las 4 celdas.

    grid[h, a] = Poisson(h; lam) * Poisson(a; mu) * tau(h, a). max_goals incluido,
    asi que la forma es (max_goals+1, max_goals+1). La correccion tau preserva masa
    total exactamente; la unica perdida (grilla suma < 1) es por truncamiento.
    """
    gh = poisson.pmf(np.arange(max_goals + 1), lam)
    ga = poisson.pmf(np.arange(max_goals + 1), mu)
    g = np.outer(gh, ga)
    t00, t10, t01, t11 = _tau_grid_correction(lam, mu, rho)
    g[0, 0] *= t00
    g[1, 0] *= t10
    g[0, 1] *= t01
    g[1, 1] *= t11
    return g


# --------------------------------------------------------------------------- #
# Grilla de prediccion (objeto de salida)                                      #
# --------------------------------------------------------------------------- #
class ScorelineGrid:
    """Grilla P(home=h, away=a) NORMALIZADA. grid[h, a] = probabilidad."""

    __slots__ = ("grid",)

    def __init__(self, grid: np.ndarray):
        self.grid = grid

    def p_home_win(self) -> float:
        return float(np.tril(self.grid, -1).sum())

    def p_draw(self) -> float:
        return float(np.trace(self.grid))

    def p_away_win(self) -> float:
        return float(np.triu(self.grid, 1).sum())


# --------------------------------------------------------------------------- #
# Engine                                                                        #
# --------------------------------------------------------------------------- #
class DixonColesEngine:
    def __init__(self, xi: float = 0.0018, max_goals: int = 15,
                 rho_bounds: tuple = (-0.2, 0.2), fit_rho: bool = True):
        self.xi = xi
        self.max_goals = max_goals
        self.rho_bounds = rho_bounds
        self.fit_rho = fit_rho
        # fitted attrs (None hasta fit)
        self.attack_: dict | None = None
        self.defence_: dict | None = None
        self.home_adv_: float | None = None
        self.rho_: float | None = None
        self.loglik_: float | None = None
        self.teams_: list | None = None

    # ---- preparacion de arrays --------------------------------------------- #
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
        x = df["home_score"].to_numpy(dtype=float)     # goles home
        y = df["away_score"].to_numpy(dtype=float)     # goles away
        # neutral semantics: gamma aplica SOLO si NOT neutral
        home_flag = (~df["neutral"].astype(bool)).to_numpy(dtype=float)
        w = dixon_coles_weights(df["date"], self.xi, base_date)

        return teams, idx, hi, ai, x, y, home_flag, w

    # ---- desempaquetado del vector de parametros --------------------------- #
    def _unpack(self, p, n_teams):
        """p = [attack_0 .. attack_{N-2}, defence_0 .. defence_{N-1}, gamma, (rho)].

        attack tiene N-1 libres; el ultimo = -sum(libres) (mean(attack)=0 por
        construccion). defence con N libres. gamma escalar. rho opcional al final.
        """
        a_free = p[: n_teams - 1]
        attack = np.empty(n_teams)
        attack[: n_teams - 1] = a_free
        attack[-1] = -a_free.sum()
        defence = p[n_teams - 1: 2 * n_teams - 1]
        gamma = p[2 * n_teams - 1]
        if self.fit_rho:
            rho = p[2 * n_teams]
        else:
            rho = 0.0
        return attack, defence, gamma, rho

    # ---- log-lik negativa vectorizada + gradiente analitico ---------------- #
    def _negloglik_and_grad(self, p, n_teams, hi, ai, x, y, home_flag, w):
        attack, defence, gamma, rho = self._unpack(p, n_teams)

        log_lam = np.clip(attack[hi] - defence[ai] + gamma * home_flag,
                          -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        log_mu = np.clip(attack[ai] - defence[hi], -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        lam = np.exp(log_lam)
        mu = np.exp(log_mu)

        # --- termino Poisson de la log-lik ---
        ll_poisson = w * (x * log_lam - lam + y * log_mu - mu)

        # --- correccion tau (solo en partidos cuyo marcador cae en las 4 celdas) ---
        # tau depende de lam, mu, rho. Calculamos tau por partido segun (x,y).
        tau = np.ones_like(lam)
        # mascaras de las 4 celdas
        m00 = (x == 0) & (y == 0)
        m10 = (x == 1) & (y == 0)
        m01 = (x == 0) & (y == 1)
        m11 = (x == 1) & (y == 1)
        tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
        tau[m10] = 1.0 + mu[m10] * rho
        tau[m01] = 1.0 + lam[m01] * rho
        tau[m11] = 1.0 - rho
        # clip dentro de la log-lik — evita log(<=0) = NaN (el bound de caja no alcanza)
        clipped = tau <= TAU_FLOOR        # celdas donde el clip se activo
        tau_clip = np.maximum(tau, TAU_FLOOR)
        ll_tau = w * np.log(tau_clip)

        neg_ll = -(ll_poisson.sum() + ll_tau.sum())

        # ===================== GRADIENTE ANALITICO ===========================
        # d(loglik)/d(log_lam) por partido:
        #   Poisson: w*(x - lam)
        #   tau:     w * (1/tau) * d tau / d log_lam   (solo donde tau != 1)
        # d tau/d log_lam = d tau/d lam * lam:
        #   (0,0): -mu*rho*lam ; (0,1): rho*lam ; (1,0),(1,1): 0
        # d tau/d log_mu = d tau/d mu * mu:
        #   (0,0): -lam*rho*mu ; (1,0): rho*mu ; (0,1),(1,1): 0
        # CONSISTENCIA DEL CLIP: donde tau<=TAU_FLOOR la loglik usa log(TAU_FLOOR)
        # constante -> su derivada es 0. inv_tau debe anularse ahi, o el gradiente
        # explota (w/1e-10 ~ 1e10) e inconsistente con la funcion clipeada -> L-BFGS-B
        # devuelve ABNORMAL. Sin esta mascara el fit full descarrila (status 2).
        inv_tau = np.where(clipped, 0.0, w / tau_clip)

        g_loglam = w * (x - lam)
        g_logmu = w * (y - mu)

        # contribuciones tau a g_loglam
        dll_dloglam = np.zeros_like(lam)
        dll_dloglam[m00] = -mu[m00] * rho * lam[m00]
        dll_dloglam[m01] = rho * lam[m01]
        g_loglam = g_loglam + inv_tau * dll_dloglam

        # contribuciones tau a g_logmu
        dll_dlogmu = np.zeros_like(mu)
        dll_dlogmu[m00] = -lam[m00] * rho * mu[m00]
        dll_dlogmu[m10] = rho * mu[m10]
        g_logmu = g_logmu + inv_tau * dll_dlogmu

        # --- propagar a attack/defence/gamma ---
        # log_lam = attack[hi] - defence[ai] + gamma*home_flag
        # log_mu  = attack[ai] - defence[hi]
        # d/d attack[t]:  +g_loglam donde hi==t  +g_logmu donde ai==t
        # d/d defence[t]: -g_loglam donde ai==t  -g_logmu donde hi==t
        # d/d gamma:      sum(g_loglam * home_flag)
        grad_attack_full = (
            np.bincount(hi, weights=g_loglam, minlength=n_teams)
            + np.bincount(ai, weights=g_logmu, minlength=n_teams)
        )
        grad_defence = -(
            np.bincount(ai, weights=g_loglam, minlength=n_teams)
            + np.bincount(hi, weights=g_logmu, minlength=n_teams)
        )
        grad_gamma = float((g_loglam * home_flag).sum())

        # attack[-1] = -sum(attack_free) -> regla de la cadena:
        # d L/d a_free_k = grad_attack_full[k] - grad_attack_full[N-1]
        grad_attack_free = grad_attack_full[: n_teams - 1] - grad_attack_full[-1]

        # grad_* arriba son gradientes de la LOGLIK (positiva). Como minimizamos
        # neg_ll, el gradiente que devolvemos es -grad para attack/defence/gamma.
        grad_loglik = np.concatenate([
            grad_attack_free,
            grad_defence,
            np.array([grad_gamma]),
        ])
        grad_negll = -grad_loglik

        if self.fit_rho:
            # rho: GRADIENTE ANALITICO (todo el gradiente analitico -> consistente,
            # sin la inestabilidad del numerico que descarrilaba L-BFGS-B).
            # d(loglik)/d rho = sum_m w_m * (1/tau_m) * d tau_m / d rho
            # d tau/d rho por celda: (0,0): -lam*mu ; (1,0): mu ; (0,1): lam ; (1,1): -1
            dtau_drho = np.zeros_like(lam)
            dtau_drho[m00] = -lam[m00] * mu[m00]
            dtau_drho[m10] = mu[m10]
            dtau_drho[m01] = lam[m01]
            dtau_drho[m11] = -1.0
            grad_rho_loglik = float((inv_tau * dtau_drho).sum())
            grad_negll = np.concatenate([grad_negll, np.array([-grad_rho_loglik])])

        return neg_ll, grad_negll

    def _negloglik_only(self, p, n_teams, hi, ai, x, y, home_flag, w) -> float:
        attack, defence, gamma, rho = self._unpack(p, n_teams)
        log_lam = np.clip(attack[hi] - defence[ai] + gamma * home_flag,
                          -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        log_mu = np.clip(attack[ai] - defence[hi], -LOG_MEAN_CLIP, LOG_MEAN_CLIP)
        lam = np.exp(log_lam)
        mu = np.exp(log_mu)
        ll_poisson = w * (x * log_lam - lam + y * log_mu - mu)
        tau = np.ones_like(lam)
        m00 = (x == 0) & (y == 0)
        m10 = (x == 1) & (y == 0)
        m01 = (x == 0) & (y == 1)
        m11 = (x == 1) & (y == 1)
        tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
        tau[m10] = 1.0 + mu[m10] * rho
        tau[m01] = 1.0 + lam[m01] * rho
        tau[m11] = 1.0 - rho
        tau_clip = np.maximum(tau, TAU_FLOOR)
        ll = ll_poisson.sum() + (w * np.log(tau_clip)).sum()
        return -ll

    # ---- fit --------------------------------------------------------------- #
    def fit(self, df, base_date=None, fit_since=None) -> "DixonColesEngine":
        teams, idx, hi, ai, x, y, home_flag, w = self._prepare(df, base_date, fit_since)
        n_teams = len(teams)

        # init: attacks/defences en 0, gamma pequeno positivo, rho 0
        n_free = (n_teams - 1) + n_teams + 1
        p0 = np.zeros(n_free)
        p0[2 * n_teams - 1] = 0.1  # gamma
        bounds = [(None, None)] * n_free
        if self.fit_rho:
            p0 = np.concatenate([p0, np.array([0.0])])
            bounds = bounds + [self.rho_bounds]

        res = minimize(
            self._negloglik_and_grad,
            p0,
            args=(n_teams, hi, ai, x, y, home_flag, w),
            jac=True,
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": 1000, "ftol": 1e-12, "gtol": 1e-8},
        )

        attack, defence, gamma, rho = self._unpack(res.x, n_teams)
        self.teams_ = teams
        self.attack_ = {t: float(attack[i]) for t, i in idx.items()}
        self.defence_ = {t: float(defence[i]) for t, i in idx.items()}
        self.home_adv_ = float(gamma)
        self.rho_ = float(rho)
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
        lam = np.exp(self.attack_[home] - self.defence_[away] + home_term)
        mu = np.exp(self.attack_[away] - self.defence_[home])

        raw = dc_scoreline_grid(lam, mu, self.rho_, self.max_goals)
        total = raw.sum()
        assert total >= 0.999, (
            f"masa pre-normalizacion {total:.6f} < 0.999 — lambda/mu explotaron "
            f"(lam={lam:.3f} mu={mu:.3f}); fail loud (spec §3.2)"
        )
        return ScorelineGrid(raw / total)
