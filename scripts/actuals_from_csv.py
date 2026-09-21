"""actuals_from_csv.py — deriva el archivo de actuals (.md) directo del results.csv
re-pineado, en el formato que consume score_matchday.py.

Por qué: el scorer lee una tabla '## Resultados' de un .md. Hasta ahora ese .md se
transcribía a mano (FotMob) — fuente de fricción: name-maps (Czechia/USA/Türkiye),
estados provisionales, cobertura parcial. Derivarlo del CSV pineado da single source of
truth (mismo dato que alimenta el fit), ya pasado por el gate, con nombres canónicos
martj42 (matchean directo con las predicciones). NO es oráculo: es un conveniencia de I/O.

Uso:
  .venv/Scripts/python.exe scripts/actuals_from_csv.py --from 2026-06-11 --to 2026-06-17 \
      --out data/actuals_2026-06-18.md
"""
import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wcprode import ingest  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GROUPS_JSON = REPO / "data" / "raw" / "wc2026_groups.json"


def team_to_group() -> dict:
    """Mapa equipo -> letra de grupo, robusto ante la forma del JSON."""
    out: dict = {}

    def harvest(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, list) and all(isinstance(x, str) for x in v):
                    for t in v:
                        out[t] = k
                else:
                    harvest(v)
        elif isinstance(obj, list):
            for x in obj:
                harvest(x)

    if GROUPS_JSON.exists():
        harvest(json.loads(GROUPS_JSON.read_text(encoding="utf-8")))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="dfrom", required=True)
    ap.add_argument("--to", dest="dto", required=True)
    ap.add_argument("--out", dest="out", required=True)
    args = ap.parse_args()

    df, _ = ingest.load_results()  # verifica hash contra el lock + gate
    mask = (
        (df["tournament"] == "FIFA World Cup")
        & (df["date"] >= args.dfrom)
        & (df["date"] <= args.dto)
        & (df["played"])
    )
    wc = df.loc[mask].sort_values(["date", "home_team"]).reset_index(drop=True)
    t2g = team_to_group()

    # Tandas de penales (KO): (date, home, away) -> equipo ganador de la tanda. El scorer
    # lo usa para acreditar el +5 a un pick de empate que fue a penales (prode_rules §1.4).
    # Nombres canonicos martj42 (matchean con home/away de results.csv, sin name-map).
    shootouts = ingest.load_shootouts()
    pen_by_match = {
        (s["date"], s["home_team"], s["away_team"]): s["winner"]
        for _, s in shootouts.iterrows()
    }

    lines = [
        f"# Resultados reales WC2026 {args.dfrom}..{args.dto} — derivados del CSV re-pineado",
        "",
        "**Provenance:** `data/raw/results.csv` (pin martj42 en `sources.lock.json`), "
        "filtro `FIFA World Cup` jugados en la ventana. Validado por el gate de ingesta. "
        "Nombres canónicos martj42 (sin name-map). Generado por `scripts/actuals_from_csv.py`.",
        "",
        "## Resultados (FT)",
        "",
        "| Fecha | Grupo | Local | GL | GV | Visitante | Nota |",
        "|-------|-------|-------|----|----|-----------|------|",
    ]
    for _, r in wc.iterrows():
        grp = t2g.get(r["home_team"], t2g.get(r["away_team"], "-"))
        pen_winner = pen_by_match.get((r["date"], r["home_team"], r["away_team"]), "")
        nota = f"pen: {pen_winner}" if pen_winner else ""
        lines.append(
            f"| {r['date'][5:]} | {grp} | {r['home_team']} | "
            f"{r['home_score']} | {r['away_score']} | {r['away_team']} | {nota} |"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{out_path} generado: {len(wc)} partidos jugados en [{args.dfrom}..{args.dto}]")
    print("grupos:", " ".join(sorted({t2g.get(r["home_team"], "-") for _, r in wc.iterrows()})))


if __name__ == "__main__":
    main()
