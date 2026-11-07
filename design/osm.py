"""OpenStreetMap から取り出した形（osm_features.txt / osm_taxiways.txt）を読む。単位は m（基準点 35.546N 139.792E から東・北）"""
from pathlib import Path
HERE = Path(__file__).resolve().parent
U = 2.0

def _dec(s):
    pts = []
    x = y = 0
    for i, tok in enumerate(s.split()):
        a, b = map(int, tok.split(","))
        if i == 0:
            x, y = a, b
        else:
            x += a; y += b
        pts.append((x * U, y * U))
    return pts

def features():
    out = []
    for line in (HERE / "osm_features.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        kind, role, g = line.split("|", 2)
        out.append((kind, role, _dec(g)))
    return out

def taxiways():
    return [_dec(s) for s in (HERE / "osm_taxiways.txt").read_text().strip().split(";")]

def buildings():
    """osm_buildings.txt：[(種類, 名前, 点の列)]。種類 T/H/P/S/R/B（末尾 i は中の穴）、J はボーディングブリッジ（線）"""
    out = []
    for line in (HERE / "osm_buildings.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if parts[0] == "J":
            kind, name, g = "J", "", parts[1]
        else:
            kind, name, g = parts
        pts = [(x / U, y / U) for x, y in _dec(g)]     # このファイルは 1m 単位
        out.append((kind, name, pts))
    return out
