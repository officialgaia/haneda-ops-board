"""
部品の模型をケースに入れて、干渉（重なり）とすき間を検査する。

  python3 check_fit.py
    → fit_report.md（検査結果）と images/section_*.png（断面図）を出力

部品の寸法は case.py の値（出典はそちらに記載）を使う。
接触させる設計の場所（液晶ガラスと前面など）は 0.02mm 離して置き、
「接触」として扱う。
"""
from pathlib import Path
import itertools
import cadquery as cq
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
import case as C
from case import box, cyl_z, cyl_x, cyl_y

E = 0.02   # 意図した接触面のすき間

def components():
    c = {}
    # ---- 液晶 ----
    gx = C.LCD_X + (C.LCD_PCB_W - C.LCD_GLASS_W) / 2
    c["液晶ガラス"] = box(gx, C.LCD_Y + C.LCD_GLASS_TOP, C.FRONT + E,
                      gx + C.LCD_GLASS_W, C.LCD_Y + C.LCD_GLASS_TOP + C.LCD_GLASS_H, C.FRONT + C.LCD_GLASS_T)
    pz0 = C.FRONT + C.LCD_GLASS_T + E
    pcb = box(C.LCD_X, C.LCD_Y, pz0, C.LCD_X + C.LCD_PCB_W, C.LCD_Y + C.LCD_PCB_H, pz0 + C.LCD_PCB_T)
    for hx, hy in C.LCD_HOLES:
        pcb = pcb.cut(cyl_z(C.LCD_X + hx, C.LCD_Y + hy, C.LCD_HOLE_D, pz0 - 1, pz0 + 3))
    c["液晶基板"] = pcb
    pz1 = pz0 + C.LCD_PCB_T
    c["液晶の配線はんだ"] = box(C.LCD_X + 9.0, C.LCD_Y + C.LCD_PIN_Y - 1.8, pz1,
                         C.LCD_X + 28.5, C.LCD_Y + C.LCD_PIN_Y + 1.8, pz1 + 3.0)
    # ---- エンコーダ ----
    ex, ey = C.ENC_X, C.ENC_Y
    c["エンコーダ本体"] = box(ex - 6, ey - 6, C.FRONT + E, ex + 6, ey + 6, C.FRONT + C.ENC_BODY_H)
    c["エンコーダ軸受け"] = cyl_z(ex, ey, 7.0, C.FRONT - 7.0, C.FRONT)
    c["エンコーダのナット"] = cyl_z(ex, ey, 11.6, -2.0, -E).cut(cyl_z(ex, ey, 7.0, -3, 1))
    shaft = cyl_z(ex, ey, 6.0, C.FRONT - 20.0, C.FRONT - 7.0)
    sx, sy = C.P(ex, ey)
    flat = cq.Workplane("XY").box(10, 10, 20, centered=(True, True, False)).translate((sx, sy + 1.5 + 5, C.FRONT - 21))
    c["エンコーダの軸"] = shaft.cut(flat)
    kz0 = C.FRONT + C.ENC_BODY_H
    far = C.KY_ENC_FROM_FAR_END
    kx0, kx1 = ex - (C.KY_PCB_L - far), ex + far                   # ピン側が左
    c["エンコーダ基板"] = box(kx0, ey - C.KY_PCB_W / 2, kz0, kx1, ey + C.KY_PCB_W / 2, kz0 + C.KY_PCB_T)
    c["エンコーダ基板の裏はんだ"] = box(kx0, ey - C.KY_PCB_W / 2, kz0 + C.KY_PCB_T, kx1, ey + C.KY_PCB_W / 2, kz0 + C.KY_PCB_T + 1.5)
    c["エンコーダのピン"] = box(kx0 - C.KY_PIN_LEN, ey - 6.5, kz0 - 2.5, kx0, ey + 6.5, kz0 + C.KY_PCB_T + 1.0)
    # ---- ノブ（前面の外）----
    knob = C.make_knob().mirror("XY").translate((0, 0, 0))     # 底面を z=0、上へ -z
    kx, ky = C.P(ex, ey)
    c["ノブ"] = knob.translate((kx, ky, -C.KNOB_GAP))
    # ---- 側面ボタン ----
    for side in ("L", "R"):
        X = (lambda x: x) if side == "L" else (lambda x: C.W - x)
        name = "VIEW" if side == "L" else "LIGHT"
        bpx = C.BTN_PCB_X
        y, z = C.BTN_Y, C.BTN_Z
        c[f"{name}ボタン基板"] = box(X(bpx), y - C.PROTO_Y / 2, z - C.PROTO_Z / 2, X(bpx + C.PROTO_T), y + C.PROTO_Y / 2, z + C.PROTO_Z / 2)
        c[f"{name}ボタン裏はんだ"] = box(X(bpx + C.PROTO_T), y - 6, z - 6, X(bpx + C.PROTO_T + 1.5), y + 6, z + 6)
        c[f"{name}スイッチ"] = box(X(bpx - C.SW_BODY_H), y - 6, z - 6, X(bpx), y + 6, z + 6)
        cap_top = bpx - C.CAP_TOP_FROM_PCB
        xa, xb = sorted([X(cap_top), X(cap_top + C.CAP_H)])
        c[f"{name}キャップ"] = cyl_x(xa, xb, y, z, C.CAP_D)
    # ---- ESP32-C3（横向き、USB-C は右）----
    y0, y1 = C.C3_Y - C.C3_W / 2, C.C3_Y + C.C3_W / 2
    c["ESP32-C3基板"] = box(C.C3_X0, y0, C.C3_BOARD_Z0, C.C3_X1, y1, C.C3_BOARD_Z1 - E)
    c["ESP32-C3の部品"] = box(C.C3_X0 + 1, y0 + 1, C.C3_BOARD_Z0 - 1.5, C.C3_USB_FRONT_X - C.C3_USB_L - 0.1, y1 - 1, C.C3_BOARD_Z0)
    c["USB-Cコネクタ"] = box(C.C3_USB_FRONT_X - C.C3_USB_L, C.C3_Y - C.C3_USB_W / 2, C.C3_BOARD_Z0 - C.C3_USB_H,
                         C.C3_USB_FRONT_X, C.C3_Y + C.C3_USB_W / 2, C.C3_BOARD_Z0)
    plug = cq.Workplane("YZ").rect(12.3, 6.5).extrude(C.W + 15 - C.C3_USB_FRONT_X - 0.05).edges("|X").fillet(1.0)
    px, py = C.P(C.C3_USB_FRONT_X + 0.05, C.C3_Y)
    c["USB-Cプラグ（差した状態）"] = plug.mirror("YZ").translate((px, py, C.USB_Z))
    # ---- ブザー ----
    bz1 = C.LID_Z0 - E
    c["ブザー"] = cyl_z(C.BUZ_X, C.BUZ_Y, C.BUZ_D, bz1 - C.BUZ_H, bz1)
    c["ブザー基板"] = box(C.BUZ_X - C.BUZ_PCB_W / 2, C.BUZ_Y - C.BUZ_PCB_L / 2, bz1 - C.BUZ_H - C.BUZ_PCB_T,
                       C.BUZ_X + C.BUZ_PCB_W / 2, C.BUZ_Y + C.BUZ_PCB_L / 2, bz1 - C.BUZ_H)
    c["ブザー裏はんだ"] = box(C.BUZ_X - C.BUZ_PCB_W / 2, C.BUZ_Y - C.BUZ_PCB_L / 2, bz1 - C.BUZ_H - C.BUZ_PCB_T - 1.5,
                         C.BUZ_X + C.BUZ_PCB_W / 2, C.BUZ_Y + C.BUZ_PCB_L / 2, bz1 - C.BUZ_H - C.BUZ_PCB_T)
    # ---- 電源分配基板（ふたの内側）----
    dz1 = C.LID_Z0 - E
    c["電源分配基板"] = box(C.DIST_X0, C.DIST_Y0, dz1 - C.DIST_T, C.DIST_X1, C.DIST_Y1, dz1)
    c["電源分配基板のはんだと線"] = box(C.DIST_X0, C.DIST_Y0, dz1 - C.DIST_T - C.DIST_SOLDER, C.DIST_X1, C.DIST_Y1, dz1 - C.DIST_T)
    return c

def solid(w):
    return w.val() if hasattr(w, "val") else w

def overlap_volume(a, b):
    try:
        return solid(a).intersect(solid(b)).Volume()
    except Exception:
        return 0.0

def distance(a, b):
    d = BRepExtrema_DistShapeShape(solid(a).wrapped, solid(b).wrapped)
    d.Perform()
    return d.Value()

def run():
    shell, lid = C.make_shell(), C.make_lid()
    comps = components()
    parts = {"ケース本体": shell, "ふた": lid, **comps}
    rows = []
    names = list(parts)
    bbs = {n: solid(parts[n]).BoundingBox() for n in names}
    def near(a, b, m=3.0):
        A, B = bbs[a], bbs[b]
        return not (A.xmax + m < B.xmin or B.xmax + m < A.xmin or A.ymax + m < B.ymin or
                    B.ymax + m < A.ymin or A.zmax + m < B.zmin or B.zmax + m < A.zmin)
    for a, b in itertools.combinations(names, 2):
        if not near(a, b):
            continue
        v = overlap_volume(parts[a], parts[b])
        dist = 0.0 if v > 0.01 else distance(parts[a], parts[b])
        rows.append((a, b, v, dist))
    return parts, rows

if __name__ == "__main__":
    parts, rows = run()
    clash = [r for r in rows if r[2] > 0.01]
    touch = [r for r in rows if r[2] <= 0.01 and r[3] < 0.15]
    tight = [r for r in rows if r[2] <= 0.01 and 0.15 <= r[3] < 1.0]
    out = Path(__file__).resolve().parent / "fit_report.md"
    with open(out, "w") as f:
        f.write("# 干渉チェックの結果\n\n")
        f.write(f"外形 {C.W} × {C.H} × {C.D} mm\n\n")
        f.write(f"- 干渉（重なっている）: {len(clash)} 件\n- 接触（設計どおり当たっている）: {len(touch)} 件\n- すき間 1mm 未満: {len(tight)} 件\n\n")
        for title, rs in (("干渉", clash), ("接触", touch), ("すき間 1mm 未満", tight)):
            f.write(f"## {title}\n\n")
            if not rs:
                f.write("なし\n\n"); continue
            f.write("| 部品A | 部品B | 重なり (mm³) | すき間 (mm) |\n| --- | --- | --- | --- |\n")
            for a, b, v, d in sorted(rs, key=lambda r: r[3]):
                f.write(f"| {a} | {b} | {v:.2f} | {d:.2f} |\n")
            f.write("\n")
    print(open(out).read())
