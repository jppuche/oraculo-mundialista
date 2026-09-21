"""ingest_thirds_table.py — ingesta de la tabla Annex C (495 combinaciones) que
asigna los 8 mejores terceros a los slots del R32 del WC2026.

Fuente: Wikipedia Template:2026 FIFA World Cup third-place table, PINEADA por oldid
(análogo al SHA-pin de martj42). Re-pin = cambiar OLDID + quarantine+diff (data_security P2).

Salida: data/raw/wc2026_thirds_combinations.json — lista de {option, groups, assign}
donde assign = {winner_group: third_group}. CSV/JSON-only, never pickle (regla de datos).

Validación dura (falla ruidoso): 495 filas, 495 group-sets únicos, 8 terceros por fila,
set(terceros asignados)==set(grupos clasificados), cada tercero en el set elegible de su
slot, ningún tercero contra el ganador de su propio grupo. Si algo no cuadra, aborta.
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

OLDID = 1357614390  # Template:2026 FIFA World Cup third-place table @ 2026-06-03T17:09:34Z
TEMPLATE = "Template:2026 FIFA World Cup third-place table"
KNOCKOUT_PAGE_OLDID = 1359418806  # 2026 FIFA World Cup knockout stage (bracket + sedes)
UA = {"User-Agent": "OraculoMundialista/1.0 (research; contact github.com/jppuche)"}

GROUPS = list("ABCDEFGHIJKL")               # 12 grupos
WINNER_COLS = ["A", "B", "D", "E", "G", "I", "K", "L"]  # orden de columnas del template

# Set elegible de terceros por slot-ganador (verificado del bracket R32, Wikipedia)
ELIGIBLE = {
    "A": set("CEFHI"),
    "B": set("EFGIJ"),
    "D": set("BEFIJ"),
    "E": set("ABCDF"),
    "G": set("AEHIJ"),
    "I": set("CDFGH"),
    "K": set("DEIJL"),
    "L": set("EHIJK"),
}


def fetch_wikitext(oldid: int) -> str:
    url = ("https://en.wikipedia.org/w/api.php?action=parse&oldid="
           f"{oldid}&prop=wikitext&format=json&formatversion=2")
    req = urllib.request.Request(url, headers=UA)
    d = json.load(urllib.request.urlopen(req, timeout=30))
    return d["parse"]["wikitext"]


def parse_rows(wt: str) -> list[dict]:
    rows = []
    blocks = wt.split("|-")
    for block in blocks:
        m = re.search(r'!\s*scope="row"\s*\|\s*(\d+)', block)
        if not m:
            continue
        option = int(m.group(1))
        cells = []
        for line in block.splitlines():
            ls = line.strip()
            if (ls.startswith("|") and not ls.startswith("|-")
                    and not ls.startswith("|+") and ls != "|}"):
                # quita el "|" inicial, separa por "||"
                cells += [c.strip() for c in ls[1:].split("||")]
        if len(cells) != 20:
            sys.exit(f"FILA {option}: esperaba 20 celdas, hubo {len(cells)} -> {cells}")
        group_cells = cells[:12]
        assign_cells = cells[12:]

        # grupos clasificados: celda no vacía en su posición
        groups = []
        for i, c in enumerate(group_cells):
            letter = c.replace("'", "").strip()
            if letter:
                if letter != GROUPS[i]:
                    sys.exit(f"FILA {option}: col {i} dice {letter!r}, esperaba {GROUPS[i]!r}")
                groups.append(letter)

        # asignaciones: '3X' por columna-ganador
        assign = {}
        for j, c in enumerate(assign_cells):
            cc = c.replace("'", "").strip()
            mm = re.fullmatch(r"3([A-L])", cc)
            if not mm:
                sys.exit(f"FILA {option}: celda de asignación {j} ilegible: {c!r}")
            assign[WINNER_COLS[j]] = mm.group(1)

        rows.append({"option": option, "groups": groups, "assign": assign})
    return rows


def validate(rows: list[dict]) -> None:
    if len(rows) != 495:
        sys.exit(f"Esperaba 495 filas, hubo {len(rows)}")
    seen = set()
    for r in rows:
        opt, groups, assign = r["option"], r["groups"], r["assign"]
        if len(groups) != 8:
            sys.exit(f"FILA {opt}: {len(groups)} grupos clasificados (esperaba 8)")
        key = frozenset(groups)
        if key in seen:
            sys.exit(f"FILA {opt}: group-set duplicado {sorted(groups)}")
        seen.add(key)
        if len(assign) != 8:
            sys.exit(f"FILA {opt}: {len(assign)} asignaciones (esperaba 8)")
        if set(assign.values()) != set(groups):
            sys.exit(f"FILA {opt}: terceros asignados {sorted(assign.values())} != "
                     f"grupos clasificados {sorted(groups)}")
        for winner, third in assign.items():
            if third not in ELIGIBLE[winner]:
                sys.exit(f"FILA {opt}: 3{third} -> 1{winner} viola elegibilidad "
                         f"{sorted(ELIGIBLE[winner])}")
            if third == winner:
                sys.exit(f"FILA {opt}: 3{winner} jugaría contra 1{winner} (mismo grupo)")
    if len(seen) != 495:
        sys.exit(f"group-sets únicos: {len(seen)} (esperaba 495)")
    print("VALIDACIÓN: OK — 495 filas, 495 group-sets únicos, todas las restricciones pasan")


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "raw" / "wc2026_thirds_combinations.json"
    print(f"Fetch template oldid={OLDID} ...")
    wt = fetch_wikitext(OLDID)
    rows = parse_rows(wt)
    validate(rows)

    # spot-check fila 1 (decodificada a mano por el orquestador)
    r1 = next(r for r in rows if r["option"] == 1)
    expected_r1 = {"A": "E", "B": "J", "D": "I", "E": "F", "G": "H", "I": "G", "K": "L", "L": "K"}
    assert sorted(r1["groups"]) == list("EFGHIJKL"), r1["groups"]
    assert r1["assign"] == expected_r1, r1["assign"]
    print("SPOT-CHECK fila 1: OK (coincide con decodificación a mano)")

    payload = {
        "_provenance": {
            "source": f"Wikipedia {TEMPLATE}",
            "url": f"https://en.wikipedia.org/w/index.php?title={urllib.parse.quote(TEMPLATE)}&oldid={OLDID}",
            "oldid": OLDID,
            "bracket_page_oldid": KNOCKOUT_PAGE_OLDID,
            "fetched": "2026-06-15",
            "note": "Annex C de las regulaciones FIFA WC2026, transcrita en Wikipedia. "
                    "495 combinaciones C(12,8). winner_cols order: " + ",".join(WINNER_COLS),
        },
        "winner_cols": WINNER_COLS,
        "eligible": {k: sorted(v) for k, v in ELIGIBLE.items()},
        "combinations": rows,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"Escrito: {out}  ({len(rows)} combinaciones)")


if __name__ == "__main__":
    main()
