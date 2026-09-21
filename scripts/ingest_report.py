"""Diagnostico del gate de ingesta. Corre el gate sobre el results.csv pineado e
imprime el Report, los motivos de descarte, la estructura de fixtures del WC2026 y
la cobertura historica de los 48 equipos (sanity del fit). Re-ejecutable.

Uso:  .venv/Scripts/python.exe scripts/ingest_report.py
"""
import sys
from collections import Counter

from wcprode import data_validation as dv
from wcprode import ingest

# La consola de Windows usa cp1252 y no imprime caracteres unicode (acentos, schwa).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main() -> None:
    df, rep = ingest.load_results()
    print("RESULTS:", rep.summary())

    reasons = Counter(msg.split(":")[0] for _, msg in rep.dropped)
    print("dropped por motivo:", dict(reasons))
    for idx, msg in rep.dropped:
        print(f"  drop[{idx}] {msg}")
    if rep.defanged:
        print("defanged (muestra):", rep.defanged[:6])

    fixtures = ingest.wc2026_group_fixtures(df)
    print("\nWC2026 group fixtures:", len(fixtures))
    print("estructura:", dv.validate_wc2026_groups(fixtures))

    played = ingest.played_results(df)
    teams = sorted(set(fixtures["home_team"]) | set(fixtures["away_team"]))
    appear = {
        t: int(((played["home_team"] == t) | (played["away_team"] == t)).sum())
        for t in teams
    }
    ranked = sorted(appear.items(), key=lambda kv: kv[1])
    print(f"\n48 equipos WC2026 — min historial={ranked[0][1]}, max={ranked[-1][1]}")
    print("5 con menos historial:", ranked[:5])


if __name__ == "__main__":
    main()
