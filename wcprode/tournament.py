"""tournament.py — Monte Carlo de torneo WC2026 -> marginales P(campeón)/P(subcampeón)
-> par óptimo de la Final Soñada. Segundo optimizador (docs/prode_rules.md §3.2,
docs/final_sonada_design.md).

ESQUELETO + DATOS VERIFICADOS. El orquestador fija: (1) la plantilla del bracket
(verificada por DIRECT_FETCH 2026-06-15, ver final_sonada_design.md §3.1), (2) los
contratos de API que el oráculo testea. El builder implementa los cuerpos marcados
`NotImplementedError` para que `tests/test_tournament_oracle.py` pase, SIN tocar:
  - las constantes de datos del bracket (R32_SLOTS, KO_FLOW, ELIGIBLE, ...)
  - las firmas públicas (el oráculo depende de ellas)

Decisiones de modelado (final_sonada_design.md §4, cerradas por JP 2026-06-15):
  - Localía en knockouts: TILT ANFITRIÓN por país de sede (regla venue-country).
  - Penales: 0.55 al favorito pre-partido.
  - N=50k default, reporte con SE.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# DATOS VERIFICADOS DEL BRACKET (NO MODIFICAR — DIRECT_FETCH 2026-06-15)       #
# Fuente: Wikipedia 2026_FIFA_World_Cup_knockout_stage oldid=1359418806 +      #
# Template ...third-place table oldid=1357614390. Ver final_sonada_design §3.1 #
# --------------------------------------------------------------------------- #
GROUP_LETTERS = list("ABCDEFGHIJKL")           # 12 grupos
HOSTS = {"United States", "Mexico", "Canada"}  # anfitriones (tilt de localía)
COUNTRY_HOST = {"USA": "United States", "MEX": "Mexico", "CAN": "Canada"}

# Orden de columnas-ganador del template Annex C (slots que hospedan un tercero)
WINNER_COLS = ["A", "B", "D", "E", "G", "I", "K", "L"]

# Set elegible de terceros por slot-ganador (verificado del bracket R32)
ELIGIBLE = {
    "A": set("CEFHI"), "B": set("EFGIJ"), "D": set("BEFIJ"), "E": set("ABCDF"),
    "G": set("AEHIJ"), "I": set("CDFGH"), "K": set("DEIJL"), "L": set("EHIJK"),
}

# Round of 32: match -> (slotA, slotB, venue_country)
# slot = ("W", g) ganador grupo g | ("R", g) subcampeón grupo g |
#        ("3", g) el tercero asignado al slot del ganador del grupo g (via Annex C)
R32_SLOTS = {
    73: (("R", "A"), ("R", "B"), "USA"),
    74: (("W", "E"), ("3", "E"), "USA"),
    75: (("W", "F"), ("R", "C"), "MEX"),
    76: (("W", "C"), ("R", "F"), "USA"),
    77: (("W", "I"), ("3", "I"), "USA"),
    78: (("R", "E"), ("R", "I"), "USA"),
    79: (("W", "A"), ("3", "A"), "MEX"),
    80: (("W", "L"), ("3", "L"), "USA"),
    81: (("W", "D"), ("3", "D"), "USA"),
    82: (("W", "G"), ("3", "G"), "USA"),
    83: (("R", "K"), ("R", "L"), "CAN"),
    84: (("W", "H"), ("R", "J"), "USA"),
    85: (("W", "B"), ("3", "B"), "CAN"),
    86: (("W", "J"), ("R", "H"), "USA"),
    87: (("W", "K"), ("3", "K"), "USA"),
    88: (("R", "D"), ("R", "G"), "USA"),
}

# Knockouts post-R32: match -> (feeder_match_1, feeder_match_2, venue_country).
# El ganador de cada feeder avanza. La final es 104 (se omite el 3er puesto, 103).
KO_FLOW = {
    89: (73, 75, "USA"), 90: (74, 77, "USA"), 91: (76, 78, "USA"), 92: (79, 80, "MEX"),
    93: (83, 84, "USA"), 94: (81, 82, "USA"), 95: (86, 88, "USA"), 96: (85, 87, "CAN"),
    97: (89, 90, "USA"), 98: (93, 94, "USA"), 99: (91, 92, "USA"), 100: (95, 96, "USA"),
    101: (97, 98, "USA"), 102: (99, 100, "USA"),
    104: (101, 102, "USA"),
}
FINAL_MATCH = 104

DEFAULT_PEN_WIN_PROB = 0.55
DEFAULT_N_SIMS = 50_000


# --------------------------------------------------------------------------- #
# Carga de la tabla Annex C (495 combinaciones)                               #
# --------------------------------------------------------------------------- #
def load_thirds_table(path: str | Path | None = None) -> dict:
    """Carga data/raw/wc2026_thirds_combinations.json -> lookup
    {frozenset(8 letras de grupo): {winner_group: third_group}}.

    Si path es None usa data/raw/wc2026_thirds_combinations.json del repo.
    """
    if path is None:
        repo_root = Path(__file__).parent.parent
        path = repo_root / "data" / "raw" / "wc2026_thirds_combinations.json"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return {
        frozenset(entry["groups"]): dict(entry["assign"])
        for entry in payload["combinations"]
    }


def assign_thirds_to_slots(qualifying_third_groups, table: dict) -> dict:
    """qualifying_third_groups: iterable de 8 letras de grupo (los grupos cuyo
    tercero clasificó). table: salida de load_thirds_table.
    Retorna {winner_group: third_group} (8 entradas). KeyError si la combinación
    de 8 grupos no existe en la tabla (no debería pasar: cubre las 495)."""
    return dict(table[frozenset(qualifying_third_groups)])


# --------------------------------------------------------------------------- #
# Standings de grupo (desempates WC2026 — head-to-head PRIMERO)               #
# --------------------------------------------------------------------------- #
def group_standings(matches, teams, rng=None) -> list:
    """Rankea `teams` (lista de 4 nombres) por los desempates WC2026 aplicados a
    `matches` (lista de (home, away, home_goals, away_goals) entre esos equipos).

    Orden de desempate (final_sonada_design §3.1, VERIFICADO — nuevo en 2026):
      1. Puntos totales
      2-4. Head-to-head entre empatados: puntos H2H -> GD H2H -> GF H2H
           (se reaplica al subconjunto que siga empatado)
      5. GD global
      6. GF global
      7. Fallback: moneda sembrada por `rng` (no tenemos fair-play ni ranking FIFA;
         estos empates profundos son raros y de efecto despreciable en las marginales).

    Retorna los 4 nombres ordenados 1°..4°. `rng` (np.random.Generator) solo se usa
    para el fallback #7; si es None y se necesita, romper el empate determinísticamente
    por nombre de equipo (documentar)."""
    # -- Stats globales -------------------------------------------------------
    pts = {t: 0 for t in teams}
    gd  = {t: 0 for t in teams}
    gf  = {t: 0 for t in teams}
    for home, away, hg, ag in matches:
        if home not in pts or away not in pts:
            continue
        gf[home] += hg
        gf[away] += ag
        gd[home] += hg - ag
        gd[away] += ag - hg
        if hg > ag:
            pts[home] += 3
        elif ag > hg:
            pts[away] += 3
        else:
            pts[home] += 1
            pts[away] += 1

    def rank_tied(tied: list) -> list:
        """Recursivo: rankea sub-bloque por desempates H2H luego global."""
        if len(tied) == 1:
            return tied

        tied_set = set(tied)
        h2h_pts = {t: 0 for t in tied}
        h2h_gd  = {t: 0 for t in tied}
        h2h_gf  = {t: 0 for t in tied}
        for home, away, hg, ag in matches:
            if home in tied_set and away in tied_set:
                h2h_gf[home] += hg
                h2h_gf[away] += ag
                h2h_gd[home] += hg - ag
                h2h_gd[away] += ag - hg
                if hg > ag:
                    h2h_pts[home] += 3
                elif ag > hg:
                    h2h_pts[away] += 3
                else:
                    h2h_pts[home] += 1
                    h2h_pts[away] += 1

        all_criteria = [h2h_pts, h2h_gd, h2h_gf, gd, gf]

        for crit in all_criteria:
            vals = sorted(set(crit[t] for t in tied), reverse=True)
            if len(vals) == 1:
                continue
            # Separación encontrada: partir en sub-bloques y recursión desde inicio
            result = []
            for v in vals:
                sub = [t for t in tied if crit[t] == v]
                result.extend(rank_tied(sub))
            return result

        # Fallback total
        if rng is not None:
            order = sorted(tied, key=lambda t: rng.random())
        else:
            order = sorted(tied)
        return order

    # -- Agrupar por puntos y rankear cada bloque -----------------------------
    pts_vals = sorted(set(pts[t] for t in teams), reverse=True)
    ranked = []
    for p in pts_vals:
        block = [t for t in teams if pts[t] == p]
        ranked.extend(rank_tied(block))
    return ranked


def best_thirds(records, rng=None) -> list:
    """records: dict {group_letter: (points, goal_diff, goals_for)} de los 12 terceros.
    Retorna las 8 mejores LETRAS de grupo, rankeadas por puntos -> GD -> GF -> fallback
    (moneda sembrada por rng; mismo caveat que group_standings)."""
    if rng is not None:
        letters = sorted(records.keys(), key=lambda g: (records[g][0], records[g][1], records[g][2], rng.random()), reverse=True)
    else:
        letters = sorted(records.keys(), key=lambda g: (records[g][0], records[g][1], records[g][2]), reverse=True)
    return letters[:8]


# --------------------------------------------------------------------------- #
# Resolución de un partido / penales                                          #
# --------------------------------------------------------------------------- #
def resolve_penalties(favorite: str, underdog: str, rng, p: float = DEFAULT_PEN_WIN_PROB) -> str:
    """Shootout: retorna `favorite` con probabilidad p, si no `underdog`.
    Convención (la fija el oráculo): favorite si rng.random() < p."""
    return favorite if rng.random() < p else underdog


def simulate_bracket(pairings, prob_provider, rng, *, neutral: bool = True,
                     pen_win_prob: float = DEFAULT_PEN_WIN_PROB) -> tuple:
    """Single-elimination genérico desde `pairings` (lista de (home, away) de la
    primera ronda; longitud potencia de 2). Juega rondas hasta un campeón.

    Cada partido: samplea un marcador de prob_provider(home, away, neutral).grid;
    si es empate, va a penales (favorito = mayor P(victoria) en 90/120 del grid;
    resolve_penalties con pen_win_prob). El ganador avanza emparejado en orden.

    `prob_provider`: callable (home, away, neutral) -> np.ndarray (grid P[h,a]
    normalizada). En producción: `lambda h,a,n: eng.predict(h,a,neutral=n).grid`.
    Para el helper genérico `neutral` es fijo.

    Retorna (champion, runnerup) = (ganador de la final, perdedor de la final)."""
    def play_match(home, away, is_neutral):
        grid = prob_provider(home, away, is_neutral)
        flat = grid.ravel()
        total = flat.sum()
        idx = rng.choice(flat.size, p=flat / total)
        h_g, a_g = np.unravel_index(idx, grid.shape)
        if h_g > a_g:
            return home, away
        elif a_g > h_g:
            return away, home
        else:
            # Empate -> penales
            # Favorito = mayor P(victoria en 90) = mayor masa bajo la diagonal
            p_home_win = np.tril(grid, -1).sum()
            p_away_win = np.triu(grid, 1).sum()
            if p_home_win >= p_away_win:
                favorite, underdog = home, away
            else:
                favorite, underdog = away, home
            winner = resolve_penalties(favorite, underdog, rng, pen_win_prob)
            loser = away if winner == home else home
            return winner, loser

    current_pairs = list(pairings)
    last_loser = None

    while True:
        winners = []
        losers = []
        for home, away in current_pairs:
            w, l = play_match(home, away, neutral)
            winners.append(w)
            losers.append(l)

        if len(winners) == 1:
            return winners[0], losers[0]

        # Remparejar ganadores consecutivos
        current_pairs = [(winners[i], winners[i + 1]) for i in range(0, len(winners), 2)]


# --------------------------------------------------------------------------- #
# Optimizador de asignación (Final Soñada)                                    #
# --------------------------------------------------------------------------- #
def final_sonada_pick(p_champion: dict, p_runnerup: dict) -> dict:
    """p_champion, p_runnerup: dict {team: prob}. Resuelve
        max 10*P(A=campeón) + 10*P(B=subcampeón)  con A != B
    por fuerza bruta. Retorna {"champion": A, "runnerup": B, "expected_points": v}."""
    best_val = -1.0
    best_a = None
    best_b = None
    for a, pc in p_champion.items():
        for b, pr in p_runnerup.items():
            if a == b:
                continue
            v = pc + pr
            if v > best_val:
                best_val = v
                best_a = a
                best_b = b
    return {"champion": best_a, "runnerup": best_b, "expected_points": 10.0 * best_val}


# --------------------------------------------------------------------------- #
# Simulador de torneo completo                                                 #
# --------------------------------------------------------------------------- #
class TournamentSimulator:
    """Monte Carlo del torneo completo condicionado en resultados parciales.

    Parámetros:
      groups: dict {group_letter: [4 nombres de equipo]} (los 12 grupos).
      played_results: lista de (home, away, hg, ag) de partidos de grupo YA jugados
                      (se fijan; el resto se samplea). Vacío = simular todo.
      remaining_fixtures: lista de (group_letter, home, away) de grupo NO jugados.
      thirds_table: salida de load_thirds_table.
      prob_provider: callable (home, away, neutral) -> np.ndarray (grid P[h,a] normalizada).
      hosts: set de nombres de equipos anfitriones (tilt de localía).
      pen_win_prob: 0.55.

    run(n_sims, seed) -> dict con:
      'champion': {team: P}, 'runnerup': {team: P}, 'reach_final': {team: P},
      'n_sims': int, 'se': {team: SE de P(campeón)}.

    Invariantes (oráculo Tier 3): sum(champion.values())==1, sum(runnerup.values())==1,
    champion[t]+runnerup[t]==reach_final[t] para todo t.

    Localía (Tier/knob): en un knockout en país C, el equipo == COUNTRY_HOST[C] juega de
    local (neutral=False, pasado como `home`); si ninguno es el anfitrión del país, neutral.
    Grupos: respetar el flag neutral del fixture (martj42) vía remaining_fixtures si se provee.
    """

    def __init__(self, groups, played_results, remaining_fixtures, thirds_table,
                 prob_provider, *, hosts=HOSTS, pen_win_prob=DEFAULT_PEN_WIN_PROB):
        self.groups = groups  # {letter: [t1, t2, t3, t4]}
        self.played_results = list(played_results)
        # remaining_fixtures: lista de (group_letter, home, away) o (group_letter, home, away, neutral)
        self._raw_fixtures = list(remaining_fixtures)
        self.thirds_table = thirds_table
        self.prob_provider = prob_provider
        self.hosts = hosts
        self.pen_win_prob = pen_win_prob

        # Precomputar a qué grupo pertenece cada equipo
        self._team_to_group = {}
        for letter, teams in groups.items():
            for t in teams:
                self._team_to_group[t] = letter

        # Precomputar host del país -> equipo anfitrión (para tilt)
        # COUNTRY_HOST: {"USA": "United States", "MEX": "Mexico", "CAN": "Canada"}
        self._country_host = COUNTRY_HOST  # ya importado como constante

    def _sample_scoreline(self, home, away, is_neutral, rng):
        """Samplea un marcador (hg, ag) de la grilla — sin penales (para grupos)."""
        grid = self.prob_provider(home, away, is_neutral)
        flat = grid.ravel()
        total = flat.sum()
        idx = rng.choice(flat.size, p=flat / total)
        h_g, a_g = np.unravel_index(idx, grid.shape)
        return int(h_g), int(a_g)

    def _play_ko_match(self, home, away, is_neutral, rng):
        """Juega un partido de knockout: samplea marcador; empate -> penales."""
        h_g, a_g = self._sample_scoreline(home, away, is_neutral, rng)
        if h_g > a_g:
            return home, away
        elif a_g > h_g:
            return away, home
        else:
            grid = self.prob_provider(home, away, is_neutral)
            p_home_win = np.tril(grid, -1).sum()
            p_away_win = np.triu(grid, 1).sum()
            if p_home_win >= p_away_win:
                favorite, underdog = home, away
            else:
                favorite, underdog = away, home
            winner = resolve_penalties(favorite, underdog, rng, self.pen_win_prob)
            loser = away if winner == home else home
            return winner, loser

    def _ko_teams_for_slot(self, slot, winner_map, runnerup_map, third_team_map):
        """Resuelve un slot R32 a un nombre de equipo."""
        slot_type, group = slot
        if slot_type == "W":
            return winner_map[group]
        elif slot_type == "R":
            return runnerup_map[group]
        else:  # "3"
            return third_team_map[group]

    def run(self, n_sims: int = DEFAULT_N_SIMS, seed: int = 0) -> dict:
        rng = np.random.default_rng(seed)

        # Todos los equipos (orden determinista para reproducibilidad)
        all_teams = []
        for letter in sorted(self.groups.keys()):
            all_teams.extend(self.groups[letter])

        champ_cnt   = {t: 0 for t in all_teams}
        runnerup_cnt = {t: 0 for t in all_teams}
        final_cnt   = {t: 0 for t in all_teams}

        # Precomputar fixtures por grupo
        fixtures_by_group = {letter: [] for letter in self.groups}
        for row in self._raw_fixtures:
            if len(row) == 3:
                g, h, a = row
                is_neutral = True
            else:
                g, h, a, is_neutral = row
            fixtures_by_group[g].append((h, a, is_neutral))

        # Clasificar played_results por grupo
        played_by_group = {letter: [] for letter in self.groups}
        for home, away, hg, ag in self.played_results:
            g = self._team_to_group.get(home)
            if g is not None:
                played_by_group[g].append((home, away, hg, ag))

        for _ in range(n_sims):
            winner_map   = {}  # letter -> equipo ganador del grupo
            runnerup_map = {}  # letter -> subcampeón
            third_team_map = {}  # letter -> 3° equipo (por letra del grupo)
            third_records  = {}  # letter -> (pts, gd, gf) del 3°

            # ---- Simular grupos ----
            for letter, teams in self.groups.items():
                # Matches fijos
                matches = list(played_by_group[letter])
                # Samplear remaining
                for h, a, is_neutral in fixtures_by_group[letter]:
                    hg, ag = self._sample_scoreline(h, a, is_neutral, rng)
                    matches.append((h, a, hg, ag))

                ranking = group_standings(matches, teams, rng)
                winner_map[letter]   = ranking[0]
                runnerup_map[letter] = ranking[1]
                third_name           = ranking[2]
                third_team_map[letter] = third_name

                # Calcular stats del 3° para best_thirds
                pts_t = {t: 0 for t in teams}
                gd_t  = {t: 0 for t in teams}
                gf_t  = {t: 0 for t in teams}
                for home, away, hg, ag in matches:
                    if home not in pts_t:
                        continue
                    gf_t[home] += hg
                    gf_t[away] += ag
                    gd_t[home] += hg - ag
                    gd_t[away] += ag - hg
                    if hg > ag:
                        pts_t[home] += 3
                    elif ag > hg:
                        pts_t[away] += 3
                    else:
                        pts_t[home] += 1
                        pts_t[away] += 1
                third_records[letter] = (pts_t[third_name], gd_t[third_name], gf_t[third_name])

            # ---- Mejores 8 terceros ----
            best8 = best_thirds(third_records, rng)  # lista de 8 letras
            assign = assign_thirds_to_slots(set(best8), self.thirds_table)

            # ---- Resolver slots R32 ----
            # assign: {winner_group_letter: third_group_letter}
            # R32_SLOTS: {match_num: (slotA, slotB, country)}
            ko_winners = {}  # match_num -> equipo ganador

            def get_team(slot):
                slot_type, group = slot
                if slot_type == "W":
                    return winner_map[group]
                elif slot_type == "R":
                    return runnerup_map[group]
                else:  # "3": group aquí es la letra del slot winner
                    # assign[group] nos da qué letra de grupo aportó el tercero
                    return third_team_map[assign[group]]

            def apply_home_tilt(teamA, teamB, country):
                host_team = self._country_host.get(country)
                if host_team is not None:
                    if teamA == host_team:
                        return teamA, teamB, False
                    elif teamB == host_team:
                        return teamB, teamA, False
                return teamA, teamB, True

            # Jugar R32
            for m, (slotA, slotB, country) in R32_SLOTS.items():
                tA = get_team(slotA)
                tB = get_team(slotB)
                home, away, is_neutral = apply_home_tilt(tA, tB, country)
                winner, _ = self._play_ko_match(home, away, is_neutral, rng)
                ko_winners[m] = winner

            # Jugar KO_FLOW en orden ascendente de clave
            champion = None
            runnerup = None
            for m in sorted(KO_FLOW.keys()):
                f1, f2, country = KO_FLOW[m]
                tA = ko_winners[f1]
                tB = ko_winners[f2]
                home, away, is_neutral = apply_home_tilt(tA, tB, country)
                winner, loser = self._play_ko_match(home, away, is_neutral, rng)
                ko_winners[m] = winner
                if m == FINAL_MATCH:
                    champion = winner
                    runnerup = loser

            champ_cnt[champion]    += 1
            runnerup_cnt[runnerup] += 1
            final_cnt[champion]    += 1
            final_cnt[runnerup]    += 1

        # Normalizar
        p_champ   = {t: champ_cnt[t] / n_sims for t in all_teams}
        p_run     = {t: runnerup_cnt[t] / n_sims for t in all_teams}
        p_final   = {t: final_cnt[t] / n_sims for t in all_teams}
        se        = {t: float(np.sqrt(p_champ[t] * (1 - p_champ[t]) / n_sims)) for t in all_teams}

        return {
            "champion":    p_champ,
            "runnerup":    p_run,
            "reach_final": p_final,
            "n_sims":      n_sims,
            "se":          se,
        }
