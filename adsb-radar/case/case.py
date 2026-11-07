"""
ADS-B レーダー 小型ケース（CadQuery）  v2

  python3 case.py         → stl/ と step/ に印刷用ファイルを出力
  python3 check_fit.py    → 部品の模型を入れて干渉とすき間を検査

座標の決め方
  レイアウト座標：前から見て左上が原点。右へ x、下へ y、奥へ z（mm）
  前面（液晶側）が z=0。前面を下にして印刷する向きのまま出力する。

寸法の出典
  液晶 GMT020-02 … Toppop の外形図（基板 37.25×62.0、厚さ 液晶2.2＋基板1.2、
                    表示部 30.6×40.8、取付穴 φ2.5 が左右 4.5mm・上下 2mm の位置、ピッチ 28×58）
  KY-040         … 販売店の外形 32×19×30（基板26＋ピン6 として扱う）、EC11 の M7 軸受け
  12×12 タクト   … 12×12×7.3、丸キャップ φ13×8
  ESP32-C3 SuperMini … 22.52×18.0、基板厚1.0、USB-C 8.94×7.35×3.26
  アクティブブザー … φ12×9.5、モジュール基板 15×18.5
"""
from pathlib import Path
import math
import cadquery as cq

# =========================================================
#  外形
# =========================================================
WALL = 1.6        # 側面の厚み
FRONT = 1.6       # 前面の厚み
LID_T = 1.6       # ふたの厚み
W = 41.6
H = 83.5
D = 21.0
CORNER_R = 3.0
EDGE_R = 1.2
LID_Z0 = D - LID_T            # ふたの内側の面（z）

# ---- 液晶 GMT020-02 ----
LCD_PCB_W, LCD_PCB_H, LCD_PCB_T = 37.25, 62.0, 1.2
LCD_GLASS_W, LCD_GLASS_H, LCD_GLASS_T = 35.70, 51.20, 2.2
LCD_GLASS_TOP = 5.6           # 基板上端→ガラス上端
LCD_AA_W, LCD_AA_H = 30.6, 40.8
LCD_AA_TOP = 8.3              # 基板上端→表示部上端（図面の 5.6＋2.44 と図の実測の間）
LCD_HOLES = [(4.5, 2.0), (LCD_PCB_W - 4.5, 2.0), (4.5, 60.0), (LCD_PCB_W - 4.5, 60.0)]
LCD_HOLE_D = 2.5
LCD_PIN_Y = 2.8               # 基板上端→ピン列
LCD_X = (W - LCD_PCB_W) / 2   # 基板左端
LCD_Y = WALL + 0.5            # 基板上端
WIN_MARGIN = 0.5
WIN_W, WIN_H = 36.0, 52.0     # 液晶窓の大きさ（実物に合わせて変更。液晶ガラスの中心に合わせて開ける）

# ---- ロータリーエンコーダ（KY-040）----
ENC_X = W / 2 + 1.0           # ピン側が左壁に当たらないよう 1mm 右へ
ENC_Y = LCD_Y + LCD_PCB_H + 0.5 + 6.0
ENC_HOLE = 7.4                # M7 軸受けの穴
ENC_BODY = 12.0               # 本体の幅
ENC_BODY_H = 6.5              # 基板面→本体上面
KY_PCB_L, KY_PCB_W, KY_PCB_T = 26.0, 19.0, 1.6
KY_ENC_FROM_FAR_END = 12.5    # 基板のピンと反対の端→軸の中心
KY_PIN_LEN = 4.0              # ピンは根元から約2mmで切り、そこに線をはんだ付けする（はんだ込み4mm）

# ---- 側面ボタン（12×12×7.3 タクト＋φ13 キャップ）----
BTN_Y = 24.0                  # ボタン中心の高さ
BTN_Z = 12.1                  # ボタン中心の奥行き
BTN_HOLE = 13.6
SW_BODY, SW_BODY_H, SW_TOTAL_H = 12.0, 3.6, 7.3
CAP_D, CAP_H, CAP_TOP_FROM_PCB = 13.0, 8.0, 11.8
CAP_OUT = 1.5                 # キャップが外に出る量
PROTO_Y, PROTO_Z, PROTO_T = 15.0, 13.0, 1.6
BTN_PCB_X = -CAP_OUT + CAP_TOP_FROM_PCB   # 外壁面からボタン基板の表面まで（x）

# ---- ESP32-C3 SuperMini（ふたに横向きに寝かせ、USB-C を右側面から出す）----
C3_L, C3_W, C3_T = 22.52, 18.0, 1.0
C3_USB_W, C3_USB_L, C3_USB_H, C3_USB_OVER = 8.94, 7.35, 3.26, 0.8
C3_RIB = 0.5
C3_Y = 70.0                            # 基板中心の高さ
C3_BOARD_Z1 = LID_Z0 - C3_RIB          # 基板の裏
C3_BOARD_Z0 = C3_BOARD_Z1 - C3_T       # 基板の部品面
USB_Z = C3_BOARD_Z0 - C3_USB_H / 2
C3_USB_FRONT_X = W - WALL - 0.2        # USB-C の先端（右の内壁から 0.2mm）
C3_X1 = C3_USB_FRONT_X - C3_USB_OVER   # 基板の右端
C3_X0 = C3_X1 - C3_L
USB_SLOT_W, USB_SLOT_H, USB_SLOT_R = 13.4, 7.4, 1.5

# ---- ブザー（ふたの裏、音穴の真上）----
BUZ_X, BUZ_Y = W / 2, 44.0
BUZ_D, BUZ_H = 12.0, 9.5
BUZ_PCB_W, BUZ_PCB_L, BUZ_PCB_T = 15.0, 18.5, 1.6

# ---- 電源分配基板（ユニバーサル基板 3列×7行、ふたの内側の左下にホットボンドで貼る）----
PITCH = 2.54
DIST_COLS, DIST_ROWS = 3, 7
DIST_X0, DIST_Y0 = WALL + 2.0, 55.0
DIST_X1, DIST_Y1 = DIST_X0 + DIST_COLS * PITCH, DIST_Y0 + DIST_ROWS * PITCH
DIST_T, DIST_SOLDER = 1.6, 2.5     # 基板の厚み、上面のはんだと線の高さ

# ---- ふたのはめ込み ----
LID_CLEAR = 0.2
SKIRT_T, SKIRT_H = 1.2, 3.0
SNAP_BUMP = 0.5
SNAP_SPANS_TOP = [(W / 2 - 9, W / 2 + 9)]
SNAP_SPANS_BOTTOM = [(W / 2 - 9, W / 2 + 9)]

# =========================================================
#  ユーティリティ
# =========================================================
def P(x, y):
    """レイアウト座標 → CadQuery 座標（前から見た右は CadQuery の -x）"""
    return (W / 2 - x, H / 2 - y)

def box(x0, y0, z0, x1, y1, z1):
    """レイアウト座標の 2 点で囲まれた直方体"""
    cx, cy = P((x0 + x1) / 2, (y0 + y1) / 2)
    return (cq.Workplane("XY").box(abs(x1 - x0), abs(y1 - y0), abs(z1 - z0), centered=(True, True, False))
            .translate((cx, cy, min(z0, z1))))

def cyl_z(x, y, d, z0, z1):
    cx, cy = P(x, y)
    return cq.Workplane("XY").circle(d / 2).extrude(z1 - z0).translate((cx, cy, z0))

def cyl_x(xa, xb, y, z, d):
    """x 方向の円柱（レイアウト x の xa→xb）"""
    ca, cy = P(xa, y)
    cb, _ = P(xb, y)
    lo = min(ca, cb)
    return cq.Workplane("YZ").circle(d / 2).extrude(abs(cb - ca)).translate((lo, cy, z))

def cyl_y(x, ya, yb, z, d):
    cx, ca = P(x, ya)
    _, cb = P(x, yb)
    lo = min(ca, cb)
    return cq.Workplane("XZ").circle(d / 2).extrude(-abs(cb - ca)).translate((cx, lo, z))

INNER_W, INNER_H = W - 2 * WALL, H - 2 * WALL

def win_rect():
    cx = LCD_X + LCD_PCB_W / 2
    cy = LCD_Y + LCD_GLASS_TOP + LCD_GLASS_H / 2
    return cx - WIN_W / 2, cy - WIN_H / 2, cx + WIN_W / 2, cy + WIN_H / 2

# =========================================================
#  本体
# =========================================================
def make_shell():
    body = (cq.Workplane("XY").box(W, H, D, centered=(True, True, False))
            .edges("|Z").fillet(CORNER_R).faces("<Z").edges().fillet(EDGE_R))
    cavity = (cq.Workplane("XY").box(INNER_W, INNER_H, D, centered=(True, True, False))
              .edges("|Z").fillet(CORNER_R - WALL).translate((0, 0, FRONT)))
    s = body.cut(cavity)

    # 液晶の窓と面取り
    x0, y0, x1, y1 = win_rect()
    s = s.cut(box(x0, y0, -1, x1, y1, FRONT + 1))
    cx, cy = P((x0 + x1) / 2, (y0 + y1) / 2)
    s = s.cut(cq.Workplane("XY").rect(x1 - x0 + 1.4, y1 - y0 + 1.4).workplane(offset=0.7)
              .rect(x1 - x0, y1 - y0).loft().translate((cx, cy, 0)))

    # 液晶の取付柱：ガラス厚ぶんの台座＋基板の穴に通るピン
    for hx, hy in LCD_HOLES:
        x, y = LCD_X + hx, LCD_Y + hy
        s = s.union(cyl_z(x, y, 4.0, FRONT, FRONT + LCD_GLASS_T))
        s = s.union(cyl_z(x, y, LCD_HOLE_D - 0.3, FRONT, FRONT + LCD_GLASS_T + LCD_PCB_T + 0.8))

    # エンコーダの穴
    s = s.cut(cyl_z(ENC_X, ENC_Y, ENC_HOLE, -1, FRONT + 1))

    # 側面ボタンの穴と、ボタン基板を受けるレール
    s = s.cut(cyl_x(-1, WALL + 1, BTN_Y, BTN_Z, BTN_HOLE))
    s = s.cut(cyl_x(W - WALL - 1, W + 1, BTN_Y, BTN_Z, BTN_HOLE))
    s = s.union(button_rails("L")).union(button_rails("R"))

    # USB-C の穴（右側面）
    cx, cy = P(W, C3_Y)
    s = s.cut(cq.Workplane("YZ").rect(USB_SLOT_W, USB_SLOT_H).extrude(WALL * 3).edges("|X").fillet(USB_SLOT_R)
              .translate((cx - WALL * 1.5, cy, USB_Z)))

    # ふたのツメが入る溝（上下の内壁。下は USB-C を避けて左右に分ける）
    gz0, gz1 = LID_Z0 - SKIRT_H + 0.9, LID_Z0 - SKIRT_H + 1.7
    for (xa, xb) in SNAP_SPANS_TOP:
        s = s.cut(box(xa - 0.5, WALL - 0.6, gz0, xb + 0.5, WALL + 0.01, gz1))
    for (xa, xb) in SNAP_SPANS_BOTTOM:
        s = s.cut(box(xa - 0.5, H - WALL - 0.01, gz0, xb + 0.5, H - WALL + 0.6, gz1))
    return engrave(s)

def prism_xz(pts, y0, y1):
    """レイアウト座標 (x, z) の多角形を y0〜y1 の範囲に押し出す"""
    cad = [(W / 2 - x, z) for x, z in pts]
    return cq.Workplane("XZ").polyline(cad).close().extrude(y1 - y0).translate((0, H / 2 - y0, 0))

def button_rails(side):
    """ボタン基板（ユニバーサル基板の切れ端）を上下から挟むレールと、押したときに
    基板が奥へ逃げないための受け。下側は45度の斜面で、液晶に当たらずサポートなしで刷れる"""
    z_start = FRONT + LCD_GLASS_T + LCD_PCB_T + 0.4
    reach = BTN_PCB_X + PROTO_T + 1.2
    z_top = LID_Z0 - 0.3
    X = (lambda x: x) if side == "L" else (lambda x: W - x)
    pts = [(X(WALL - 0.01), z_start), (X(reach), z_start + (reach - WALL)), (X(reach), z_top), (X(WALL - 0.01), z_top)]
    out = None
    gap = PROTO_Y / 2 + 0.25
    for sgn in (-1, 1):
        ya, yb = (BTN_Y - gap - 1.2, BTN_Y - gap) if sgn < 0 else (BTN_Y + gap, BTN_Y + gap + 1.2)
        r = prism_xz(pts, ya, yb)
        xs0, xs1 = BTN_PCB_X + PROTO_T + 0.1, reach
        lip_ya, lip_yb = (yb - 0.01, yb + 1.5) if sgn < 0 else (ya - 1.5, ya + 0.01)
        lz0 = z_start + (xs1 - WALL)
        r = r.union(box(X(xs0), lip_ya, lz0, X(xs1), lip_yb, z_top))
        out = r if out is None else out.union(r)
    return out

def engrave(s):
    """側面にボタン名を刻む（外から見て読める向き）"""
    try:
        for side, txt in (("L", "VIEW"), ("R", "LIGHT")):
            t = cq.Workplane("XY").text(txt, 2.6, 0.8, combine=False, halign="center", valign="center",
                                        font="Sans", kind="bold")
            _, cy = P(0, BTN_Y + 10.5)
            if side == "L":
                t = t.rotate((0, 0, 0), (0, 1, 0), 90).translate((W / 2 - 0.4, cy, BTN_Z))
            else:
                t = t.rotate((0, 0, 0), (0, 1, 0), -90).translate((-W / 2 + 0.4, cy, BTN_Z))
            s = s.cut(t)
    except Exception as e:  # noqa
        print("刻印を省略:", e)
    return s

# =========================================================
#  ふた（はめ込み式・ネジなし）
# =========================================================
def make_lid():
    lw, lh = INNER_W - 2 * LID_CLEAR, INNER_H - 2 * LID_CLEAR
    lid = (cq.Workplane("XY").box(lw, lh, LID_T, centered=(True, True, False))
           .edges("|Z").fillet(CORNER_R - WALL - LID_CLEAR).translate((0, 0, LID_Z0)))
    # 上下のスカートとツメ（下は USB-C を避けて左右に分ける）
    z0 = LID_Z0 - SKIRT_H
    for (xa, xb) in SNAP_SPANS_TOP:
        yo = WALL + LID_CLEAR
        lid = lid.union(box(xa, yo, z0, xb, yo + SKIRT_T, LID_Z0 + 0.01))
        lid = lid.union(box(xa + 1, yo - SNAP_BUMP, z0 + 1.0, xb - 1, yo + 0.01, z0 + 1.6))
    for (xa, xb) in SNAP_SPANS_BOTTOM:
        yo = H - WALL - LID_CLEAR
        lid = lid.union(box(xa, yo - SKIRT_T, z0, xb, yo, LID_Z0 + 0.01))
        lid = lid.union(box(xa + 1, yo - 0.01, z0 + 1.0, xb - 1, yo + SNAP_BUMP, z0 + 1.6))

    # ESP32-C3 の受け：基板を 0.5mm 浮かせる2本のレールと、位置決めの壁（USB 側は開けておく）
    for ya, yb in ((C3_Y - C3_W / 2 + 0.5, C3_Y - C3_W / 2 + 2.0), (C3_Y + C3_W / 2 - 2.0, C3_Y + C3_W / 2 - 0.5)):
        lid = lid.union(box(C3_X0 + 1, ya, C3_BOARD_Z1, C3_X1 - 1, yb, LID_Z0 + 0.01))
    gz = C3_BOARD_Z0 + 0.3
    for y0 in (C3_Y - C3_W / 2 - 0.25 - 1.0, C3_Y + C3_W / 2 + 0.25):
        lid = lid.union(box(C3_X0 + 3, y0, gz, C3_X1 - 3, y0 + 1.0, LID_Z0 + 0.01))
    lid = lid.union(box(C3_X0 - 0.25 - 1.0, C3_Y - 5, gz, C3_X0 - 0.25, C3_Y + 5, LID_Z0 + 0.01))

    # USB-C の穴にかかるふたの縁を逃がす
    if USB_Z + USB_SLOT_H / 2 > LID_Z0:
        lid = lid.cut(box(W - WALL - 1.0, C3_Y - USB_SLOT_W / 2, LID_Z0 - 1, W, C3_Y + USB_SLOT_W / 2, LID_Z0 + 0.8))

    # ブザーの音穴と、ブザーの位置合わせリング
    for i in range(-1, 2):
        for j in range(-1, 2):
            lid = lid.cut(cyl_z(BUZ_X + i * 3.0, BUZ_Y + j * 3.0, 1.5, LID_Z0 - 1, D + 1))
    ring = cyl_z(BUZ_X, BUZ_Y, BUZ_D + 2.4, LID_Z0 - 1.2, LID_Z0 + 0.01).cut(
        cyl_z(BUZ_X, BUZ_Y, BUZ_D + 0.4, LID_Z0 - 2, LID_Z0 + 0.1))
    lid = lid.union(ring)
    # 指をかける切り欠き
    lid = lid.cut(box(W / 2 - 6, WALL + LID_CLEAR - 0.1, D - 0.8, W / 2 + 6, WALL + LID_CLEAR + 1.2, D + 1))
    return lid

# =========================================================
#  ノブ（D カット軸 φ6）
# =========================================================
KNOB_D, KNOB_H = 17.0, 19.0     # 軸（ケース前面から約18mm 出る）を切らずに収まる高さ
KNOB_GAP = 0.6                  # 前面とノブのすき間

def make_knob():
    """D カット軸 φ6（平面まで4.5mm）用のノブ。底にナット（M7、対角約11.5mm）の逃げ"""
    k = cq.Workplane("XY").circle(KNOB_D / 2).extrude(KNOB_H).faces(">Z").edges().fillet(1.2)
    for i in range(24):                       # 滑り止めの溝
        g = (cq.Workplane("XY").rect(0.9, 1.2).extrude(KNOB_H - 2).translate((0, KNOB_D / 2 + 0.2, 0))
             .rotate((0, 0, 0), (0, 0, 1), i * 15))
        k = k.cut(g)
    hole = cq.Workplane("XY").circle(3.1).extrude(KNOB_H - 1.0).cut(
        cq.Workplane("XY").rect(10, 10).extrude(KNOB_H).translate((0, 1.55 + 5, 0)))
    k = k.cut(hole)
    k = k.cut(cq.Workplane("XY").circle(6.3).extrude(2.8))      # ナットの逃げ
    k = k.cut(cq.Workplane("XY").circle(3.9).extrude(5.6))      # 軸受け（ネジ部）の逃げ
    return k

# =========================================================
#  スタンド（下面から USB ケーブルを出せるよう、本体を 20mm 浮かせて支える）
# =========================================================
STAND_TILT = 15.0          # 後ろへ傾ける角度
STAND_T = 3.0              # 板の厚み
STAND_LIP = 3.0            # 前の縁の厚み

def _stand_drop():
    L = STAND_LIP + D + 0.4 + STAND_T
    return L * math.sin(math.radians(STAND_TILT))

def place_on_stand(obj):
    """ケース座標の物体を、スタンドに置いた位置へ動かす（床が z=0、前が -y）"""
    o = obj.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 180)
    o = o.translate((0, STAND_LIP, H / 2 + STAND_T))
    return o.rotate((0, 0, 0), (1, 0, 0), -STAND_TILT).translate((0, 0, _stand_drop()))

def make_stand():
    """本体を15度後ろに傾けて置く台。座面は背もたれと直角（本体の底がぴったり乗る）。
    USB-C は右側面から横に出るので、台に当たらない"""
    sw = W + 8
    T, LIP = STAND_T, STAND_LIP
    yb = LIP + D + 0.4                     # 背もたれの前面
    back_h = 46.0
    # 本体と同じ向き（まだ傾けていない）で座面・縁・背もたれを作る
    seat = cq.Workplane("XY").box(sw, yb + T, T, centered=(True, False, False))
    lip = cq.Workplane("XY").box(sw, LIP, T + 2.5, centered=(True, False, False))
    back = cq.Workplane("XY").box(sw, T, back_h, centered=(True, False, False)).translate((0, yb, 0))
    st = seat.union(lip).union(back)
    st = st.rotate((0, 0, 0), (1, 0, 0), -STAND_TILT)
    drop = _stand_drop()
    st = st.translate((0, 0, drop))
    # 座面の下を床まで埋めるくさびと、後ろへ伸ばした脚
    L = yb + T
    c, sn = math.cos(math.radians(STAND_TILT)), math.sin(math.radians(STAND_TILT))
    wedge_pts = [(0, 0), (L * c, 0), (0, drop)]
    wedge = cq.Workplane("YZ").polyline(wedge_pts).close().extrude(sw).translate((-sw / 2, 0, 0))
    foot = cq.Workplane("XY").box(sw, L * c + 14, T, centered=(True, False, False))
    st = st.union(wedge).union(foot)
    for x in (-sw / 2, sw / 2 - 3.0):     # 背もたれを後ろから支えるリブ
        y0 = L * c - 1
        rib = (cq.Workplane("YZ").polyline([(y0, 0), (L * c + 14, 0), (L * c + 14, T), (y0 + 30 * sn, 30 * c)])
               .close().extrude(3.0).translate((x, 0, 0)))
        st = st.union(rib)
    return st

# =========================================================
#  出力
# =========================================================
def export_all():
    out = Path(__file__).resolve().parent
    (out / "stl").mkdir(exist_ok=True)
    (out / "step").mkdir(exist_ok=True)
    for f in list((out / "stl").glob("*.stl")) + list((out / "step").glob("*.step")):
        f.unlink()
    shell, lid, knob, stand = make_shell(), make_lid(), make_knob(), make_stand()
    fit = shell.intersect(cq.Workplane("XY").box(W + 2, H + 2, FRONT + 4.0, centered=(True, True, False)))
    lid_print = lid.translate((0, 0, -D)).mirror("XY")          # 外側を下に
    parts = {"case_front": shell, "case_lid": lid_print, "knob": knob, "stand": stand, "fit_test_front": fit}
    for name, obj in parts.items():
        cq.exporters.export(obj, str(out / "stl" / f"{name}.stl"), tolerance=0.02, angularTolerance=0.15)
        cq.exporters.export(obj, str(out / "step" / f"{name}.step"))
        print("exported", name)
    return shell, lid

if __name__ == "__main__":
    export_all()
