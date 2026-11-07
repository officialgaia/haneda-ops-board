"""プレビュー画像（外観・断面図）を images/ に出力する"""
from pathlib import Path
import io
import numpy as np
import trimesh
import cadquery as cq
import cairosvg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPoly
from matplotlib import font_manager
import case as C
import check_fit as F

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "images"
IMG.mkdir(exist_ok=True)

# 日本語フォント
for f in font_manager.findSystemFonts():
    if "NotoSansCJK-Regular" in f or "NotoSansCJKjp-Regular" in f:
        font_manager.fontManager.addfont(f)
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()
        break

def to_mesh(w):
    s = w.val() if hasattr(w, "val") else w
    vs, fs = s.tessellate(0.05, 0.2)
    return trimesh.Trimesh([(v.x, v.y, v.z) for v in vs], fs, process=True)

def svg_png(obj, path, size=520):
    cq.exporters.export(obj, "/tmp/_v.svg", opt={"width": size, "height": size, "marginLeft": 10, "marginTop": 10,
                                                  "showAxes": False, "projectionDir": (0, 0, 1), "strokeWidth": 0.3,
                                                  "strokeColor": (30, 40, 50), "showHidden": False})
    cairosvg.svg2png(url="/tmp/_v.svg", write_to=str(path), background_color="white")
    from PIL import Image
    im = Image.open(path).convert("RGB")
    bb = Image.eval(im.convert("L"), lambda p: 255 - p).getbbox()
    im.crop((max(bb[0] - 12, 0), max(bb[1] - 12, 0), bb[2] + 12, bb[3] + 12)).save(path)

COL = {
    "ケース本体": "#9fb7c9", "ふた": "#c9b48f", "液晶": "#3d6fb6", "エンコーダ": "#2f9a5a", "ノブ": "#7a8a84",
    "VIEW": "#d8604a", "LIGHT": "#d8604a", "ESP32": "#7d4fb8", "USB": "#b57a2a", "ブザー": "#d9b21c",
}
def color_for(name):
    for k, v in COL.items():
        if name.startswith(k):
            return v
    return "#888888"

def section(parts, origin, normal, axes, title, path, xlim=None, ylim=None, flipx=False, labels=None):
    fig, ax = plt.subplots(figsize=(6, 7.5), dpi=150)
    for name, w in parts.items():
        m = to_mesh(w)
        sec = m.section(plane_origin=origin, plane_normal=normal)
        if sec is None:
            continue
        for ent in sec.discrete:
            pts = np.array(ent)[:, axes]
            if flipx:
                pts[:, 0] = -pts[:, 0]
            ax.add_patch(MplPoly(pts, closed=True, facecolor=color_for(name), edgecolor="#222", lw=0.4, alpha=0.9))
    ax.set_aspect("equal")
    ax.autoscale_view()
    if xlim: ax.set_xlim(*xlim)
    if ylim: ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=11)
    ax.tick_params(labelsize=7)
    ax.grid(True, lw=0.3, alpha=0.4)
    handles = []
    from matplotlib.patches import Patch
    used = []
    for k, v in COL.items():
        if any(n.startswith(k) for n in parts):
            if v not in [u[1] for u in used]:
                used.append((k, v))
    names = {"ケース本体": "ケース", "ふた": "ふた", "液晶": "液晶", "エンコーダ": "エンコーダ", "ノブ": "ノブ",
             "VIEW": "ボタン", "ESP32": "ESP32-C3", "USB": "USB-C", "ブザー": "ブザー"}
    for k, v in used:
        handles.append(Patch(facecolor=v, edgecolor="#222", label=names.get(k, k)))
    ax.legend(handles=handles, fontsize=7, loc="upper right", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

if __name__ == "__main__":
    shell, lid = C.make_shell(), C.make_lid()
    comps = F.components()
    parts = {"ケース本体": shell, "ふた": lid, **comps}

    # 外観（線画）
    front = shell.rotate((0, 0, 0), (0, 1, 0), 180)
    svg_png(front, IMG / "case_front_view.png")
    svg_png(front.rotate((0, 0, 0), (0, 1, 0), 30).rotate((0, 0, 0), (1, 0, 0), -18), IMG / "case_iso.png")
    svg_png(shell.rotate((0, 0, 0), (0, 1, 0), -28).rotate((0, 0, 0), (1, 0, 0), 22), IMG / "case_inside.png")
    svg_png(lid.rotate((0, 0, 0), (0, 1, 0), -25).rotate((0, 0, 0), (1, 0, 0), 25), IMG / "case_lid.png")
    # 側面（刻印の確認）
    svg_png(shell.rotate((0, 0, 0), (0, 1, 0), 90), IMG / "case_left_side.png")
    svg_png(shell.rotate((0, 0, 0), (0, 1, 0), -90), IMG / "case_right_side.png")

    # スタンドに置いた状態
    import math
    stand = C.make_stand()
    dev = shell.union(lid)
    kx, ky = C.P(C.ENC_X, C.ENC_Y)
    dev = dev.union(C.make_knob().mirror("XY").translate((kx, ky, -C.KNOB_GAP)))
    dev = C.place_on_stand(dev)
    asm = stand.union(dev)
    v = asm.rotate((0, 0, 0), (1, 0, 0), -90 + 12).rotate((0, 0, 0), (0, 1, 0), -30)
    svg_png(v, IMG / "case_on_stand.png", 560)

    # 断面図
    # 1) 正面から見た断面（奥行き z=10 で切る）
    section(parts, (0, 0, 10.0), (0, 0, 1), [0, 1], "断面A：前から見て奥行き10mmの位置", IMG / "section_front_z10.png", flipx=True)
    # 2) 横から見た断面（中央 x で切る）
    section(parts, (C.P(C.ENC_X, 0)[0], 0, 0), (1, 0, 0), [2, 1], "断面B：中央で縦に切って横から見た図（左が前面）", IMG / "section_side_center.png")
    section(parts, (0, C.P(0, C.C3_Y)[1], 0), (0, 1, 0), [0, 2], "断面D：ESP32-C3の高さで横に切って上から見た図（下が前面）",
            IMG / "section_top_esp32.png", flipx=True)
    # 3) 上から見た断面（ボタンの高さ y で切る）
    section(parts, (0, C.P(0, C.BTN_Y)[1], 0), (0, 1, 0), [0, 2], "断面C：ボタンの高さで横に切って上から見た図（下が前面）",
            IMG / "section_top_buttons.png", flipx=True)
    print("rendered")
