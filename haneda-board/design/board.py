"""
羽田空港 運用ボード（第4版：ADS-B レーダーと合体）：レーザーカット用の図面と 3D ビューア用データを作る

  python3 board.py  →  ../laser/*.svg・*.dxf、../build/board.json、../laser/check_report.md

・空港の形・ターミナル・エプロン・誘導路・滑走路は OpenStreetMap のデータ（osm_*.txt）から
・LED は在庫の 5mm LED（赤・緑・黄）と 2色LEDモジュール 2 個、RGB LEDモジュール 1 個
・板は 3mm 黄ボード。下から
    L1 底板（LED の足の穴） / L2 海の板 / L3 空港の島 / L4 ターミナル
  海の板は島のまわりだけ（島の大きさは第3版と同じ）。右上に ADS-B レーダーの本体（裏ぶたなし）をのせ、
  その下の L1・L2 に穴をあけて、裏の 3D プリントのトレーに ESP32 などの基板をしまう
  配線は底板の裏に這わせて、トレーへ入れる
座標：mm、x = 右（東）、y = 上（北）。原点は板の外形の左下。
"""
import json, math
from pathlib import Path
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, box as sbox
from shapely.ops import unary_union
from shapely import affinity
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import osm

ROOT = Path(__file__).resolve().parent.parent
(ROOT / "laser").mkdir(exist_ok=True)
(ROOT / "build").mkdir(exist_ok=True)

# ---------------- 縮尺と板 ----------------
SCALE = 25000                     # 1:25000（1km = 40mm）
MM = 1000.0 / SCALE
T = 3.0
LOCAL_C = (-194.0, -32.0)         # 第3版の板（290 × 246）の中心に来た現地座標（m）
OX, OY = 9.0, 7.2                 # 第3版の座標から外形の左下までのずれ（島の位置関係は第3版と同じ）

def Q(x, y):
    """第3版の板の座標 → 第4版の座標"""
    return (x - OX, y - OY)

def M(p):
    """現地座標（m）→ 板の上の mm"""
    return (145.0 + (p[0] - LOCAL_C[0]) * MM - OX, 123.0 + (p[1] - LOCAL_C[1]) * MM - OY)

def Mg(pts):
    return [M(p) for p in pts]

FONT_B = FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
FONT_M = FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc")

def rounded_rect(x0, y0, x1, y1, r):
    return sbox(x0 + r, y0 + r, x1 - r, y1 - r).buffer(r, quad_segs=8)

def text_poly(s, size, x, y, angle=0.0, anchor="center", font=FONT_M):
    tp = TextPath((0, 0), s, size=size, prop=font)
    g = None
    for p in tp.to_polygons():
        if len(p) < 3:
            continue
        q = Polygon(p).buffer(0)
        g = q if g is None else g.symmetric_difference(q)
    minx, miny, maxx, maxy = g.bounds
    dx = -(minx + maxx) / 2 if anchor == "center" else -minx
    g = affinity.translate(g, dx, -(miny + maxy) / 2)
    g = affinity.rotate(g, angle, origin=(0, 0))
    return affinity.translate(g, x, y)

def polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]

# =========================================================
#  OpenStreetMap の形
# =========================================================
FEAT = osm.features()
def feat(kind, role=None):
    return [g for k, r, g in FEAT if k == kind and (role is None or r == role)]

ISLAND = Polygon(Mg(feat("AERO", "outer")[0])).buffer(0)
# ---------------- 建物（OpenStreetMap の建物の輪郭そのまま） ----------------
#  大きな建物（ターミナル・格納庫・整備工場・貨物ビル・立体駐車場・ホテルなど）は L4 の板で切り出して島に貼る（立体）
#  小さな建物は島に濃く刻印、ボーディングブリッジは細い線で刻印
def clean(p, r=0.3):
    """細すぎる部分（0.6mm 未満）を落とす"""
    return p.buffer(r, join_style="mitre").buffer(-2 * r, join_style="mitre").buffer(r, join_style="mitre")

BLD = osm.buildings()
def _bld_polys():
    out = []
    for i, (k, name, pts) in enumerate(BLD):
        if k == "J" or k.endswith("i") or len(pts) < 3:
            continue
        p = Polygon(Mg(pts)).buffer(0)
        # 直後に続く中の穴（Ti・Bi）
        j = i + 1
        while j < len(BLD) and BLD[j][0] == k + "i":
            if len(BLD[j][2]) >= 3:
                p = p.difference(Polygon(Mg(BLD[j][2])).buffer(0))
            j += 1
        out.append((k, name, p))
    return out
BUILDINGS = _bld_polys()
RAISE_MIN_AREA = 3.0                # これ以上（mm²、実物で約 1900m²）で、幅 1.2mm 以上ある建物は立体にする
TERMINALS = {}                      # 名前つきで立体にする建物（ターミナルは名前を刻印）
_raised, _small = [], []
for k, name, p in BUILDINGS:
    q = clean(p).intersection(ISLAND.buffer(-0.3))
    if q.is_empty:
        continue
    big = [g for g in polys(q) if g.area >= RAISE_MIN_AREA and not g.buffer(-0.6).is_empty]
    if big:
        _raised.append((k, name, unary_union(big)))
    rest = q.difference(unary_union(big)) if big else q
    if not rest.is_empty and rest.area > 0.15:
        _small.append(rest)
_T_NAME = {"第1旅客ターミナル": "T1", "第2旅客ターミナル": "T2", "第3旅客ターミナル": "T3"}
for k, name, g in _raised:
    key = _T_NAME.get(name)
    if key:
        TERMINALS[key] = TERMINALS[key].union(g) if key in TERMINALS else g
FACILITIES = unary_union([g for k, name, g in _raised if name not in _T_NAME])   # 格納庫・整備工場・貨物ビル・駐車場など
RAISED_KINDS = [(k, name, g) for k, name, g in _raised]
SMALL_BLD = unary_union(_small) if _small else Polygon()
JET_BRIDGES = unary_union([LineString(Mg(pts)).buffer(0.13, cap_style="flat") for k, n, pts in BLD if k == "J" and len(pts) >= 2])
TOWER_XY = Polygon(Mg(feat("TWR")[0])).centroid.coords[0]
APRONS = unary_union([Polygon(Mg(g)).buffer(0) for g in feat("APR")])
HANGARS = SMALL_BLD                 # 小さな建物（刻印）
TAXIWAYS = unary_union([LineString(Mg(g)).buffer(0.16, cap_style="round") for g in osm.taxiways() if len(g) >= 2])

# 滑走路（OSM の中心線をつないで端を求める）
RWY_DEF = {  # 名前: (端1, 端2)  端1 → 端2 の向き
    "A": ("16R", "34L"), "B": ("04", "22"), "C": ("16L", "34R"), "D": ("05", "23"),
}
RWY_OSM = {"A": "16R/34L", "B": "04/22", "C": "16L/34R", "D": "05/23"}
RWY_W = 60 * MM                    # 幅 60m（2.4mm、実物どおり）
rwy = {}
for k, ref in RWY_OSM.items():
    pts = [p for g in feat("RWY", ref) for p in Mg(g)]
    # 主軸の向きに並べて両端を取る
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    best = max(((a, b) for a in pts for b in pts), key=lambda ab: math.dist(*ab))
    a, b = best
    # 端1 を北（A, C）または南西（B, D）にそろえる
    if k in ("A", "C"):
        a, b = (a, b) if a[1] > b[1] else (b, a)
    else:
        a, b = (a, b) if a[1] < b[1] else (b, a)
    L = math.dist(a, b)
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    rwy[k] = dict(a=a, b=b, L=L, u=u, ends=RWY_DEF[k],
                  poly=LineString([a, b]).buffer(RWY_W / 2, cap_style="flat"))
RUNWAYS = unary_union([r["poly"] for r in rwy.values()])

# =========================================================
#  LED（在庫の 5mm LED とモジュール）
# =========================================================
#  緑＝着陸機が降りてくる端　黄＝離陸機が走り出す端　赤＝飛行機が向かう先の端
#  （羽田のふだんの運用で、それぞれの端が実際に使われる役割だけ置く）
LED_D_HOLE = 5.2                  # 5mm LED の本体の穴（モジュールの L1・L2、タイトル板）
ISLAND_LED_HOLE = 6.2             # 空港の島（L3）の LED の穴
LED_POCKET = 6.6                  # つば（Φ5.8）の入る穴（L3）
MOD_POCKET = (20.0, 17.0)         # モジュール基板の穴（L2・L3）
IN1, IN2 = 3.2, 9.8               # 滑走路の端から 1 個目・2 個目の LED までの距離
LEDS = [
    # (id, 滑走路, 端(0/1), 何番目, 種類, 色)
    ("A16R_Y", "A", 0, 1, "led", "yellow"), ("A16R_R", "A", 0, 2, "led", "red"),
    ("A34L_G", "A", 1, 1, "led", "green"),  ("A34L_R", "A", 1, 2, "led", "red"),
    ("B04_R", "B", 0, 1, "led", "red"),     ("B22_G", "B", 1, 1, "led", "green"),
    ("C16L_Y", "C", 0, 1, "led", "yellow"), ("C16L_R", "C", 0, 2, "led", "red"),
    ("C34R_GR", "C", 1, 1, "bicolor", "green/red"), ("C34R_Y", "C", 1, 2, "led", "yellow"),
    ("D05_Y", "D", 0, 1, "led", "yellow"),  ("D05_R", "D", 0, 2, "led", "red"),
    ("D23_GR", "D", 1, 1, "bicolor", "green/red"),
]

def led_xy(rw, end, nth):
    r = rwy[rw]
    d = IN1 if nth == 1 else IN2
    if end == 0:
        return (r["a"][0] + r["u"][0] * d, r["a"][1] + r["u"][1] * d)
    return (r["b"][0] - r["u"][0] * d, r["b"][1] - r["u"][1] * d)

leds = []
for lid, rw, end, nth, kind, col in LEDS:
    x, y = led_xy(rw, end, nth)
    leds.append(dict(id=lid, rw=rw, end=end, nth=nth, kind=kind, color=col, x=x, y=y))

# ---------------- 右上の小さな表示（タイトル・運用ランプ） ----------------
# =========================================================
#  ADS-B レーダー（ケースの本体を裏ぶたなしで海の板にのせる。液晶が上）
# =========================================================
RADAR_W, RADAR_H = 41.6, 83.5       # ケースの外形（adsb-radar/case/case.py の W・H）
RADAR_X0, RADAR_Y0 = Q(210.0, 132.0)  # ケースの左下（海の板がいちばん小さくなる場所を計算して決めた）
RADAR_BOX = sbox(RADAR_X0, RADAR_Y0, RADAR_X0 + RADAR_W, RADAR_Y0 + RADAR_H)
RADAR_HOLE = RADAR_BOX.buffer(-3.0, join_style=2)   # L1・L2 の穴（ケースの壁 1.6mm が穴の縁にのる）
# レーダーのボタン（VIEW・LIGHT）を板へ移す。キャップ Φ13 が通る穴
BTN_HOLE = 13.6
BTNS = [("表示", (RADAR_X0 + RADAR_W / 2 - 10.0, RADAR_Y0 - 10.0)),
        ("明るさ", (RADAR_X0 + RADAR_W / 2 + 10.0, RADAR_Y0 - 10.0))]
BTN_PCB = (15.0, 13.0)              # ボタンをのせた小さな基板（底板の裏に貼る）
GROUP = RADAR_BOX.union(sbox(RADAR_X0, RADAR_Y0 - 22.0, RADAR_X0 + RADAR_W, RADAR_Y0))

# ---------------- タイトル・運用ランプ（島とレーダーの間の海） ----------------
TITLE_X, TITLE_Y = Q(161.0, 211.0)   # タイトルの左端・中心
MODE_LED = Q(165.0, 197.0)           # RGB LED（北風＝青、南風＝橙）
leds.append(dict(id="MODE_RGB", rw="mode", end=0, nth=0, kind="rgb", color="rgb", x=MODE_LED[0], y=MODE_LED[1]))

# タイトル板（L5）：タイトル・運用ランプ・凡例・縮尺を別の板に彫って、海の板の上に貼る
def plaque_items():
    bx0, by = TITLE_X + 2.0, TITLE_Y - 31.0       # 縮尺 1 km = 40 mm
    return unary_union([
        text_poly("羽田空港", 6.2, TITLE_X, TITLE_Y, anchor="left", font=FONT_B),
        text_poly("RJTT  1:25000", 2.8, TITLE_X, TITLE_Y - 7.5, anchor="left"),
        text_poly("運用ランプ  北風 青 / 南風 橙", 2.3, MODE_LED[0] + 5.0, MODE_LED[1], anchor="left"),
        text_poly("滑走路の光  緑 着陸 / 黄 離陸 / 赤 滑走路の先", 2.3, TITLE_X, TITLE_Y - 21.0, anchor="left"),
        text_poly("離陸のたびに 黄→赤 が点滅", 2.3, TITLE_X, TITLE_Y - 25.0, anchor="left"),
        sbox(bx0, by, bx0 + 40.0, by + 1.2),
        text_poly("1 km", 2.6, bx0 + 20.0, by - 2.8),
    ])
PLAQUE_MARGIN, PLAQUE_R = 3.0, 2.5
_pb = unary_union([plaque_items(), Point(MODE_LED).buffer(3.5)]).bounds
PLAQUE = rounded_rect(_pb[0] - PLAQUE_MARGIN, _pb[1] - PLAQUE_MARGIN, _pb[2] + PLAQUE_MARGIN, _pb[3] + PLAQUE_MARGIN, PLAQUE_R)
# 島の岸とレーダーにかかる所は、岸に沿って切り落とす（すき間 1.2mm）
PLAQUE = (PLAQUE.difference(ISLAND.buffer(1.2)).difference(sbox(RADAR_X0 - 1.2, RADAR_Y0 - 1.2, RADAR_X0 + RADAR_W + 1.2, RADAR_Y0 + RADAR_H + 1.2))
          .buffer(-1.0, quad_segs=8).buffer(1.0, quad_segs=8))
PLAQUE = max(polys(PLAQUE), key=lambda p: p.area)

# =========================================================
#  配線（5 本の線を全部の LED に回す。溝は木の形にして配線層を 1 枚に保つ）
# =========================================================
HUB = Q(150.0, 118.0)              # 運用ボードのケース（第3版と同じ位置・同じもの）。配線は底板の裏を通してケースへ
HUB_HOLE = 10.0
WIRE_W = 5.0

def mst(points):
    n = len(points)
    used = [False] * n
    dist = [float("inf")] * n
    parent = [-1] * n
    dist[0] = 0
    edges = []
    for _ in range(n):
        i = min((j for j in range(n) if not used[j]), key=lambda j: dist[j])
        used[i] = True
        if parent[i] >= 0:
            edges.append((parent[i], i))
        for j in range(n):
            if not used[j]:
                d = math.dist(points[i], points[j])
                if d < dist[j]:
                    dist[j], parent[j] = d, i
    return edges

NODES = [HUB] + [(l["x"], l["y"]) for l in leds]
EDGES = mst(NODES)

# =========================================================
#  各層
# =========================================================
SEA_MARGIN = 6.0                  # 島のまわりの海の幅
def _label_area():
    return unary_union([
        text_poly("羽田空港", 6.2, TITLE_X, TITLE_Y, anchor="left", font=FONT_B),
        text_poly("滑走路の光  緑 着陸 / 黄 離陸 / 赤 滑走路の先", 2.3, TITLE_X, TITLE_Y - 21.0, anchor="left"),
        text_poly("運用ランプ  北風 青 / 南風 橙", 2.3, MODE_LED[0] + 5.0, MODE_LED[1], anchor="left"),
        text_poly("離陸のたびに 黄→赤 が点滅", 2.3, TITLE_X, TITLE_Y - 25.0, anchor="left"),
        sbox(TITLE_X + 2.0, TITLE_Y - 35.0, TITLE_X + 42.0, TITLE_Y - 29.8),
        Point(MODE_LED).buffer(5),
    ])
OUTLINE = (unary_union([ISLAND.buffer(SEA_MARGIN), GROUP.buffer(SEA_MARGIN), _label_area().buffer(4.0), PLAQUE.buffer(4.0)])
           .buffer(14, quad_segs=12).buffer(-14, quad_segs=12).simplify(0.02))
BX0, BY0, BW, BH = OUTLINE.bounds
BR = 0

def with_pins(g):
    """レーダーとボタンの穴（L1・L2 共通）"""
    g = g.difference(RADAR_HOLE)
    for _, (x, y) in BTNS:
        g = g.difference(Point(x, y).buffer(BTN_HOLE / 2, quad_segs=24))
    return g

def led_holes():
    return unary_union([Point(l["x"], l["y"]).buffer(LED_D_HOLE / 2, quad_segs=16) for l in leds])

def cavity():
    c = []
    for l in leds:
        if l["kind"] == "led":
            c.append(Point(l["x"], l["y"]).buffer(LED_POCKET / 2, quad_segs=16))
        else:
            c.append(sbox(l["x"] - MOD_POCKET[0] / 2, l["y"] - MOD_POCKET[1] / 2, l["x"] + MOD_POCKET[0] / 2, l["y"] + MOD_POCKET[1] / 2))
    for i, j in EDGES:
        c.append(LineString([NODES[i], NODES[j]]).buffer(WIRE_W / 2, cap_style="round"))
    c.append(Point(HUB).buffer(HUB_HOLE / 2 + 2))
    return unary_union(c)

CAV = cavity()

LEG_HOLE = 3.6                    # 底板：LED の足だけ通す穴（つばは底板の上にのる）
SEA_POCKET = 6.2                  # 海の板：LED のつば（Φ5.8）が入る穴

def leg_holes():
    h = []
    for l in leds:
        d = LEG_HOLE if l["kind"] == "led" else LED_D_HOLE   # モジュールは底板の下から LED を差し込む
        h.append(Point(l["x"], l["y"]).buffer(d / 2, quad_segs=16))
    return unary_union(h)

def sea_holes():
    return unary_union([Point(l["x"], l["y"]).buffer((SEA_POCKET if l["kind"] == "led" else LED_D_HOLE) / 2, quad_segs=16) for l in leds])

def layer_base():
    return with_pins(OUTLINE.difference(leg_holes()))

def layer_sea():
    return with_pins(OUTLINE.difference(sea_holes()))

TOWER_HOLE = 2.2                  # 管制塔の模型（3D プリント）を差す穴

def layer_island():
    holes = unary_union([Point(l["x"], l["y"]).buffer(ISLAND_LED_HOLE / 2, quad_segs=16) for l in leds if l["rw"] != "mode"])
    return ISLAND.difference(holes).difference(Point(TOWER_XY).buffer(TOWER_HOLE / 2, quad_segs=12))

def layer_plaque():
    """L5：タイトル板（運用ランプの LED が通る穴つき）。海の板の上、島の横に貼る"""
    return PLAQUE.difference(Point(MODE_LED).buffer(LED_D_HOLE / 2, quad_segs=16))

def layer_terminals():
    """L4：ターミナルと大きな施設（LED・管制塔の穴にかからないように少しよける）"""
    g = unary_union(list(TERMINALS.values()) + [FACILITIES])
    g = g.difference(led_holes().buffer(1.0)).difference(Point(TOWER_XY).buffer(TOWER_HOLE / 2 + 1.0))
    return unary_union([p for p in polys(clean(g)) if p.area >= 1.0])

# ---------------- 刻印 ----------------
def engravings():
    """{層: {"dark": 図形, "light": 図形}}。dark は濃く（滑走路・文字）、light は薄く（エプロン・誘導路）"""
    hole_guard = sea_holes().buffer(0.6)
    isl_in = ISLAND.buffer(-0.4)
    E = {"island": {}, "sea": {}, "terminal": {}, "plaque": {}}
    # 島：滑走路（濃く）、エプロン・誘導路・格納庫（薄く）
    E["island"]["dark"] = (RUNWAYS.union(HANGARS).union(JET_BRIDGES.difference(layer_terminals().buffer(0.1)))
                           .intersection(isl_in).difference(hole_guard))
    light = unary_union([APRONS, TAXIWAYS]).difference(RUNWAYS.buffer(0.3)).difference(layer_terminals().buffer(0.2))
    # ターミナルを貼る位置の目印（輪郭線）
    marks = unary_union([p.exterior.buffer(0.12) for p in polys(layer_terminals())])
    E["island"]["light"] = light.union(marks).intersection(isl_in).difference(hole_guard)
    # 滑走路番号（滑走路の延長線上、島の上ならそこに、海なら海の板に）
    sea_dark = []
    isl_txt = []
    for k, r in rwy.items():
        ux, uy = r["u"]
        ang = math.degrees(math.atan2(uy, ux))
        for name, p, sgn in ((r["ends"][0], r["a"], -1), (r["ends"][1], r["b"], 1)):
            q = (p[0] + sgn * ux * 3.6, p[1] + sgn * uy * 3.6)
            tp = text_poly(name, 2.4, q[0], q[1], ang + (90 if sgn < 0 else -90), font=FONT_B)
            (isl_txt if ISLAND.buffer(-0.3).contains(tp) else sea_dark).append(tp)
    E["island"]["dark"] = E["island"]["dark"].union(unary_union(isl_txt))
    # 海の板：タイトル・方位・縮尺・小さな凡例
    # タイトル・凡例・縮尺はタイトル板（L5）へ
    E["plaque"] = {"dark": plaque_items().difference(Point(MODE_LED).buffer(LED_D_HOLE / 2 + 0.6))}
    nx, ny = Q(197.0, 160.0)
    sea_dark.append(Polygon([(nx, ny + 7), (nx - 3, ny - 4), (nx, ny - 1.5), (nx + 3, ny - 4)]))
    sea_dark.append(text_poly("N", 3.2, nx, ny + 11, font=FONT_B))
    # ボタンの名前
    for name, (x, y) in BTNS:
        sea_dark.append(text_poly(name, 2.3, x, y - BTN_HOLE / 2 - 2.2))
    E["sea"]["dark"] = unary_union(sea_dark).difference(ISLAND.buffer(0.5)).difference(hole_guard)
    # レーダーを置く位置の線（薄く）
    E["sea"]["light"] = unary_union([RADAR_BOX.exterior.buffer(0.15), PLAQUE.exterior.buffer(0.15)]).intersection(OUTLINE.buffer(-0.5))
    # ターミナルの名前
    tt = []
    for k, p in TERMINALS.items():
        c = p.representative_point()
        tt.append(text_poly(k, 2.4, c.x, c.y, font=FONT_B))
    E["terminal"]["dark"] = unary_union(tt).intersection(layer_terminals().buffer(-0.3))
    return E

# =========================================================
#  書き出し
# =========================================================
COLORS = {"dark": "#000000", "light": "#808080"}

def ring_d(coords):
    return "M" + " L".join(f"{x - BX0:.3f},{BH - y:.3f}" for x, y in coords) + " Z"

# 加工ごとにファイルを分ける：laser/<板>/1_彫刻_濃く・2_彫刻_薄く・3_切断（この順に加工する）
#  どのファイルも同じ用紙サイズ・同じ原点。彫刻のファイルには位置合わせ用に切断線を青で入れてある（出力しない）
OPS = [("dark", "1_彫刻_濃く"), ("light", "2_彫刻_薄く")]
GUIDE = "#0000ff"

def _svg_head():
    W, H = BW - BX0 + 10, BH - BY0 + 10
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.3f}mm" height="{H:.3f}mm" viewBox="-5 -5 {W:.3f} {H:.3f}">']

def _svg_rings(g, attrs):
    out = []
    for p in polys(g):
        for ring in [p.exterior] + list(p.interiors):
            out.append(f'<path d="{ring_d(ring.coords)}" {attrs}/>')
    return out

def _svg_fill(g, color):
    out = []
    for p in polys(g):
        d = ring_d(p.exterior.coords) + "".join(ring_d(i.coords) for i in p.interiors)
        out.append(f'<path d="{d}" fill="{color}" fill-rule="evenodd" stroke="none"/>')
    return out

def _dxf(path, items):
    """items: [(レイヤー名, 色番号, 図形)]"""
    import ezdxf
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    for lname, col, g in items:
        doc.layers.add(lname, color=col)
        for p in polys(g):
            for ring in [p.exterior] + list(p.interiors):
                msp.add_lwpolyline(list(ring.coords), close=True, dxfattribs={"layer": lname})
    doc.saveas(path)

# 1 枚の板につき 1 つのファイル（SVG と DXF）。切断と彫刻は同じファイルの中で分けてある
#  SVG：xTool Creative Space が読む加工の種類（data-processing-type）を全部の線・面に付けてある
#    赤の線   … VECTOR_CUTTING（切断）
#    黒の面   … FILL_VECTOR_ENGRAVING（彫刻・濃く：滑走路・文字・小さな建物）
#    灰色の面 … FILL_VECTOR_ENGRAVING（彫刻・薄く：エプロン・誘導路・位置の線）
#  DXF：CUT・ENGRAVE_DARK・ENGRAVE_LIGHT の 3 つのレイヤー
SVG_CUT = 'data-processing-type="VECTOR_CUTTING" fill="none" stroke="#FF0000" stroke-width="0.1"'
SVG_FILL = {"dark": 'data-processing-type="FILL_VECTOR_ENGRAVING" fill="#000000" stroke="none" fill-rule="evenodd"',
            "light": 'data-processing-type="FILL_VECTOR_ENGRAVING" fill="#808080" stroke="none" fill-rule="evenodd"'}
SHEET_MARGIN = 3.0

def _pd(g, ox, oy, H):
    out = []
    for p in polys(g):
        for ring in [p.exterior] + list(p.interiors):
            out.append("M" + " L".join(f"{x - ox:.3f},{H - (y - oy):.3f}" for x, y in ring.coords) + " Z")
    return " ".join(out)

def write_layer(name, cut, eng=None):
    x0, y0, x1, y1 = cut.bounds
    ox, oy = x0 - SHEET_MARGIN, y0 - SHEET_MARGIN            # 板ごとに、その板の大きさ＋余白 3mm の用紙にする
    W, H = x1 - x0 + 2 * SHEET_MARGIN, y1 - y0 + 2 * SHEET_MARGIN
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" viewBox="0 0 {W:.2f} {H:.2f}">',
           f'<g id="{name.split("_")[0]}" data-layer-mode="cut engrave">']
    for kind, label in (("dark", "engrave_dark"), ("light", "engrave_light")):
        g = (eng or {}).get(kind)
        if g is not None and not g.is_empty:
            svg.append(f'<path {SVG_FILL[kind]} d="{_pd(g, ox, oy, H)}"/>')
    svg.append(f'<path {SVG_CUT} d="{_pd(cut, ox, oy, H)}"/>')
    svg += ["</g>", "</svg>"]
    (ROOT / "laser" / f"{name}.svg").write_text("\n".join(svg), encoding="utf-8")
    from shapely import affinity as _af
    sh = lambda g: _af.translate(g, -ox, -oy)
    items = [("ENGRAVE_DARK", 7, sh(eng["dark"])) for _ in [0] if eng and eng.get("dark") is not None and not eng["dark"].is_empty]
    items += [("ENGRAVE_LIGHT", 8, sh(eng["light"])) for _ in [0] if eng and eng.get("light") is not None and not eng["light"].is_empty]
    items.append(("CUT", 1, sh(cut)))
    _dxf(ROOT / "laser" / f"{name}.dxf", items)
    return W, H

def to_json_polys(g, nd=2):
    return [{"o": [[round(x, nd), round(y, nd)] for x, y in p.exterior.coords],
             "h": [[[round(x, nd), round(y, nd)] for x, y in i.coords] for i in p.interiors]} for p in polys(g)]

# 運用のパターン（ふだんの羽田。実物はライブのデータで判定）
MODES = {
    "north": {"label": "北風運用", "on": {"A34L_G": "green", "A16R_R": "red", "C34R_GR": "green", "C34R_Y": "yellow",
                                         "C16L_R": "red", "D05_Y": "yellow", "D23_GR": "red"},
              "mode": "#3d7bff", "use": {"A": "着陸 34L", "B": "使わない", "C": "着陸・離陸 34R", "D": "離陸 05"}},
    "south": {"label": "南風運用", "on": {"A16R_Y": "yellow", "A34L_R": "red", "B22_G": "green", "B04_R": "red",
                                         "C16L_Y": "yellow", "C34R_GR": "red", "D23_GR": "green", "D05_R": "red"},
              "mode": "#ff8a1f", "use": {"A": "離陸 16R", "B": "着陸 22", "C": "離陸 16L", "D": "着陸 23"}},
}

def build():
    E = engravings()
    layers = [
        ("L1_底板", layer_base(), None, 0.0),
        ("L2_海の板", layer_sea(), E["sea"], T),
        ("L3_空港の島", layer_island(), E["island"], 2 * T),
        ("L4_ターミナルと施設", layer_terminals(), E["terminal"], 3 * T),
        ("L5_タイトル板", layer_plaque(), E["plaque"], 2 * T),
    ]
    import shutil
    for f in (ROOT / "laser").glob("*"):
        if f.is_dir():
            shutil.rmtree(f)
        elif f.suffix != ".md":
            f.unlink()
    for name, cut, eng, _ in layers:
        write_layer(name, cut, eng)
    data = {
        "BW": BW, "BH": BH, "T": T, "outline": to_json_polys(OUTLINE),
        "radar": {"box": [RADAR_X0, RADAR_Y0, RADAR_W, RADAR_H], "buttons": [[x, y] for _, (x, y) in BTNS]},
        "layers": [{"name": n, "z": z, "t": T, "polys": to_json_polys(g)} for n, g, _, z in layers],
        "engrave": [{"layer": l, "kind": k, "polys": to_json_polys(g)} for l, d in E.items() for k, g in d.items()],
        "leds": [{k: (round(v, 2) if isinstance(v, float) else v) for k, v in l.items()} for l in leds],
        "runways": {k: {"a": r["a"], "b": r["b"], "ends": r["ends"]} for k, r in rwy.items()},
        "wires": [[NODES[i], NODES[j]] for i, j in EDGES],   # 底板の裏に這わせる線
        "hub": HUB, "tower": TOWER_XY, "modes": MODES,
    }
    (ROOT / "build" / "board.json").write_text(json.dumps(data, ensure_ascii=False))
    return layers, E


def check(layers, E):
    rep = ["# 運用ボード 図面チェック（第4版：ADS-B レーダーと合体）", ""]
    ok = True
    def line(s):
        rep.append(s); print(s)
    rim = min(OUTLINE.exterior.distance(p) for p in polys(sea_holes()))
    line(f"- LED の穴と板の外周の最小距離：{rim:.1f} mm"); ok &= rim >= 5
    gap = min(math.dist((a["x"], a["y"]), (b["x"], b["y"])) for i, a in enumerate(leds) for b in leds[i + 1:])
    line(f"- 隣り合う LED の中心の最小間隔：{gap:.1f} mm（つばの穴 Φ{SEA_POCKET} より大きければ OK）"); ok &= gap > SEA_POCKET
    rd = RADAR_BOX.distance(ISLAND)
    line(f"- レーダーのケースと島のすき間：{rd:.1f} mm、外周までの余白：{OUTLINE.exterior.distance(RADAR_BOX):.1f} mm"); ok &= rd >= 2 and RADAR_BOX.within(OUTLINE.buffer(-4))
    bt = min(Point(x, y).buffer(BTN_HOLE / 2).distance(ISLAND.union(RADAR_BOX)) for _, (x, y) in BTNS)
    line(f"- ボタンの穴と島・レーダーのすき間：{bt:.1f} mm"); ok &= bt >= 1.5 and all(Point(x, y).buffer(BTN_HOLE / 2 + 3).within(OUTLINE) for _, (x, y) in BTNS)
    pi = PLAQUE.intersection(ISLAND.buffer(0.8)).area + PLAQUE.intersection(RADAR_BOX.buffer(0.8)).area + PLAQUE.difference(OUTLINE.buffer(-1.5)).area
    ins = plaque_items().buffer(0.8).within(PLAQUE)
    line(f"- タイトル板の文字が板の内側に収まる（縁から 0.8mm 以上）：{'OK' if ins else '要確認'}"); ok &= ins
    line(f"- タイトル板（{PLAQUE.bounds[2] - PLAQUE.bounds[0]:.0f} × {PLAQUE.bounds[3] - PLAQUE.bounds[1]:.0f} mm）が島・レーダー・板の外にかかる面積：{pi:.2f} mm²"); ok &= pi < 0.01
    lab = _label_area()
    li = lab.intersection(ISLAND.buffer(0.5)).area + lab.difference(OUTLINE.buffer(-1.5)).area + lab.intersection(RADAR_BOX.buffer(1)).area
    line(f"- タイトル・凡例が島・レーダー・板の外にかかる面積：{li:.2f} mm²"); ok &= li < 0.01
    lr = [l["id"] for l in leds if Point(l["x"], l["y"]).buffer(10).intersects(RADAR_HOLE)]
    line(f"- レーダーの穴に近すぎる LED：{lr or 'なし'}"); ok &= not lr
    # LED 同士・LED とターミナル
    holes = [Point(l["x"], l["y"]).buffer(LED_POCKET / 2) for l in leds if l["kind"] == "led"]
    term = layers[3][1]
    hit_t = [l["id"] for l in leds if Point(l["x"], l["y"]).buffer(LED_D_HOLE / 2 + 0.5).intersects(term)]
    line(f"- ターミナルにかかる LED：{hit_t or 'なし'}"); ok &= not hit_t
    on_isl = [l["id"] for l in leds if l["rw"] != "mode" and not ISLAND.buffer(-0.5).contains(Point(l["x"], l["y"]).buffer(ISLAND_LED_HOLE / 2))]
    line(f"- 島からはみ出す滑走路の LED：{on_isl or 'なし'}"); ok &= not on_isl
    # モジュールの穴が他の穴とぶつからないか（同じ溝の中なので重なりは可。板の外に出ないか）
    # モジュールの基板（底板の裏に貼る）が板からはみ出さないか（滑走路のモジュールは滑走路の向きにそろえて貼る）
    for l in leds:
        if l["kind"] != "led":
            pk = sbox(l["x"] - MOD_POCKET[0] / 2, l["y"] - MOD_POCKET[1] / 2, l["x"] + MOD_POCKET[0] / 2, l["y"] + MOD_POCKET[1] / 2)
            if l["rw"] in rwy:
                u = rwy[l["rw"]]["u"]
                pk = affinity.rotate(pk, math.degrees(math.atan2(u[1], u[0])), origin=(l["x"], l["y"]))
            good = pk.within(OUTLINE.buffer(-1.5)) and not pk.intersects(RADAR_HOLE)
            line(f"- {l['id']} のモジュール基板：{'板の内側' if good else 'はみ出す'}"); ok &= good
    ti = term.difference(ISLAND).area
    line(f"- ターミナルが島からはみ出す面積：{ti:.2f} mm²"); ok &= ti < 0.01
    # ターミナルの細い部分
    thin = min(p.buffer(-0.45).area / p.area for p in polys(term))
    line(f"- ターミナルの形：{len(polys(term))} 個（最も細い部分でも 0.9mm 以上：{'OK' if thin > 0 else '要確認'}）")
    # 台数
    from collections import Counter
    c = Counter()
    for l in leds:
        if l["kind"] == "led":
            c[l["color"]] += 1
        else:
            c[l["kind"]] += 1
    line(f"- 使う LED：赤 {c['red']}・緑 {c['green']}・黄 {c['yellow']}（在庫 各 5）、2色LEDモジュール {c['bicolor']}（在庫 2）、RGB LEDモジュール {c['rgb']}（在庫 2）")
    ok &= c["red"] <= 5 and c["green"] <= 5 and c["yellow"] <= 5 and c["bicolor"] <= 2 and c["rgb"] <= 2
    line(f"- 板の外形：{BW - BX0:.0f} × {BH - BY0:.0f} mm（面積 {OUTLINE.area / 100:.0f} cm²。第3版の長方形 290 × 246 は 713 cm²）")
    ok &= ISLAND.within(OUTLINE.buffer(-5))
    # タイトルが島にかからないか
    ok &= Point(MODE_LED).buffer(10).intersection(ISLAND).area < 0.01
    line("")
    line("総合：" + ("問題なし" if ok else "要修正"))
    (ROOT / "laser" / "check_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    return ok


if __name__ == "__main__":
    layers, E = build()
    check(layers, E)
