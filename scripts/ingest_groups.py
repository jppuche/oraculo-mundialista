"""ingest_groups.py — composición oficial de grupos WC2026 (letra A-L -> 4 equipos),
en NOMBRES CANÓNICOS de martj42 (los que usa el motor y los fixtures).

Método robusto (evita el drift de nombres):
  1. Membresía: derivar las 12 camarillas (K4) de los fixtures de grupo de martj42
     (nombres canónicos, fuente autoritativa de quién está con quién).
  2. Etiquetado A-L: anclar cada camarilla por su cabeza de serie (Pot 1, uno por grupo),
     cuya LETRA se lee de la página dedicada de Wikipedia (códigos FIFA) y cuyo NOMBRE
     canónico ya está en la camarilla. Validar: 12 letras distintas, 12 camarillas
     distintas, cobertura total, anfitriones Mexico=A / Canada=B / United States=D.

Salida: data/raw/wc2026_groups.json {letter: [4 nombres canónicos]} + provenance.
"""
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from wcprode import ingest

UA = {"User-Agent": "OraculoMundialista/1.0 (research; contact github.com/jppuche)"}
REPO = Path(__file__).resolve().parent.parent
LETTERS = list("ABCDEFGHIJKL")

# Anclas Pot-1: código FIFA -> nombre canónico martj42 (uno por grupo, inequívocos).
ANCHORS = {
    "MEX": "Mexico", "CAN": "Canada", "USA": "United States", "BRA": "Brazil",
    "GER": "Germany", "NED": "Netherlands", "ESP": "Spain", "FRA": "France",
    "ARG": "Argentina", "ENG": "England", "POR": "Portugal", "BEL": "Belgium",
}
CODE_RE = re.compile(r"\{\{#invoke:flag\|fb(?:-rt|-rw)?\|([A-Z]{3})\}\}")


def derive_cliques() -> list[set]:
    df, _ = ingest.load_results()
    # todos los partidos de grupo WC2026 (jugados o no) para la membresía
    mask = (df["tournament"] == "FIFA World Cup") & \
           (df["date"] >= "2026-06-11") & (df["date"] <= "2026-06-27")
    g = df.loc[mask]
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    for _, r in g.iterrows():
        union(r["home_team"], r["away_team"])
    comp = {}
    for t in parent:
        comp.setdefault(find(t), set()).add(t)
    cliques = list(comp.values())
    sizes = sorted(len(c) for c in cliques)
    if sizes != [4] * 12:
        raise SystemExit(f"Camarillas mal formadas: tamaños {sizes} (esperaba 12x4). "
                         f"¿pin de martj42 sin los 72 fixtures de grupo?")
    return cliques


def fetch_group_codes() -> tuple[dict, dict]:
    """Retorna ({letter: set(codes)}, {letter: revid}) de las páginas dedicadas."""
    letter_codes, revids = {}, {}
    for L in LETTERS:
        title = f"2026 FIFA World Cup Group {L}"
        q = ("https://en.wikipedia.org/w/api.php?action=query&prop=revisions&titles="
             + urllib.parse.quote(title) + "&rvprop=ids&format=json&formatversion=2")
        p = json.load(urllib.request.urlopen(urllib.request.Request(q, headers=UA), timeout=30))
        page = p["query"]["pages"][0]
        if page.get("missing"):
            raise SystemExit(f"Falta página: {title}")
        rv = page["revisions"][0]["revid"]
        pu = ("https://en.wikipedia.org/w/api.php?action=parse&oldid=" + str(rv)
              + "&prop=wikitext&format=json&formatversion=2")
        wt = json.load(urllib.request.urlopen(urllib.request.Request(pu, headers=UA),
                                              timeout=30))["parse"]["wikitext"]
        codes = set(CODE_RE.findall(wt))
        letter_codes[L] = codes
        revids[L] = rv
    return letter_codes, revids


def main() -> None:
    cliques = derive_cliques()
    letter_codes, revids = fetch_group_codes()

    result = {}        # letter -> sorted(clique)
    used_cliques = []
    for code, name in ANCHORS.items():
        letters = [L for L, cs in letter_codes.items() if code in cs]
        if len(letters) != 1:
            raise SystemExit(f"Ancla {code}: aparece en {letters} (esperaba 1 grupo)")
        L = letters[0]
        cls = [c for c in cliques if name in c]
        if len(cls) != 1:
            raise SystemExit(f"Ancla {name!r}: en {len(cls)} camarillas (esperaba 1). "
                             f"¿nombre canónico distinto en martj42?")
        clique = cls[0]
        if L in result:
            raise SystemExit(f"Letra {L} asignada dos veces (ancla {code}/{name})")
        if id(clique) in [id(c) for c in used_cliques]:
            raise SystemExit(f"Camarilla {sorted(clique)} ya etiquetada (ancla {code})")
        result[L] = sorted(clique)
        used_cliques.append(clique)

    if set(result) != set(LETTERS):
        raise SystemExit(f"Faltan letras: {set(LETTERS) - set(result)} "
                         f"(alguna camarilla sin cabeza de serie en ANCHORS)")
    # anfitriones
    for host, L in [("Mexico", "A"), ("Canada", "B"), ("United States", "D")]:
        if host not in result[L]:
            raise SystemExit(f"Anfitrión {host} no quedó en grupo {L}: {result[L]}")
    print("VALIDACIÓN: OK — 12 grupos etiquetados, anfitriones A/B/D, partición completa")
    for L in LETTERS:
        print(f"  Grupo {L}: {', '.join(result[L])}".encode('ascii', 'backslashreplace').decode())

    out = REPO / "data" / "raw" / "wc2026_groups.json"
    payload = {
        "_provenance": {
            "membership_source": "martj42 fixtures (sources.lock.json) — nombres canónicos",
            "labels_source": "Wikipedia '2026 FIFA World Cup Group X' (códigos FIFA), anclado por Pot 1",
            "group_page_revids": revids,
            "fetched": "2026-06-15",
        },
        "groups": result,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito: {out}")


if __name__ == "__main__":
    main()
