"""score_matchday.py — scorea predicciones del prode contra resultados reales.

Reusable para cualquier matchday: toma un archivo de predicciones (.txt, formato
predict_matchday.py) y un archivo de actuals (.md, tabla bajo heading
'## Resultados') y emite tabla de puntos + reporte markdown.

Uso:
  .venv/Scripts/python.exe scripts/score_matchday.py \\
      --predictions predictions/groups_full_2026-06-10.txt \\
      --actuals data/actuals_2026-06-15.md \\
      --out predictions/scored_2026-06-15.md
"""
import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Aseguramos que wcprode sea importable desde cualquier CWD
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wcprode.scoring import match_points  # noqa: E402

# ---------------------------------------------------------------------------
# Mapeo de nombres: marcador → nombre martj42 (en nuestras predicciones)
# Extendible: agregar entradas según aparezcan discrepancias futuras
# ---------------------------------------------------------------------------
ACTUAL_NAME_MAP = {
    "Czechia": "Czech Republic",
    "USA": "United States",
    "Türkiye": "Turkey",
}


# ---------------------------------------------------------------------------
# Parseo de predicciones
# ---------------------------------------------------------------------------
# Regex: fecha  local(con espacios)  goles_h-goles_a  visitante(con espacios)  EV=
# El score \d+-\d+ es el ancla; .+? non-greedy captura equipos con espacios.
PRED_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})\s+(.+?)\s+(\d+)-(\d+)\s+(.+?)\s+EV=([\d.]+)",
)

# Probabilidades 1X2 (a 120' en KO). Se usan SOLO para derivar el favorito de la tanda
# en un pick de empate (pen_pred). Opcional: si la línea no las trae, pen_pred queda None.
PROB_RE = re.compile(r"\[H ([\d.]+) D ([\d.]+) A ([\d.]+)\]")


def parse_predictions(path: Path) -> dict:
    """Retorna dict {(home, away): {date, pred_h, pred_a, ev}} ."""
    preds = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            m = PRED_RE.match(line)
            if not m:
                continue
            date, home, gh, ga, away, ev = (
                m.group(1), m.group(2).strip(), int(m.group(3)),
                int(m.group(4)), m.group(5).strip(), float(m.group(6)),
            )
            pm = PROB_RE.search(line)
            p_home = float(pm.group(1)) if pm else None
            p_away = float(pm.group(3)) if pm else None
            preds[(home, away)] = dict(date=date, pred_h=gh, pred_a=ga, ev=ev,
                                       p_home=p_home, p_away=p_away)
    return preds


# ---------------------------------------------------------------------------
# Parseo de actuals desde .md
# ---------------------------------------------------------------------------
def parse_actuals(path: Path) -> list[dict]:
    """
    Parsea SOLO la tabla bajo el heading '## Resultados'.
    Columnas: Fecha | Grupo | Local | GL | GV | Visitante | Nota
    Retorna lista de dicts con claves: home, away, real_h, real_a, provisional.
    IGNORA tablas subsiguientes (e.g. 'Sanity preview').
    """
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Extraemos solo el bloque entre '## Resultados' y el siguiente heading '##'
    block_match = re.search(
        r"^## Resultados.*?\n(.*?)(?=^##|\Z)",
        content, re.MULTILINE | re.DOTALL
    )
    if not block_match:
        raise ValueError(f"No se encontró el heading '## Resultados' en {path}")

    block = block_match.group(1)

    # Encontramos la tabla que tiene columnas Local/GL/GV/Visitante
    # Identificamos la línea header
    rows = []
    in_table = False
    header_found = False

    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            if in_table:
                break  # terminó la tabla
            continue

        # Es una línea de tabla
        if not header_found:
            # Buscamos el header: contiene "Local" y "Visitante"
            if "Local" in stripped and "Visitante" in stripped:
                header_found = True
                in_table = True
                # Guardamos posición de columnas
                cols = [c.strip() for c in stripped.split("|")]
                # cols[0] = '' (antes del primer |), luego Fecha, Grupo, Local, GL, GV, Visitante, Nota
                # Mapeamos índice (base 1, ignorando cols[0])
                col_names = [c for c in cols if c]  # Fecha Grupo Local GL GV Visitante Nota
                idx = {name: i for i, name in enumerate(col_names)}
            continue

        # Salteamos línea separadora (|---|)
        if re.match(r"\|[-| :]+\|", stripped):
            continue

        # Fila de datos
        parts = [c.strip() for c in stripped.split("|")]
        parts = [p for p in parts if p is not None]  # quitar vacíos de bordes
        # parts tiene un '' al inicio si la línea empieza con |
        # Removemos el primero si está vacío
        if parts and parts[0] == "":
            parts = parts[1:]
        if parts and parts[-1] == "":
            parts = parts[:-1]

        if len(parts) < len(col_names):
            continue  # fila incompleta, saltar

        home_raw = parts[idx["Local"]]
        away_raw = parts[idx["Visitante"]]
        try:
            real_h = int(parts[idx["GL"]])
            real_a = int(parts[idx["GV"]])
        except (ValueError, IndexError):
            continue

        nota = parts[idx["Nota"]] if "Nota" in idx and idx["Nota"] < len(parts) else ""
        provisional = "PROVISIONAL" in nota.upper()

        # Ganador de la tanda de penales (KO): Nota "pen: <equipo>" (prode_rules §1.4).
        # Vacío si el partido no fue a penales. Nombre canónico (mismo name-map).
        m_pen = re.search(r"pen:\s*(.+?)\s*$", nota)
        pen_winner_raw = m_pen.group(1).strip() if m_pen else ""
        pen_winner = ACTUAL_NAME_MAP.get(pen_winner_raw, pen_winner_raw)

        # Aplicamos mapeo de nombres
        home = ACTUAL_NAME_MAP.get(home_raw, home_raw)
        away = ACTUAL_NAME_MAP.get(away_raw, away_raw)

        rows.append(dict(
            home=home, away=away,
            real_h=real_h, real_a=real_a,
            provisional=provisional,
            home_raw=home_raw, away_raw=away_raw,
            pen_winner=pen_winner,
        ))

    return rows


# ---------------------------------------------------------------------------
# Join, scoring, y reporte
# ---------------------------------------------------------------------------
def outcome_str(h: int, a: int) -> str:
    if h > a:
        return "H"
    elif a > h:
        return "A"
    return "D"


def penalty_pred_actual(pred_h, pred_a, p_home, p_away, pen_winner, home, away):
    """(pen_pred, pen_actual) para match_points — prode_rules §1.4.

    El +5 de penales SOLO lo accede un pick de EMPATE (`pred_h == pred_a`). En ese caso:
    - pen_pred = favorito de la tanda = el equipo con mayor P a 120' ("H"/"A"), mismo
      criterio que el optimizer con pen_win_prob=0.55. None si la línea no trae probs.
    - pen_actual = ganador real de la tanda ("H"/"A"), derivado de `pen_winner` (nombre del
      equipo, de la Nota "pen: X"); None si el partido no fue a penales.
    Para un pick no-empate devuelve (None, None): el +5 no está en juego (el bonus del prode
    solo se ofrece si predecís empate).
    """
    if pred_h != pred_a:
        return None, None
    pen_pred = None
    if p_home is not None and p_away is not None:
        pen_pred = "H" if p_home >= p_away else "A"
    pen_actual = None
    if pen_winner and pen_winner == home:
        pen_actual = "H"
    elif pen_winner and pen_winner == away:
        pen_actual = "A"
    return pen_pred, pen_actual


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Scorea predicciones del prode contra resultados reales."
    )
    ap.add_argument("--predictions", required=True,
                    help="Ruta al .txt de predicciones (predict_matchday.py output)")
    ap.add_argument("--actuals", required=True,
                    help="Ruta al .md de resultados reales")
    ap.add_argument("--out", required=True,
                    help="Ruta de salida del reporte .md")
    ap.add_argument("--label", default="matchday",
                    help="Etiqueta de la fecha para el título/notas, e.g. 'Fecha 2'")
    args = ap.parse_args()

    pred_path = Path(args.predictions)
    actual_path = Path(args.actuals)
    out_path = Path(args.out)

    # --- carga ---
    preds = parse_predictions(pred_path)
    actuals = parse_actuals(actual_path)

    print(f"Predicciones cargadas: {len(preds)} fixtures")
    print(f"Actuals parseados:     {len(actuals)} partidos\n")

    # --- join y scoring ---
    results = []
    missing_preds = []

    for act in actuals:
        key = (act["home"], act["away"])
        if key not in preds:
            missing_preds.append(f"  FALTA predicción para: {act['home']} vs {act['away']}"
                                 f" (raw: {act['home_raw']} vs {act['away_raw']})")
            continue

        p = preds[key]
        pred_h, pred_a = p["pred_h"], p["pred_a"]
        real_h, real_a = act["real_h"], act["real_a"]

        # Penales (prode_rules §1.4): el +5 SOLO se acredita a un pick de EMPATE que fue a
        # la tanda y acertó al ganador. Derivación aislada + testeada (penalty_pred_actual).
        pen_pred, pen_actual = penalty_pred_actual(
            pred_h, pred_a, p.get("p_home"), p.get("p_away"),
            act.get("pen_winner", ""), act["home"], act["away"])
        pts = match_points((pred_h, pred_a), (real_h, real_a),
                           pen_pred=pen_pred, pen_actual=pen_actual)

        pred_outcome = outcome_str(pred_h, pred_a)
        real_outcome = outcome_str(real_h, real_a)
        outcome_ok = "✓" if pred_outcome == real_outcome else "✗"
        goal_match = "✓" if (pred_h == real_h or pred_a == real_a) else "✗"
        prov = "⚠ PROV" if act["provisional"] else ""
        pen_involved = (pred_h == pred_a and act.get("pen_winner", "") != "")
        pen_bonus = (pen_involved and pen_pred is not None
                     and pen_actual is not None and pen_pred == pen_actual)

        results.append(dict(
            date=p["date"],
            home=act["home"], away=act["away"],
            pred=f"{pred_h}-{pred_a}", real=f"{real_h}-{real_a}",
            outcome_ok=outcome_ok, goal_match=goal_match,
            pts=pts, ev=p["ev"],
            pts_minus_ev=round(pts - p["ev"], 2),
            provisional=act["provisional"],
            prov_label=prov,
            pen_pred=pen_pred, pen_actual=pen_actual,
            pen_involved=pen_involved, pen_bonus=pen_bonus,
        ))

    # --- preds SIN actual: no abortan, pero se avisan (M3 review R16/QF) ---
    # El loop itera sobre actuals, así que una predicción sin actual quedaría fuera del
    # reporte en silencio (p. ej. un partido reprogramado fuera de la ventana --to).
    scored_keys = {(r["home"], r["away"]) for r in results}
    preds_sin_actual = set(preds.keys()) - scored_keys
    if preds_sin_actual:
        print("ADVERTENCIA: predicciones SIN actual (NO scoreadas; no abortan):")
        for h, a in sorted(preds_sin_actual):
            print(f"  - {h} vs {a}")
        print("  Si esperabas scorearlas, revisá la ventana --from/--to de los actuals.\n")

    # --- fallos ruidosos ---
    if missing_preds:
        print("ERROR: actuals sin predicción correspondiente:")
        for m in missing_preds:
            print(m)
        print("\nAbortando — revisar mapeo de nombres o archivo de predicciones.")
        sys.exit(1)

    if not results:
        print("ERROR: sin resultados después del join. Revisar archivos.")
        sys.exit(1)

    # --- tabla a stdout ---
    total_pts = sum(r["pts"] for r in results)
    total_ev = sum(r["ev"] for r in results)
    n = len(results)
    n_sin_prov = sum(1 for r in results if not r["provisional"])
    pts_sin_prov = sum(r["pts"] for r in results if not r["provisional"])
    avg_pts = total_pts / n if n else 0
    avg_pts_sin = pts_sin_prov / n_sin_prov if n_sin_prov else 0
    avg_ev = total_ev / n if n else 0
    ratio_pct = (avg_pts / avg_ev - 1) * 100 if avg_ev else 0

    header = (f"{'Fecha':<12} {'Partido':<42} {'Pred':>6} {'Real':>6} "
              f"{'Out':>4} {'Gol':>4} {'Pts':>4} {'EV':>6} {'Pts-EV':>7} {'Prov':>7}")
    sep = "-" * len(header)
    print(header)
    print(sep)
    for r in results:
        partido = f"{r['home']} vs {r['away']}"
        print(f"{r['date']:<12} {partido:<42} {r['pred']:>6} {r['real']:>6} "
              f"{r['outcome_ok']:>4} {r['goal_match']:>4} {r['pts']:>4} "
              f"{r['ev']:>6.2f} {r['pts_minus_ev']:>7.2f} {r['prov_label']:>7}")
    print(sep)
    print(f"\nTOTALES ({n} partidos, incluyendo provisional)")
    print(f"  Total pts:         {total_pts}")
    print(f"  Media pts/partido: {avg_pts:.3f}")
    print(f"  Sin provisional ({n_sin_prov} partidos):")
    print(f"    Total pts:         {pts_sin_prov}")
    print(f"    Media pts/partido: {avg_pts_sin:.3f}")
    print(f"  Suma EV ({n}):     {total_ev:.2f}")
    print(f"  Media EV:          {avg_ev:.3f}")
    print(f"  Ratio real/EV:     {ratio_pct:+.1f}%  (negativo = quedamos bajo expectativa)")
    print()

    # --- reporte markdown ---
    lines = []
    lines.append(f"# Oráculo Mundialista — Reporte {args.label} (scored)")
    lines.append("")
    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- **Predicciones:** `{pred_path.name}`")
    lines.append(f"- **Actuals:** `{actual_path.name}`")
    lines.append(f"- **Rung 1:** vs resultados = verdad (el veredicto serio es Fase 3, backtest multi-copa)")
    lines.append(f"- **Scoring:** `wcprode.scoring.match_points` VERBATIM de `docs/prode_rules.md §2`")
    prov_note = f" (incl. {n - n_sin_prov} provisional)" if n != n_sin_prov else ""
    lines.append(f"- **N:** {n} partidos{prov_note}")
    lines.append("")
    lines.append("## Tabla de resultados")
    lines.append("")
    lines.append("| Fecha | Partido | Pred | Real | Outcome✓ | GolMatch | Pts | EV | Pts−EV | Prov. |")
    lines.append("|-------|---------|------|------|----------|----------|-----|----|--------|-------|")
    for r in results:
        partido = f"{r['home']} vs {r['away']}"
        lines.append(
            f"| {r['date']} | {partido} | {r['pred']} | {r['real']} "
            f"| {r['outcome_ok']} | {r['goal_match']} | {r['pts']} "
            f"| {r['ev']:.2f} | {r['pts_minus_ev']:.2f} | {r['prov_label']} |"
        )
    lines.append("")
    lines.append("## Totales")
    lines.append("")
    lines.append(f"| Métrica | Con provisional (N={n}) | Sin provisional (N={n_sin_prov}) |")
    lines.append("|---------|------------------------|----------------------------------|")
    lines.append(f"| Total pts | **{total_pts}** | **{pts_sin_prov}** |")
    lines.append(f"| Media pts/partido | **{avg_pts:.3f}** | **{avg_pts_sin:.3f}** |")
    lines.append(f"| Suma EV | {total_ev:.2f} | — |")
    lines.append(f"| Media EV | {avg_ev:.3f} | — |")
    lines.append(f"| Ratio real/EV | {ratio_pct:+.1f}% | — |")
    lines.append("")
    lines.append("## Lectura honesta")
    lines.append("")
    lines.append(
        f"N={n} — ruidoso, no es veredicto. El veredicto serio es Fase 3 "
        "(backtest WC2022 virginal, multi-copa)."
    )
    lines.append("")
    # Data-driven: top-3 que más decepcionaron vs EV y top-3 de más puntos.
    worst = sorted(results, key=lambda r: r["pts_minus_ev"])[:3]
    best = sorted(results, key=lambda r: (r["pts"], r["pts_minus_ev"]), reverse=True)[:3]
    lines.append("**Lo que más dolió (pts por debajo de EV):**")
    for r in worst:
        lines.append(
            f"- {r['home']} vs {r['away']}: pred {r['pred']}, real {r['real']} → "
            f"{r['pts']} pts (EV {r['ev']:.2f}, Δ {r['pts_minus_ev']:+.2f})"
        )
    lines.append("")
    lines.append("**Lo que mejor salió (más pts):**")
    for r in best:
        lines.append(
            f"- {r['home']} vs {r['away']}: pred {r['pred']}, real {r['real']} → "
            f"{r['pts']} pts (EV {r['ev']:.2f}, Δ {r['pts_minus_ev']:+.2f})"
        )
    lines.append("")
    lines.append(
        f"**Resumen:** {ratio_pct:+.1f}% vs expectativa propia (media real {avg_pts:.3f} vs "
        f"media EV {avg_ev:.3f}). Esperado para N pequeño dada la alta varianza del scoring."
    )

    # Descomposición jackpot (M2 review R16/QF): con N chico los marcadores exactos (12 pts)
    # cargan el resultado headline; mostramos el rendimiento sin ellos para no sobrevender.
    exactos = [r for r in results if r["pts"] == 12]
    n_rest = n - len(exactos)
    if exactos and n_rest > 0:
        pts_ex = sum(r["pts"] for r in exactos)
        pts_rest = total_pts - pts_ex
        ev_rest = total_ev - sum(r["ev"] for r in exactos)
        ratio_rest = (pts_rest / ev_rest - 1) * 100 if ev_rest else 0
        lines.append("")
        lines.append(
            f"**Descomposición jackpot:** {len(exactos)} marcador(es) exacto(s) (12 pts) "
            f"aportan {pts_ex} de {total_pts} pts. Sin ellos: {pts_rest} pts en {n_rest} "
            f"partidos vs EV {ev_rest:.2f} = **{ratio_rest:+.1f}%**. Con N chico el resultado "
            f"headline lo cargan los exactos; leer el % agregado con esa cautela."
        )

    # Picks de empate a penales (+5, prode_rules §1.4): aparece SOLO si hubo alguno.
    empates_pen = [r for r in results if r["pen_involved"]]
    if empates_pen:
        lines.append("")
        lines.append("**Picks de empate a penales (+5):**")
        for r in empates_pen:
            got = "**+5 cobrado**" if r["pen_bonus"] else "sin +5 (ganador de tanda errado)"
            lines.append(
                f"- {r['home']} vs {r['away']}: pred {r['pred']} (empate), "
                f"pen_pred={r['pen_pred']} vs real={r['pen_actual']} → {got}"
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Reporte escrito en: {out_path}")


if __name__ == "__main__":
    main()
