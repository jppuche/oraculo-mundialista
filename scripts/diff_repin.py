"""diff_repin.py — clasifica el diff de un re-pin de results.csv (quarantine vs actual).

Automatiza la verificación manual del re-pin (data_security P2 quarantine+diff): confirma que
NINGUNA fila que YA tenía score cambió (revisión/corrupción silenciosa), separando los cambios
ESPERADOS (NA→score de partidos jugados, filas nuevas = fixtures, reprogramaciones de fecha) de
las ALERTAS (score→score distinto). Es el gate que el finding L3 de la review R16/QF pedía
codificar: hoy la aserción "0 scores históricos alterados" del `_repin_note` se hacía a mano.

Read-only: no toca el pin, el lock ni el gate. Empareja partidos por (home, away, tournament)
para ser robusto a reprogramaciones de fecha (una fila que cambia de fecha aparece como
remove+add en un diff textual; acá se reconoce como el mismo partido). Exit code 1 si detecta
algún score histórico alterado (para poder encadenarlo en un check).

Uso:
  .venv/Scripts/python.exe scripts/diff_repin.py \\
      --old data/raw/_quarantine/results_OLD_25e30198.csv --new data/raw/results.csv
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wcprode import ingest  # noqa: E402

NA = {"NA", "", "na", "NaN", "nan"}


def has_score(r: dict) -> bool:
    return r.get("home_score") not in NA and r.get("away_score") not in NA


def match_key(r: dict) -> tuple:
    """Identidad de partido robusta a reprogramación de fecha."""
    return (r["home_team"], r["away_team"], r["tournament"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--old", required=True, help="results.csv previo (p. ej. del _quarantine/)")
    ap.add_argument("--new", required=True, help="results.csv actual (pineado)")
    args = ap.parse_args()

    old_df = ingest.read_csv_raw(args.old)   # dtype=str, NA preservado (na_filter=False)
    new_df = ingest.read_csv_raw(args.new)
    cols = list(old_df.columns)
    if list(new_df.columns) != cols:
        print(f"⚠️  Esquemas distintos:\n  old={cols}\n  new={list(new_df.columns)}")
        sys.exit(2)

    old_rows = [r.to_dict() for _, r in old_df.iterrows()]
    new_rows = [r.to_dict() for _, r in new_df.iterrows()]
    old_exact = {tuple(r[c] for c in cols) for r in old_rows}
    new_exact = {tuple(r[c] for c in cols) for r in new_rows}
    identicas = len(old_exact & new_exact)

    removed = [r for r in old_rows if tuple(r[c] for c in cols) not in new_exact]
    added = [r for r in new_rows if tuple(r[c] for c in cols) not in old_exact]

    added_by_key: dict = defaultdict(list)
    for a in added:
        added_by_key[match_key(a)].append(a)

    alterados, na_to_score, reprogramados, otros_mod, eliminados = [], [], [], [], []
    matched = set()
    for r in removed:
        cands = [a for a in added_by_key[match_key(r)] if id(a) not in matched]
        if not cands:
            eliminados.append(r)
            continue
        a = cands[0]
        matched.add(id(a))
        date_changed = r["date"] != a["date"]
        if has_score(r) and has_score(a) and \
                (r["home_score"], r["away_score"]) != (a["home_score"], a["away_score"]):
            alterados.append((r, a))
        elif not has_score(r) and has_score(a):
            na_to_score.append((r, a))
            if date_changed:
                reprogramados.append((r, a))
        elif date_changed:
            reprogramados.append((r, a))
        else:
            otros_mod.append((r, a))
    nuevas = [a for a in added if id(a) not in matched]

    def label(r):
        return f"{r['date']} {r['home_team']} vs {r['away_team']} ({r['tournament']})"

    print(f"# diff_repin  old={Path(args.old).name}  new={Path(args.new).name}")
    print(f"Filas: old={len(old_rows)}  new={len(new_rows)}  idénticas={identicas}\n")

    print(f"NA→score (partidos jugados): {len(na_to_score)}")
    for r, a in na_to_score:
        tag = f"  [REPROGRAMADO {r['date']}→{a['date']}]" if r["date"] != a["date"] else ""
        print(f"    {a['home_team']} {a['home_score']}-{a['away_score']} {a['away_team']}{tag}")
    print(f"Reprogramaciones de fecha (total, incl. las de arriba): {len(reprogramados)}")
    print(f"Filas nuevas (fixtures / altas): {len(nuevas)}")
    for a in nuevas:
        print(f"    {label(a)}  score={a['home_score']}-{a['away_score']}")
    if otros_mod:
        print(f"Otras modificaciones (sin cambio de score, p. ej. city/neutral): {len(otros_mod)}")
    if eliminados:
        print(f"Eliminadas (sin par en new): {len(eliminados)}")
        for r in eliminados:
            print(f"    {label(r)}")
    print()

    if alterados:
        print(f"⚠️  ALERTA: {len(alterados)} fila(s) con SCORE HISTÓRICO ALTERADO (score→score):")
        for r, a in alterados:
            print(f"    {label(a)}: {r['home_score']}-{r['away_score']} → "
                  f"{a['home_score']}-{a['away_score']}")
        print("\nRevisar ANTES de aceptar el re-pin (data_security P2). Exit 1.")
        sys.exit(1)

    print("✅ 0 scores históricos alterados. Diff consistente con un re-pin limpio "
          "(solo NA→score, reprogramaciones y altas).")


if __name__ == "__main__":
    main()
