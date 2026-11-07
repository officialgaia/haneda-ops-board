"""
3D プリント部品：レーダーの下に付ける基板のトレー、運用ボードのケース（第3版と同じ）、脚、管制塔の模型

  python3 case3d.py  →  ../stl/*.stl, ../step/*.step

座標：ボードと同じ（mm、x 右、y 北、z 上）。ボードの底面が z=0、机の面が z=-CASE_H。
"""
from pathlib import Path
import math
import cadquery as cq
import board as B

ROOT = Path(__file__).resolve().parent.parent
(ROOT / "stl").mkdir(exist_ok=True)
(ROOT / "step").mkdir(exist_ok=True)

# ---------------- トレー（レーダーの下。基板をしまう） ----------------
#  底板の裏に貼る浅い箱。上はレーダーの穴（L1・L2）につながり、レーダーのケースの中まで空間が続く
WALL, FLOOR = 1.6, 1.2          # 壁はノズル 0.4mm で 4 周、底はハニカムで軽く
HEX_D, HEX_RIB = 9.0, 1.2        # 底のハニカム：六角の穴（角から角）、骨の太さ
CASE_H = 14.0                    # 机からボードの底まで（脚と同じ）
ZB = -CASE_H                     # 机の面
RX0, RY0, RW, RH = B.RADAR_X0, B.RADAR_Y0, B.RADAR_W, B.RADAR_H
X0, X1 = RX0 - 2.0, RX0 + RW + 2.0           # 内側
Y0, Y1 = RY0 - 22.0, RY0 + RH + 2.0
CX, CY = (X0 + X1) / 2, (Y0 + Y1) / 2
C3_L, C3_W, C3_T = 22.52, 18.0, 1.0
C3_USB_W, C3_USB_L, C3_USB_H, C3_USB_OVER = 8.94, 7.35, 3.26, 0.8
RAIL_H = 1.5
C3_X1 = X1 - 0.2 - C3_USB_OVER   # ESP32-C3 の基板の右端（USB-C は右の壁へ）
C3_X0 = C3_X1 - C3_L
C3_Z0 = ZB + FLOOR + RAIL_H
USB_ZC = C3_Z0 + C3_T + C3_USB_H / 2
ESP = {"レーダー": RY0 + 20.0}   # レーダーの ESP32-C3 の中心（y）
BUZ = (CX, RY0 + 43.0)            # ブザー（KY-012）。上はレーダーの穴なので音はケースの中へ抜ける
BUZ_PCB = (15.0, 18.5)
DIST = (X0 + 2.0, RY0 + 20.0, 8.0, 18.0)     # レーダーの電源分配基板（左端 x, 中心 y, 幅, 高さ）

def box(x0, y0, z0, x1, y1, z1):
    return (cq.Workplane("XY").box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), centered=(True, True, False))
            .translate(((x0 + x1) / 2, (y0 + y1) / 2, min(z0, z1))))

def cyl(x, y, d, z0, z1):
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((x, y, z0))

def make_case():
    outer = box(X0 - WALL, Y0 - WALL, ZB, X1 + WALL, Y1 + WALL, 0).edges("|Z").fillet(3.0)
    inner = box(X0, Y0, ZB + FLOOR, X1, Y1, 1).edges("|Z").fillet(1.0)
    c = outer.cut(inner)
    c = c.cut(honeycomb())
    # 上の縁に貼りしろ（内側へ 3mm のつば。ホットボンドや両面テープで底板の裏に貼る）
    lip = box(X0, Y0, -1.2, X1, Y1, 0).cut(box(X0 + 3, Y0 + 3, -2, X1 - 3, Y1 - 3, 1))
    c = c.union(lip)
    # ESP32-C3 のレールと USB-C の穴（右の壁）
    for name, ey in ESP.items():
        for yy in (ey - C3_W / 2 + 1.0, ey + C3_W / 2 - 1.0):
            c = c.union(box(C3_X0 + 1, yy - 1.0, ZB + FLOOR - 0.1, C3_X1 - 1, yy + 1.0, ZB + FLOOR + RAIL_H))
        usb = (cq.Workplane("YZ").rect(12.8, 7.0).extrude(10).edges("|X").fillet(1.5)
               .translate((X1 - 2, ey, USB_ZC)))
        c = c.cut(usb)
    # ブザーの基板の柱
    for dx in (-BUZ_PCB[0] / 2 + 2, BUZ_PCB[0] / 2 - 2):
        for dy in (-BUZ_PCB[1] / 2 + 2, BUZ_PCB[1] / 2 - 2):
            c = c.union(cyl(BUZ[0] + dx, BUZ[1] + dy, 3.0, ZB + FLOOR - 0.1, ZB + FLOOR + 2.0))
    # 電源分配基板・抵抗基板の柱
    for x0, yc, w, h in (DIST,):
        for xx in (x0 + 1.5, x0 + w - 1.5):
            for yy in (yc - h / 2 + 1.5, yc + h / 2 - 1.5):
                c = c.union(cyl(xx, yy, 2.6, ZB + FLOOR - 0.1, ZB + FLOOR + 2.0))
    # ブザーの音の穴（右の壁）
    for k in range(-2, 3):
        c = c.cut(box(X1 - 1, BUZ[1] + k * 3.0 - 0.8, ZB + 4.0, X1 + WALL + 1, BUZ[1] + k * 3.0 + 0.8, ZB + 10.0))
    c = c.cut(wall_windows())
    return c

def honeycomb():
    """底に六角の穴をあける（柱・レールの下と縁は残す）"""
    from shapely.geometry import Point, Polygon as SP, box as sb
    from shapely.ops import unary_union
    keep = [sb(C3_X0, yy - 1.0, C3_X1, yy + 1.0) for ey in ESP.values()
            for yy in (ey - C3_W / 2 + 1.0, ey + C3_W / 2 - 1.0)]                       # ESP32 のレールの下
    for dx in (-BUZ_PCB[0] / 2 + 2, BUZ_PCB[0] / 2 - 2):
        for dy in (-BUZ_PCB[1] / 2 + 2, BUZ_PCB[1] / 2 - 2):
            keep.append(Point(BUZ[0] + dx, BUZ[1] + dy).buffer(1.5))
    for x0, yc, w, h in (DIST,):
        for xx in (x0 + 1.5, x0 + w - 1.5):
            for yy in (yc - h / 2 + 1.5, yc + h / 2 - 1.5):
                keep.append(Point(xx, yy).buffer(1.3))
    keep = unary_union(keep).buffer(HEX_RIB)
    area = sb(X0 + 1.2, Y0 + 1.2, X1 - 1.2, Y1 - 1.2)
    r = HEX_D / 2
    flat = HEX_D * math.cos(math.pi / 6)
    step = flat + HEX_RIB                     # 隣の穴の中心までの距離（六角は x 方向に角が向く）
    dx, dy = step * math.cos(math.pi / 6), step
    def grid(ox, oy):
        pts = []
        i = 0
        x = X0 + ox
        while x < X1:
            y = Y0 + oy + (dy / 2 if i % 2 else 0)
            while y < Y1:
                hexp = SP([(x + r * math.cos(math.radians(60 * k)), y + r * math.sin(math.radians(60 * k))) for k in range(6)])
                if hexp.within(area) and not hexp.intersects(keep):
                    pts.append((x, y))
                y += dy
            x += dx; i += 1
        return pts
    # 穴がいちばん多くなる並べ方を選ぶ
    pts = max((grid(dx * a / 6, dy * b / 6) for a in range(6) for b in range(6)), key=len)
    return (cq.Workplane("XY").pushPoints(pts).polygon(6, HEX_D).extrude(FLOOR + 0.4)
            .translate((0, 0, ZB - 0.2)))

def wall_windows():
    """長い壁（左右）に六角の窓。USB-C・音の穴・配線の入口のまわりと、上下の縁は残す"""
    d, zc = 7.0, ZB + 7.0                # 窓の大きさ（角から角）と高さの中心。上下に 2mm 以上の縁が残る
    step = d * math.cos(math.pi / 6) + 1.6
    avoid = {"L": [], "R": list(ESP.values()) + [BUZ[1]]}
    cut = None
    for side, xw in (("L", X0 - WALL / 2), ("R", X1 + WALL / 2)):
        y = Y0 + 7.0
        while y < Y1 - 7.0:
            if all(abs(y - a) > 12.0 for a in avoid[side]):
                h = (cq.Workplane("YZ").polygon(6, d).extrude(WALL + 2).translate((xw - WALL / 2 - 1, y, zc)))
                cut = h if cut is None else cut.union(h)
            y += step
    return cut

# ---------------- 運用ボードのケース（第3版と同じもの。ESP32-C3 と抵抗基板を入れる） ----------------
L_CASE_IN = (50.0, 34.0)          # 内寸（x, y）
L_WALL, L_FLOOR = 2.0, 2.0
L_CASE_H = 14.0                    # 机からボードの底まで
L_CX, L_CY = B.HUB                   # ケースの中心＝配線の穴の真下
L_C3_L, L_C3_W, L_C3_T = 22.52, 18.0, 1.0
L_C3_USB_W, L_C3_USB_L, L_C3_USB_H, L_C3_USB_OVER = 8.94, 7.35, 3.26, 0.8
L_RAIL_H = 1.5
L_PROTO = (20.0, 15.0, 1.6)        # 抵抗 5 本をのせる小さなユニバーサル基板

L_X0, L_X1 = L_CX - L_CASE_IN[0] / 2, L_CX + L_CASE_IN[0] / 2
L_Y0, L_Y1 = L_CY - L_CASE_IN[1] / 2, L_CY + L_CASE_IN[1] / 2
L_ZB = -L_CASE_H                    # 机の面
L_C3_X1 = L_X1 - 0.2 - L_C3_USB_OVER   # ESP32-C3 の基板の右端（USB-C は右の壁へ）
L_C3_X0 = L_C3_X1 - L_C3_L
L_C3_Z0 = L_ZB + L_FLOOR + L_RAIL_H
L_USB_ZC = L_C3_Z0 + L_C3_T + L_C3_USB_H / 2

def make_led_case():
    outer = box(L_X0 - L_WALL, L_Y0 - L_WALL, L_ZB, L_X1 + L_WALL, L_Y1 + L_WALL, 0).edges("|Z").fillet(3.0)
    inner = box(L_X0, L_Y0, L_ZB + L_FLOOR, L_X1, L_Y1, 1).edges("|Z").fillet(1.0)
    c = outer.cut(inner)
    # 角の補強（上面がボードに貼る面になる）
    for sx, sy in ((L_X0, L_Y0), (L_X1, L_Y0), (L_X0, L_Y1), (L_X1, L_Y1)):
        dx = 7 if sx == L_X0 else -7
        dy = 7 if sy == L_Y0 else -7
        tri = (cq.Workplane("XY").polyline([(sx, sy), (sx + dx, sy), (sx, sy + dy)]).close()
               .extrude(4.0).translate((0, 0, -4.0)))
        c = c.union(tri)
    # ESP32-C3 のレール
    for yy in (L_CY - L_C3_W / 2 + 1.0, L_CY + L_C3_W / 2 - 1.0):
        c = c.union(box(L_C3_X0 + 1, yy - 1.0, L_ZB + L_FLOOR - 0.1, L_C3_X1 - 1, yy + 1.0, L_ZB + L_FLOOR + L_RAIL_H))
    # 抵抗基板の柱
    px0 = L_X0 + 3
    for xx in (px0 + 2, px0 + L_PROTO[0] - 2):
        for yy in (L_CY - L_PROTO[1] / 2 + 2, L_CY + L_PROTO[1] / 2 - 2):
            c = c.union(cyl(xx, yy, 3.0, L_ZB + L_FLOOR - 0.1, L_ZB + L_FLOOR + 3.0))
    # USB-C の穴（右の壁）
    usb = (cq.Workplane("YZ").rect(12.8, 7.0).extrude(10).edges("|X").fillet(1.5)
           .translate((L_X1 - 2, L_CY, L_USB_ZC)))
    c = c.cut(usb)
    # 底板の裏を通ってきた配線の入口（左の壁の上に切り欠き）
    c = c.cut(box(L_X0 - L_WALL - 1, L_CY - 5, -4, L_X0 + 1, L_CY + 5, 1))
    # 底の名前
    c = c.cut(cq.Workplane("XY").text("RJTT", 6, 0.6, kind="bold", halign="center", valign="center")
              .mirror("YZ").translate((L_CX, L_CY, L_ZB)))
    return c

LED_CASE_RECT = (L_X0 - L_WALL, L_Y0 - L_WALL, L_X1 + L_WALL, L_Y1 + L_WALL)

# ---------------- 脚 ----------------
FOOT_D = 16.0
FOOT_ANCHORS = [B.Q(30, 165), B.Q(115, 222), B.Q(108, 94), B.Q(196, 30), B.Q(266, 104)]

def _foot_ok(x, y):
    from shapely.geometry import Point, LineString
    p = Point(x, y)
    if not p.buffer(FOOT_D / 2 + 1.0).within(B.OUTLINE):
        return False
    if any(p.distance(Point(l["x"], l["y"])) < FOOT_D / 2 + 4 for l in B.leds):
        return False
    if any(p.distance(LineString([B.NODES[i], B.NODES[j]])) < FOOT_D / 2 + 2 for i, j in B.EDGES):
        return False
    return not (p.buffer(FOOT_D / 2 + 2).intersects(B.sbox(X0 - WALL, Y0 - WALL, X1 + WALL, Y1 + WALL))
                or p.buffer(FOOT_D / 2 + 2).intersects(B.sbox(*LED_CASE_RECT)))

def _place(ax, ay):
    for r in range(0, 30):
        for k in range(max(1, 8 * r)):
            a = 2 * math.pi * k / max(1, 8 * r)
            x, y = ax + r * math.cos(a), ay + r * math.sin(a)
            if _foot_ok(x, y):
                return (round(x, 1), round(y, 1))
    raise RuntimeError(f"脚の場所が見つからない {ax},{ay}")

FEET = [_place(*a) for a in FOOT_ANCHORS]

def make_foot(x, y):
    f = cyl(x, y, FOOT_D, ZB, 0).faces("<Z").edges().chamfer(1.0)
    return f

# ---------------- レーダーのケースの横のボタン穴をふさぐ栓（ボタンは板へ移したので） ----------------
#  ケースの内側（裏ぶたのない側）から押し込む。つばが内側に当たって止まる
def make_plug():
    return cyl(0, 0, 13.4, 0, 1.6).union(cyl(0, 0, 16.0, -0.8, 0))

# ---------------- 管制塔（高さは見やすく約 3 倍） ----------------
TWR_Z0 = 3 * B.T                  # 島の上面（L3 の上）
def make_tower():
    x, y = B.TOWER_XY
    z = TWR_Z0
    peg = cyl(x, y, 2.0, z - 3.0, z)                        # 島の穴に差す
    base = cyl(x, y, 4.0, z, z + 1.2)
    shaft = (cq.Workplane("XY").circle(1.4).workplane(offset=9.0).circle(1.0).loft()
             .translate((x, y, z + 1.2)))
    cab_z = z + 10.2
    cab = (cq.Workplane("XY").polygon(8, 4.4).workplane(offset=2.2).polygon(8, 5.4).loft()
           .translate((x, y, cab_z)))
    roof = cq.Workplane("XY").polygon(8, 5.8).extrude(0.7).translate((x, y, cab_z + 2.2))
    antenna = cyl(x, y, 0.8, cab_z + 2.9, cab_z + 4.6)
    return peg.union(base).union(shaft).union(cab).union(roof).union(antenna)

def export():
    parts = {"tray": make_case(), "case": make_led_case(), "tower": make_tower()}
    for name, s in parts.items():
        bb = s.val().BoundingBox()
        o = s.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
        cq.exporters.export(o, str(ROOT / "stl" / f"{name}.stl"), tolerance=0.03, angularTolerance=0.15)
        cq.exporters.export(o, str(ROOT / "step" / f"{name}.step"))
    pl = make_plug().translate((0, 0, 0.8))
    cq.exporters.export(pl, str(ROOT / "stl" / "button_plug_x2.stl"), tolerance=0.02, angularTolerance=0.15)
    f = make_foot(*FEET[0])
    bb = f.val().BoundingBox()
    fo = f.translate((-(bb.xmin + bb.xmax) / 2, -(bb.ymin + bb.ymax) / 2, -bb.zmin))
    cq.exporters.export(fo, str(ROOT / "stl" / f"foot_x{len(FEET)}.stl"), tolerance=0.05, angularTolerance=0.2)
    cq.exporters.export(fo, str(ROOT / "step" / f"foot_x{len(FEET)}.step"))
    return parts

if __name__ == "__main__":
    p = export()
    print("脚", FEET)
    for k, v in p.items():
        bb = v.val().BoundingBox()
        print(k, round(bb.xlen, 1), round(bb.ylen, 1), round(bb.zlen, 1), "vol", round(v.val().Volume() / 1000, 2), "cm3")
