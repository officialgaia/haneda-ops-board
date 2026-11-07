"""
配線図（PDF 3 ページ ＋ PNG）
  1. LED の配線の全体図（上から見た図。5 色の帯と LED の番号）
  2〜3. LED ごとのカード（足 → 線の色）
  4. 一覧表と回路のしくみ
  5. 底板の裏の型紙（実寸・裏から見た向き）：A3 に 100% で印刷して底板に当てる
  6. 抵抗基板
  7. レーダーとの合体

  python3 wiring.py
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
from matplotlib import font_manager as fm

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
fm.fontManager.addfont("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
plt.rcParams["font.family"] = "Noto Sans CJK JP"

PINS = [3, 4, 5, 6, 7]
# 線の色は LED の色（赤・緑・黄）と同じ名前を避ける。番号は 1〜5（プログラムの中では 0〜4）
WCOL = ["#8b5a2b", "#8e44ad", "#1f77b4", "#8c8c8c", "#f4f4f4"]     # 茶・紫・青・灰・白
WNAME = ["茶", "紫", "青", "灰", "白"]
def WN(k):
    return f"線{k + 1}（{WNAME[k]}）"
# ファームウェア（haneda_board.ino）と同じ表：(場所, 種類, アノード線, カソード線, 部品 id)
LEDS = [
    ("A 16R", "黄 LED", 1, 0, "A16R_Y"), ("A 16R", "赤 LED", 0, 1, "A16R_R"),
    ("A 34L", "緑 LED", 2, 0, "A34L_G"), ("A 34L", "赤 LED", 2, 1, "A34L_R"),
    ("B 04", "赤 LED", 3, 0, "B04_R"), ("B 22", "緑 LED", 3, 1, "B22_G"),
    ("C 16L", "黄 LED", 4, 0, "C16L_Y"), ("C 16L", "赤 LED", 4, 1, "C16L_R"),
    ("C 34R", "2色モジュール 緑", 0, 3, "C34R_GR"), ("C 34R", "2色モジュール 赤", 1, 3, "C34R_GR"),
    ("C 34R", "黄 LED", 3, 2, "C34R_Y"),
    ("D 05", "黄 LED", 4, 2, "D05_Y"), ("D 05", "赤 LED", 2, 3, "D05_R"),
    ("D 23", "2色モジュール 緑", 0, 2, "D23_GR"), ("D 23", "2色モジュール 赤", 1, 2, "D23_GR"),
    ("運用ランプ", "RGB モジュール R", 0, 4, "MODE_RGB"), ("運用ランプ", "RGB モジュール G", 1, 4, "MODE_RGB"),
    ("運用ランプ", "RGB モジュール B", 2, 4, "MODE_RGB"),
]
# 部品ごとの番号（カード・型紙・点検モードの番号）。(番号, id, 場所, 部品, [(足・ピン, 線)])
PARTS = [
    (1, "A16R_Y", "A 滑走路 16R の端", "黄 LED", [("＋ 長い足", 1), ("− 短い足", 0)]),
    (2, "A16R_R", "A 滑走路 16R の端", "赤 LED", [("＋ 長い足", 0), ("− 短い足", 1)]),
    (3, "A34L_G", "A 滑走路 34L の端", "緑 LED", [("＋ 長い足", 2), ("− 短い足", 0)]),
    (4, "A34L_R", "A 滑走路 34L の端", "赤 LED", [("＋ 長い足", 2), ("− 短い足", 1)]),
    (5, "B04_R", "B 滑走路 04 の端", "赤 LED", [("＋ 長い足", 3), ("− 短い足", 0)]),
    (6, "B22_G", "B 滑走路 22 の端", "緑 LED", [("＋ 長い足", 3), ("− 短い足", 1)]),
    (7, "C16L_Y", "C 滑走路 16L の端", "黄 LED", [("＋ 長い足", 4), ("− 短い足", 0)]),
    (8, "C16L_R", "C 滑走路 16L の端", "赤 LED", [("＋ 長い足", 4), ("− 短い足", 1)]),
    (9, "C34R_GR", "C 滑走路 34R の端", "2色 LED モジュール", [("− ピン", 3), ("緑のピン", 0), ("赤のピン", 1)]),
    (10, "C34R_Y", "C 滑走路 34R の端", "黄 LED", [("＋ 長い足", 3), ("− 短い足", 2)]),
    (11, "D05_Y", "D 滑走路 05 の端", "黄 LED", [("＋ 長い足", 4), ("− 短い足", 2)]),
    (12, "D05_R", "D 滑走路 05 の端", "赤 LED", [("＋ 長い足", 2), ("− 短い足", 3)]),
    (13, "D23_GR", "D 滑走路 23 の端", "2色 LED モジュール", [("− ピン", 2), ("緑のピン", 0), ("赤のピン", 1)]),
    (14, "MODE_RGB", "タイトル板の運用ランプ", "RGB LED モジュール", [("− ピン", 4), ("R ピン", 0), ("G ピン", 1), ("B ピン", 2)]),
]
LEDCOL = {"黄 LED": "#ffcc00", "赤 LED": "#ff3b30", "緑 LED": "#2ecc40"}
BOARD = json.loads((ROOT / "build" / "board.json").read_text())

from matplotlib.patches import Polygon as MPoly
import math

def chip(ax, x, y, k, w=0.07, h=0.045, size=11, transform=None):
    """線の色の札（番号入り）"""
    tr = transform or ax.transAxes
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.004,rounding_size=0.01",
                                fc=WCOL[k], ec="#333", lw=0.8, transform=tr))
    ax.text(x, y, f"線{k + 1}", ha="center", va="center", fontsize=size, weight="bold",
            color="#222" if k >= 3 else "white", transform=tr)

def draw_board(ax, mirror=False, island=True):
    BW, BH = BOARD["BW"], BOARD["BH"]
    for p in BOARD["outline"]:
        ax.add_patch(MPoly(p["o"], closed=True, fc="#fbf6e6", ec="#777", lw=0.8))
    if island:
        for L in BOARD["layers"]:
            if L["name"].startswith("L3"):
                for p in L["polys"]:
                    ax.add_patch(MPoly(p["o"], closed=True, fc="#f3e6b8", ec="#c9b98d", lw=0.5))
    ax.set_aspect("equal"); ax.axis("off")
    if mirror:
        ax.set_xlim(BW + 2, -2)
    else:
        ax.set_xlim(-2, BW + 2)
    ax.set_ylim(-2, BH + 2)

def draw_ribbon(ax, step=0.9, lw=1.6):
    """5 本の線の通り道を、5 色の平行な線で描く"""
    for (p, q) in BOARD["wires"]:
        dx, dy = q[0] - p[0], q[1] - p[1]
        L = math.hypot(dx, dy) or 1
        nx, ny = -dy / L, dx / L
        for k in range(5):
            o = (k - 2) * step
            ax.plot([p[0] + nx * o, q[0] + nx * o], [p[1] + ny * o, q[1] + ny * o], color=WCOL[k], lw=lw,
                    solid_capstyle="butt", zorder=3, path_effects=None)
        ax.plot([p[0], q[0]], [p[1], q[1]], color="#555", lw=lw * 5.2 + 1.2, alpha=0.18, zorder=2, solid_capstyle="round")

def draw_case(ax):
    lx0, ly0, lx1, ly1 = BOARD["case"]["led_case"]
    ax.add_patch(Rectangle((lx0, ly0), lx1 - lx0, ly1 - ly0, fc="#dfe6ec", ec="#3b4a57", lw=1.2, zorder=7))
    ax.text((lx0 + lx1) / 2, (ly0 + ly1) / 2 + 4, "ケース", ha="center", va="center", fontsize=9, weight="bold", color="#3b4a57", zorder=8)
    ax.text((lx0 + lx1) / 2, (ly0 + ly1) / 2 - 4, "ESP32・抵抗", ha="center", va="center", fontsize=7, color="#3b4a57", zorder=8)

def badge_pos(lid, d=7.0):
    """番号の札の位置：いちばん近い LED と反対の向きへずらす（並んだ 2 個が重ならないように）"""
    by = {l["id"]: l for l in BOARD["leds"]}
    l = by[lid]
    others = [o for o in BOARD["leds"] if o["id"] != lid]
    o = min(others, key=lambda o: math.hypot(o["x"] - l["x"], o["y"] - l["y"]))
    dx, dy = l["x"] - o["x"], l["y"] - o["y"]
    L = math.hypot(dx, dy) or 1
    if L > 20:                      # 近くに LED がなければ右上へ
        dx, dy, L = 1, 1, math.sqrt(2)
    return l["x"] + dx / L * d, l["y"] + dy / L * d

def num_badge(ax, x, y, n, r=4.2, fs=9):
    ax.add_patch(Circle((x, y), r, fc="#1c2d4a", ec="white", lw=1.2, zorder=6))
    ax.text(x, y, str(n), ha="center", va="center", fontsize=fs, weight="bold", color="white", zorder=7)

def legend_wires(fig, x, y, dy=0.035, size=10):
    for k in range(5):
        fig.patches.append(FancyBboxPatch((x, y - k * dy - 0.012), 0.05, 0.024, boxstyle="round,pad=0.003",
                                          fc=WCOL[k], ec="#333", lw=0.8, transform=fig.transFigure, figure=fig))
        fig.text(x + 0.025, y - k * dy, f"線{k + 1}", ha="center", va="center", fontsize=size - 1, weight="bold",
                 color="#222" if k >= 3 else "white")
        fig.text(x + 0.06, y - k * dy, f"{WNAME[k]}　GPIO{PINS[k]}（47Ω を通す）", va="center", fontsize=size - 1)

# ------------------------------------------------------------
#  線ごとのつなぐ順番：ケースから出て、その線につなぐ足を順番にたどる 1 本の道（枝分かれなし）
import itertools
def wire_stops(k):
    by = {l["id"]: l for l in BOARD["leds"]}
    out = []
    for n, lid, place, kind, pins in PARTS:
        for label, w in pins:
            if w == k:
                out.append(dict(n=n, lid=lid, label=label, kind=kind, x=by[lid]["x"], y=by[lid]["y"]))
    return out

def chain(k):
    """ケースの切り欠きから全部の足を通る、いちばん短い順番"""
    start = tuple(BOARD["case"]["led_case_notch"])
    st = wire_stops(k)
    best, bl = None, 1e9
    for perm in itertools.permutations(range(len(st))):
        p, L = start, 0.0
        for i in perm:
            L += math.hypot(st[i]["x"] - p[0], st[i]["y"] - p[1]); p = (st[i]["x"], st[i]["y"])
            if L >= bl:
                break
        if L < bl:
            bl, best = L, perm
    return start, [st[i] for i in best]

def exit_path(start, target):
    """ケースの切り欠きから最初の足まで：ケースの上を通らないよう、角を回る点を足す"""
    from shapely.geometry import LineString, box as sb
    lx0, ly0, lx1, ly1 = BOARD["case"]["led_case"]
    case = sb(lx0, ly0, lx1, ly1).buffer(-0.5)
    p0 = (start[0] - 4, start[1])                       # 切り欠きの少し外
    if not LineString([p0, target]).intersects(case):
        return [start, p0]
    cands = [(lx0 - 4, ly0 - 4), (lx0 - 4, ly1 + 4)]
    best = min(cands, key=lambda c: math.dist(p0, c) + math.dist(c, target))
    return [start, p0, best]

def path_len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

def cut_len(d, first=False):
    """切る長さ（mm）：まっすぐの距離に余裕 25mm（最初の 1 本はケースの中の分も 40mm 足す）。5mm 単位に切り上げ"""
    v = d + 25 + (40 if first else 0)
    return int(math.ceil(v / 5.0) * 5)

def leg_text(label):
    return {"＋ 長い足": "＋（長い足）", "− 短い足": "−（短い足）"}.get(label, label)

def draw_chains(ax, only=None, lw=2.2, label_steps=False):
    for k in range(5):
        if only is not None and k != only:
            continue
        start, st = chain(k)
        pre = exit_path(start, (st[0]["x"], st[0]["y"]))
        pts = pre + [(s_["x"], s_["y"]) for s_ in st]
        xs, ys = zip(*pts)
        if WCOL[k] == "#f4f4f4":
            ax.plot(xs, ys, color="#555", lw=lw + 1.4, zorder=3, solid_capstyle="round")
        ax.plot(xs, ys, color=WCOL[k], lw=lw, zorder=4, solid_capstyle="round")
        if label_steps:
            for i, (x, y) in enumerate(pts[len(pre):], 1):
                s_ = st[i - 1]
                ax.add_patch(Circle((x, y), 1.6, fc=WCOL[k], ec="#222", lw=0.8, zorder=8))
                bx, by_ = badge_pos(s_["lid"], 7.0)
                ax.plot([x, bx], [y, by_], color="#222", lw=0.7, zorder=8)
                x, y = bx, by_
                ax.text(x, y, str(i), ha="center", va="center", fontsize=9, weight="bold", zorder=9,
                        color="#222" if k >= 3 else "white",
                        bbox=dict(boxstyle="circle,pad=0.28", fc=WCOL[k], ec="#222", lw=0.9))
                ax.text(x, y - 7.5, f"No.{s_['n']}", ha="center", va="center", fontsize=7, color="#1c2d4a", zorder=9,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

def page_wire(pdf, k):
    """線 1 本ぶんの手順（裏から見た図）"""
    CS = BOARD["case"]
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.03, 0.955, f"LED の配線　線{k + 1}（{WNAME[k]}）をつなぐ順番", fontsize=17, weight="bold")
    fig.text(0.03, 0.92, "板を裏返して、裏から見た向きの図です（左右が逆）。ケースから出て、①→②→… の順に足をつないでいく。"
             "途中の足には「来た線」と「次へ行く線」の 2 本をいっしょにはんだ付けする。", fontsize=9.5, color="#333")
    ax = fig.add_axes([0.02, 0.03, 0.58, 0.86])
    draw_board(ax, mirror=True)
    for fx, fy in CS["feet"]:
        ax.add_patch(Circle((fx, fy), CS["foot_d"] / 2, fc="#e6e9ec", ec="#9aa5b1", lw=0.8, zorder=2))
    lx0, ly0, lx1, ly1 = CS["led_case"]
    ax.add_patch(Rectangle((lx0, ly0), lx1 - lx0, ly1 - ly0, fc="#dfe6ec", ec="#3b4a57", lw=1.2, zorder=5))
    ax.text((lx0 + lx1) / 2, (ly0 + ly1) / 2, "ケース", ha="center", va="center", fontsize=9, weight="bold", color="#3b4a57", zorder=6)
    for l in BOARD["leds"]:
        ax.add_patch(Circle((l["x"], l["y"]), 2.2, fc="white", ec="#aaa", lw=0.8, zorder=6))
    draw_chains(ax, only=k, lw=3.0, label_steps=True)
    start, st = chain(k)
    # 右：手順の表
    t = fig.add_axes([0.62, 0.03, 0.36, 0.86]); t.axis("off"); t.set_xlim(0, 1); t.set_ylim(0, 1)
    chip(t, 0.08, 0.97, k, w=0.15, h=0.05, size=12)
    t.text(0.18, 0.97, f"{WNAME[k]}の線　GPIO{PINS[k]} → 47Ω → 抵抗基板の G 列 {k + 1} 行目", va="center", fontsize=9.5)
    y = 0.90
    t.text(0.0, y, "順番", fontsize=9, weight="bold"); t.text(0.13, y, "つなぐ LED と足", fontsize=9, weight="bold"); t.text(0.80, y, "線の長さ", fontsize=9, weight="bold")
    y -= 0.05
    prev = start
    total = 0
    for i, s_ in enumerate(st, 1):
        d = math.hypot(s_["x"] - prev[0], s_["y"] - prev[1]) if i > 1 else path_len(exit_path(start, (s_["x"], s_["y"])) + [(s_["x"], s_["y"])])
        L = cut_len(d, first=(i == 1))
        total += L
        frm = "　← 抵抗基板から" if i == 1 else ""
        t.add_patch(Rectangle((-0.01, y - 0.03), 1.02, 0.06, fc="#f4f6f8" if i % 2 else "white", ec="none"))
        t.text(0.04, y, str(i), ha="center", va="center", fontsize=10, weight="bold", color="#222" if k >= 3 else "white",
               bbox=dict(boxstyle="circle,pad=0.25", fc=WCOL[k], ec="#222", lw=0.8))
        t.text(0.13, y + 0.008, f"No.{s_['n']} {s_['kind'].replace(' モジュール', '')}", va="center", fontsize=10, weight="bold")
        t.text(0.13, y - 0.018, f"{leg_text(s_['label'])}{frm}", va="center", fontsize=9, color="#c0392b" if "＋" in s_["label"] else "#2c3e50")
        t.text(0.80, y, f"{L} mm", va="center", fontsize=10)
        y -= 0.065
        prev = (s_["x"], s_["y"])
    y -= 0.01
    t.text(0.0, y, f"切る線：{len(st)} 本（合計 約 {total / 10:.0f} cm）", fontsize=10, weight="bold")
    y -= 0.05
    notes = ["・線の長さは余裕込み。先に全部切って、番号のテープを貼っておく",
             "・最後の足（いちばん大きい番号）は 1 本だけ",
             "・つないだ足は熱収縮チューブかテープで包み、ほかの足に触れないように",
             "・線は底板の裏にテープで留め、脚（灰色の丸）はよけて通す",
             f"・この線が終わったら、次は 線{k + 2}" if k < 4 else "・これで 5 本とも終わり。電源を入れて 1 → 14 の順に光るか確かめる"]
    for n_ in notes:
        t.text(0.0, y, n_, fontsize=8.5); y -= 0.04
    pdf.savefig(fig); fig.savefig(HERE / f"{3 + k}_線{k + 1}_{WNAME[k]}_つなぐ順番.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------
def page_overview(pdf):
    """1：全体図（上から見た図）"""
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.03, 0.955, "LED の配線　1. 全体図（上から見た図）", fontsize=17, weight="bold")
    fig.text(0.03, 0.92, "線は 1 本ずつつなぐ。線1（茶）から始めて、ケースから出て決まった順番に LED の足をたどる（3〜7 ページに 1 本ずつ）。"
             "色の線は、5 本をつなぎ終わったときの様子。", fontsize=9.5, color="#333")
    ax = fig.add_axes([0.02, 0.03, 0.66, 0.86])
    draw_board(ax)
    draw_chains(ax, lw=2.0)
    draw_case(ax)
    by = {l["id"]: l for l in BOARD["leds"]}
    for n, lid, place, kind, pins in PARTS:
        l = by[lid]
        bx, by_ = badge_pos(lid, 7.5)
        ax.plot([l["x"], bx], [l["y"], by_], color="#1c2d4a", lw=0.8, zorder=5)
        ax.add_patch(Circle((l["x"], l["y"]), 1.6, fc="white", ec="#1c2d4a", lw=1, zorder=6))
        num_badge(ax, bx, by_, n)
    # 右：線の色と手順
    legend_wires(fig, 0.71, 0.84)
    steps = [
        "手順",
        "① LED をすべて差してから L3 を貼り、板を裏返す",
        "② 線1 のページを見て、書いてある長さの線を切る",
        "③ 抵抗基板 → ① → ② … の順に足へはんだ付け",
        "④ 線2 → 線3 → 線4 → 線5 と、1 本ずつ同じようにする",
        "⑤ はんだの所を熱収縮チューブかテープで包む",
        "⑥ 電源を入れると 1 → 14 の順に光る。",
        "　 光らない番号は、カード（8・9 ページ）で確かめる",
        "",
        "見分け方",
        "・LED の＋は長い足（ふちの丸い側）",
        "・LED の−は短い足（ふちが平らな側）",
        "・1 つの LED の 2 本の足は、必ず違う線につながる",
    ]
    for i, t in enumerate(steps):
        fig.text(0.71, 0.62 - i * 0.034, t, fontsize=10 if i in (0, 9) else 9, weight="bold" if i in (0, 9) else "normal")
    pdf.savefig(fig); fig.savefig(HERE / "1_全体図.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------
def draw_led(ax, kind, pins):
    """部品を横向きに描き、足（ピン）をまっすぐ右へ伸ばして線の札につなぐ（ax は 0〜1 の座標）"""
    n = len(pins)
    ys = [0.66, 0.30] if n == 2 else [0.82, 0.60, 0.38, 0.16][:n]
    single = n == 2
    if single:
        c = LEDCOL[kind]
        # 横向きの LED：左が頭、右へ足
        ax.add_patch(FancyBboxPatch((0.02, 0.33), 0.20, 0.30, boxstyle="round,pad=0,rounding_size=0.12", fc=c, ec="#555", lw=1))
        ax.add_patch(Rectangle((0.20, 0.30), 0.035, 0.36, fc=c, ec="#555", lw=1))
        ax.text(0.12, 0.20, "ふちの平らな側が −", ha="center", fontsize=7, color="#666")
        x_leg0 = 0.235
        ends = [0.60, 0.50]                       # 長い足は長く、短い足は短く
        ycen = [0.56, 0.40]
        for (label, k), y, ye, xe in zip(pins, ys, ycen, ends):
            ax.plot([x_leg0, x_leg0 + 0.05, xe], [ye, y, y], color="#888", lw=3, solid_capstyle="round")
            ax.plot([xe, 0.62], [y, y], color="#bbb", lw=1, ls=":")
            ax.text(0.30, y + 0.07, label, fontsize=9, weight="bold", color="#c0392b" if "＋" in label else "#2c3e50")
            chip(ax, 0.74, y, k, w=0.22, h=0.14, size=12)
            ax.text(0.865, y, WNAME[k], va="center", fontsize=11)
    else:
        # モジュール：左に基板、ピンを右へ
        top, bot = ys[0] + 0.1, ys[-1] - 0.1
        ax.add_patch(Rectangle((0.02, bot), 0.18, top - bot, fc="#2e6b3a", ec="#1f4a28", lw=1))
        ax.add_patch(Circle((0.10, (top + bot) / 2), 0.06, fc="#ffffff" if n == 4 else "#ffd27f", ec="#555"))
        for (label, k), y in zip(pins, ys):
            ax.plot([0.20, 0.52], [y, y], color="#bbb", lw=3, solid_capstyle="round")
            ax.plot([0.52, 0.62], [y, y], color="#bbb", lw=1, ls=":")
            ax.text(0.24, y + 0.05, label, fontsize=9, weight="bold", color="#2c3e50")
            chip(ax, 0.74, y, k, w=0.22, h=0.13, size=12)
            ax.text(0.865, y, WNAME[k], va="center", fontsize=11)
        ax.text(0.24, 0.0, "ピンの名前は基板の印刷で確かめる", fontsize=7, color="#666")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

def page_cards(pdf, parts, title, fname):
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.03, 0.955, title, fontsize=17, weight="bold")
    fig.text(0.03, 0.92, "番号は全体図・型紙・電源を入れたときの点検の順番と同じ。LED ごとに、どの足がどの色の線につながっているかを確かめるときに使う。", fontsize=9.5, color="#333")
    by = {l["id"]: l for l in BOARD["leds"]}
    cols, rows = 4, 2
    for i, (n, lid, place, kind, pins) in enumerate(parts):
        r, c = divmod(i, cols)
        x0, y0, w, h = 0.03 + c * 0.24, 0.48 - r * 0.44, 0.225, 0.41
        bg = fig.add_axes([x0, y0, w, h]); bg.axis("off"); bg.set_xlim(0, 1); bg.set_ylim(0, 1)
        bg.add_patch(FancyBboxPatch((0.01, 0.01), 0.98, 0.98, boxstyle="round,pad=0,rounding_size=0.03",
                                    fc="white", ec="#9aa5b1", lw=1))
        # 見出し
        hx = fig.add_axes([x0 + 0.008, y0 + h - 0.075, 0.06, 0.07]); hx.axis("off"); hx.set_xlim(0, 1); hx.set_ylim(0, 1); hx.set_aspect("equal")
        hx.add_patch(Circle((0.5, 0.5), 0.45, fc="#1c2d4a")); hx.text(0.5, 0.5, str(n), ha="center", va="center", fontsize=15, weight="bold", color="white")
        fig.text(x0 + 0.07, y0 + h - 0.03, place, fontsize=9.5, weight="bold")
        fig.text(x0 + 0.07, y0 + h - 0.06, kind, fontsize=9, color="#444")
        # 小さな地図
        mx = fig.add_axes([x0 + 0.12, y0 + h - 0.17, 0.10, 0.10])
        draw_board(mx)
        l = by[lid]
        mx.add_patch(Circle((l["x"], l["y"]), 9, fc="#ff3b30", ec="white", lw=0.8, zorder=5))
        # 部品と線
        px = fig.add_axes([x0 + 0.01, y0 + 0.015, w - 0.02, h - 0.19])
        draw_led(px, kind, pins)
    pdf.savefig(fig); fig.savefig(HERE / fname, dpi=130); plt.close(fig)

# ------------------------------------------------------------
def page_table(pdf):
    """一覧表と回路の考え方"""
    fig = plt.figure(figsize=(11.69, 8.27))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.text(0.03, 0.955, "LED の配線　10. 一覧表と回路のしくみ", fontsize=17, weight="bold", transform=ax.transAxes)
    # 左：しくみ
    ax.text(0.03, 0.89, "しくみ（チャーリープレクシング）", fontsize=11, weight="bold", transform=ax.transAxes)
    expl = ["・ESP32 の 5 本のピンに 47Ω を 1 本ずつ付け、その先が線1〜線5。",
            "・LED は「＋の足の線」が HIGH、「−の足の線」が LOW のときだけ光る。",
            "・ESP32 が 1 秒に何百回も 1 個ずつ切り替えて光らせるので、",
            "　全部同時に光っているように見える。",
            "・5 本の線の組み合わせで 18 個ぶんの光を作れる（同じ組み合わせは",
            "　1 回しか使っていないので、どの LED も別々に光らせられる）。",
            "・LED も抵抗も、3.3V や GND にはつながない。"]
    for i, t in enumerate(expl):
        ax.text(0.03, 0.85 - i * 0.033, t, fontsize=9, transform=ax.transAxes)
    # 回路の小さな図
    for k in range(5):
        y = 0.52 - k * 0.06
        ax.text(0.03, y, f"GPIO{PINS[k]}", va="center", fontsize=9, transform=ax.transAxes)
        ax.plot([0.08, 0.12], [y, y], color="#333", lw=1.2, transform=ax.transAxes)
        ax.add_patch(Rectangle((0.12, y - 0.012), 0.05, 0.024, fc="#f3e2c3", ec="#333", transform=ax.transAxes))
        ax.text(0.145, y, "47Ω", ha="center", va="center", fontsize=7.5, transform=ax.transAxes)
        ax.plot([0.17, 0.24], [y, y], color=WCOL[k] if k < 4 else "#bbb", lw=4, transform=ax.transAxes)
        chip(ax, 0.27, y, k, w=0.05, h=0.035, size=9)
        ax.text(0.30, y, f"{WNAME[k]} → 全部の LED のそばへ", va="center", fontsize=8.5, transform=ax.transAxes)
    ax.text(0.03, 0.17, "ESP32-C3 SuperMini は USB-C から給電（レーダーとは別）。", fontsize=8.5, color="#555", transform=ax.transAxes)
    # 右：一覧表
    x0, y0 = 0.52, 0.89
    for t, dx in (("番号", 0.0), ("場所", 0.04), ("部品", 0.12), ("足・ピン → 線", 0.22)):
        ax.text(x0 + dx, y0, t, fontsize=9, weight="bold", transform=ax.transAxes)
    y = y0 - 0.04
    for n, lid, place, kind, pins in PARTS:
        hgt = 0.045 if len(pins) <= 2 else 0.045 + (len(pins) - 2) * 0.0
        ax.add_patch(Rectangle((x0 - 0.01, y - 0.02), 0.47, 0.04, fc="#f4f6f8" if n % 2 else "white", ec="none", transform=ax.transAxes))
        ax.text(x0 + 0.012, y, str(n), ha="center", va="center", fontsize=9, weight="bold", transform=ax.transAxes)
        ax.text(x0 + 0.04, y, place.replace(" 滑走路", "").replace("の端", "").replace("タイトル板の", ""), va="center", fontsize=8.5, transform=ax.transAxes)
        ax.text(x0 + 0.12, y, kind.replace(" モジュール", ""), va="center", fontsize=8.5, transform=ax.transAxes)
        xx = x0 + 0.235
        for label, k in pins:
            lab = label.replace(" 長い足", "").replace(" 短い足", "").replace("のピン", "").replace(" ピン", "")
            ax.text(xx, y, lab, va="center", ha="right", fontsize=8.5, transform=ax.transAxes)
            chip(ax, xx + 0.025, y, k, w=0.038, h=0.028, size=7.5)
            xx += 0.06
        y -= 0.045
    pdf.savefig(fig); fig.savefig(HERE / "10_一覧表.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------
def page_protoboard(pdf):
    fig = plt.figure(figsize=(11.69, 8.27))
    ax = fig.add_axes([0.06, 0.08, 0.6, 0.8]); ax.set_aspect("equal"); ax.axis("off")
    fig.text(0.04, 0.95, "LED の配線　2. 抵抗基板（運用ボードのケースの中）", fontsize=17, weight="bold")
    fig.text(0.04, 0.915, "4×6cm のユニバーサル基板から 8 列 × 6 行を切り出す（約 20 × 15 mm）。部品面から見た図。", fontsize=9, color="#444")
    cols, rows = 8, 6
    ax.add_patch(Rectangle((-0.6, -0.6), cols + 0.2, rows + 0.2, fc="#3f8f4a", ec="#2b6634"))
    for i in range(cols):
        for j in range(rows):
            ax.add_patch(Circle((i, j), 0.18, fc="#d9b25a", ec="#8a6a20", lw=0.6))
    for i in range(cols):
        ax.text(i, rows - 0.1, "ABCDEFGH"[i], ha="center", fontsize=9, color="#333")
    for j in range(rows):
        ax.text(-1.0, j, str(rows - j), ha="center", va="center", fontsize=9, color="#333")
    # 抵抗：行 1〜5（上から）、列 B〜F（足は B と F）
    for k in range(5):
        y = rows - 1 - k
        ax.plot([1, 5], [y, y], color="#999", lw=2.5)
        ax.add_patch(FancyBboxPatch((2.1, y - 0.22), 1.8, 0.44, boxstyle="round,pad=0.05", fc="#f3e2c3", ec="#7a5a2a"))
        ax.text(3, y, "47Ω", ha="center", va="center", fontsize=8)
        # ESP32 側の線（A 列）
        ax.plot([-2.8, 0], [y, y], color="#1c2d4a", lw=2)
        ax.plot([0, 1], [y, y], color="#c0c0c0", lw=3)
        ax.text(-2.9, y, f"GPIO{PINS[k]}", ha="right", va="center", fontsize=9)
        # 線の側（G・H 列）
        ax.plot([5, 6], [y, y], color="#c0c0c0", lw=3)
        ax.plot([6, 8.6], [y, y], color=WCOL[k], lw=3.5)
        ax.text(8.75, y, f"{WN(k)} → 底板の裏へ", va="center", fontsize=9)
    ax.set_xlim(-5.5, 13.5); ax.set_ylim(-1.8, rows + 0.8)
    steps = [
        "1. 抵抗 5 本を B 列と F 列に差し、裏で足を曲げてはんだ付けする（足の余りは切る）。",
        "2. A 列と B 列、F 列と G 列を裏ではんだでつなぐ（灰色の線）。",
        "3. A 列に ESP32-C3 の GPIO3〜7 からの線、G 列に底板の裏へ行く 5 本の線をはんだ付けする。",
        "4. 線の色は 線1 茶・線2 紫・線3 青・線4 灰・線5 白。手持ちの色が違うときは、両端に番号のテープを貼れば大丈夫（LED と同じ赤・緑・黄の線は使わない方が間違えにくい）。",
        "5. 基板はケース（case.stl）の左の柱 4 本の上にホットボンドで貼る。ESP32-C3 は右のレールにのせ、USB-C を右の穴に合わせる。",
    ]
    for i, t in enumerate(steps):
        fig.text(0.04, 0.2 - i * 0.033, t, fontsize=9)
    pdf.savefig(fig); fig.savefig(HERE / "2_抵抗基板.png", dpi=130); plt.close(fig)

# ------------------------------------------------------------
def page_underside(pdf):
    """実寸。裏から見るので左右を反転"""
    BW, BH = BOARD["BW"], BOARD["BH"]
    CS = BOARD["case"]
    W_IN, H_IN = 16.54, 11.69                       # A3 横
    fig = plt.figure(figsize=(W_IN, H_IN))
    mx, my = (W_IN * 25.4 - BW) / 2, (H_IN * 25.4 - BH) / 2
    ax = fig.add_axes([mx / (W_IN * 25.4), my / (H_IN * 25.4), BW / (W_IN * 25.4), BH / (H_IN * 25.4)])
    ax.set_xlim(BW, 0); ax.set_ylim(0, BH); ax.axis("off")    # 左右反転
    from matplotlib.patches import Polygon as MPoly
    for p in BOARD["outline"]:
        ax.add_patch(MPoly(p["o"], closed=True, fc="#fbf8f0", ec="#555", lw=1))
    # レーダーの穴とボタンの穴（L1・L2 を貫通）
    x0, y0, x1, y1 = CS["radar_hole"]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="white", ec="#555", lw=0.8, hatch="//"))
    for bx, by in BOARD["radar"]["buttons"]:
        ax.add_patch(Circle((bx, by), CS["btn_hole"] / 2, fc="white", ec="#555", lw=0.8))
        ax.add_patch(Rectangle((bx - 7.5, by - 6.5), 15, 13, fc="none", ec="#3b4a57", lw=0.8, ls="--"))
    # 脚
    for fx, fy in CS["feet"]:
        ax.add_patch(Circle((fx, fy), CS["foot_d"] / 2, fc="#e6e9ec", ec="#3b4a57", lw=0.8))
        ax.text(fx, fy, "脚", ha="center", va="center", fontsize=7, color="#3b4a57")
    # 島の輪郭（参考）
    for L in BOARD["layers"]:
        if L["name"].startswith("L3"):
            for p in L["polys"]:
                xs, ys = zip(*p["o"]); ax.plot(xs, ys, color="#c9b98d", lw=0.8)
    # トレー
    hx, hy = BOARD["hub"]
    tx0, ty0, tx1, ty1 = CS["tray"]
    ax.add_patch(Rectangle((tx0, ty0), tx1 - tx0, ty1 - ty0, fc="none", ec="#3b4a57", lw=1.4))
    ax.text((tx0 + tx1) / 2, ty1 + 3, "トレー（ここに貼る）", ha="center", fontsize=9, color="#3b4a57")
    ax.text((tx0 + tx1) / 2, (y0 + y1) / 2, "レーダーの穴\n（裏の点線＝ボタンの基板）", ha="center", va="center", fontsize=7.5, color="#3b4a57",
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none"))
    lx0, ly0, lx1, ly1 = CS["led_case"]
    ax.add_patch(Rectangle((lx0, ly0), lx1 - lx0, ly1 - ly0, fc="#dfe6ec", ec="#3b4a57", lw=1.2, zorder=9))
    ax.text(hx, hy + 6, "運用ボードのケース", ha="center", fontsize=9, color="#3b4a57", zorder=10)
    ax.text(hx, hy - 3, "5 本の線は左の切り欠きから中へ", ha="center", fontsize=7, color="#3b4a57", zorder=10)
    ax.text(hx, hy - 12, "USB-C は右の側面", ha="center", fontsize=7, color="#3b4a57", zorder=10)
    # 線の通り道（5 色の帯）と番号
    draw_chains(ax, lw=1.6)
    by_id = {l["id"]: l for l in BOARD["leds"]}
    for n, lid, place, kind, pins in PARTS:
        l = by_id[lid]
        ax.add_patch(Circle((l["x"], l["y"]), 2.6, fc="white", ec="#222", lw=1, zorder=6))
        bx, by_ = badge_pos(lid, 7.0)
        ax.plot([l["x"], bx], [l["y"], by_], color="#1c2d4a", lw=0.8, zorder=5)
        ax.text(bx, by_, str(n), ha="center", va="center", fontsize=9, weight="bold", color="white", zorder=8,
                bbox=dict(boxstyle="circle,pad=0.25", fc="#1c2d4a", ec="white", lw=0.8))
    fig.text(0.02, 0.965, "LED の配線　11. 底板の裏の型紙（実寸 1:1・裏から見た向き）", fontsize=16, weight="bold")
    fig.text(0.02, 0.94, "A3 横に「実際のサイズ（100%）」で印刷し、底板の裏に当てて使う。裏から見ているので左右が逆。色の線は 線1〜線5 の通り道"
             "（つなぐ順番は 3〜7 ページ）。", fontsize=8.5, color="#333", wrap=True)
    # 目盛り（印刷の確認）
    ax.plot([BW - 10, BW - 60], [6, 6], color="k", lw=2)
    ax.text(BW - 35, 9, "50 mm（印刷後に定規で確認）", ha="center", fontsize=7)
    pdf.savefig(fig); fig.savefig(HERE / "11_底板の裏の型紙.png", dpi=110); plt.close(fig)

# ------------------------------------------------------------
def page_tray(pdf):
    CS = BOARD["case"]
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.04, 0.95, "レーダーとの合体：トレー（レーダー）とケース（運用ボード）は別々に動く", fontsize=17, weight="bold")
    fig.text(0.04, 0.915, "レーダーのケースは裏ぶたを付けずに海の板へ貼る。ふたにのっていた ESP32・ブザー・電源分配基板はトレーへ移し、液晶とつまみの線は板の穴を通して下へ。",
             fontsize=9, color="#444")
    # 左：トレーの中（上から見た図。実物と同じ向き）
    ax = fig.add_axes([0.04, 0.06, 0.32, 0.82]); ax.set_aspect("equal"); ax.axis("off")
    tx0, ty0, tx1, ty1 = CS["tray"]
    ax.add_patch(Rectangle((tx0, ty0), tx1 - tx0, ty1 - ty0, fc="#eef1f4", ec="#3b4a57", lw=1.5))
    x0, y0, x1, y1 = CS["radar_hole"]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc="none", ec="#999", lw=0.8, ls="--"))
    ax.text((x0 + x1) / 2, y1 - 3, "上はレーダーの穴", ha="center", fontsize=7, color="#888")
    col = {"ESP32-C3（レーダー）": "#1c2d4a", "ブザー": "#222", "電源分配": "#3f8f4a"}
    for name, (a, b, c, d) in CS["parts"].items():
        ax.add_patch(Rectangle((a, b), c - a, d - b, fc=col[name], ec="none", alpha=0.85))
        ax.text((a + c) / 2, (b + d) / 2, name.replace("（", "\n（"), ha="center", va="center", fontsize=6.5, color="white")
    for bx, by in BOARD["radar"]["buttons"]:
        ax.add_patch(Circle((bx, by), CS["btn_hole"] / 2, fc="none", ec="#3b4a57", lw=1))
    ax.text(BOARD["radar"]["buttons"][0][0], BOARD["radar"]["buttons"][0][1], "表示", ha="center", va="center", fontsize=7)
    ax.text(BOARD["radar"]["buttons"][1][0], BOARD["radar"]["buttons"][1][1], "明るさ", ha="center", va="center", fontsize=7)
    for (a, b, c, d) in (CS["parts"]["ESP32-C3（レーダー）"],):
        ax.annotate("USB-C", xy=(tx1, (b + d) / 2), xytext=(tx1 + 6, (b + d) / 2), fontsize=7, va="center",
                    arrowprops=dict(arrowstyle="-", color="#555"))
    ax.set_xlim(tx0 - 32, tx1 + 18); ax.set_ylim(ty0 - 6, ty1 + 6)
    ax.text((tx0 + tx1) / 2, ty0 - 4, "トレーを上から見た図（板の裏に貼る前）", ha="center", fontsize=7.5, color="#555")
    # 右：つなぎ方
    t = fig.add_axes([0.42, 0.06, 0.55, 0.82]); t.axis("off")
    rows = [
        ("電源", "レーダー：トレーの右の USB-C", "2 つの ESP32 は別々の USB-C で給電（線ではつながない）"),
        ("", "運用ボード：ケースの右の USB-C", "2 口の USB 充電器か、USB ハブにまとめると 1 か所で済む"),
        ("ボタン", "表示（VIEW）：GPIO9 と GND（今までと同じピン）", "ボタンの基板を底板の裏に貼り、線を延ばす"),
        ("", "明るさ（LIGHT）：GPIO8 と GND", "キャップが板から約 6mm 出る"),
        ("ブザー", "KY-012：S → GPIO0（ほかの線も今までと同じ）", "上がレーダーの穴なので音はケースから出る"),
        ("液晶・つまみ", "今までと同じピン。線を板の穴に通して下の ESP32 へ", "足りなければ 10cm ほど延ばす"),
        ("運用ボード", "ESP32-C3 と抵抗基板は第3版のケース（case.stl）へ", "GPIO3〜7 → 47Ω → 線1〜線5（LED配線ガイド）"),
    ]
    y = 0.97
    t.text(0.0, y, "つなぎ方", fontsize=12, weight="bold", transform=t.transAxes); y -= 0.06
    for a, b, c in rows:
        t.text(0.0, y, a, fontsize=9, weight="bold", transform=t.transAxes)
        t.text(0.16, y, b, fontsize=9, transform=t.transAxes)
        if c:
            t.text(0.16, y - 0.03, c, fontsize=7.8, color="#666", transform=t.transAxes)
        y -= 0.075
    y -= 0.02
    t.text(0.0, y, "注意", fontsize=12, weight="bold", transform=t.transAxes); y -= 0.05
    for s_ in ["・2 つの ESP32 は完全に別々（電源も線もつながない）。書き込みはそれぞれの USB-C から。",
               "・2 つの ESP32 は別々に Wi-Fi につながり、それぞれ adsb.fi からデータを取る（レーダー 5 秒・運用ボード 5 秒ごと）。",
               "・レーダーのケースの横のボタン穴は、栓（button_plug_x2.stl）を内側から押し込んでふさぐ。",
               "・組み立て順：ボタン基板とトレーの中を配線 → 動作確認 → トレーを底板の裏に貼る → レーダーを海の板に貼る。"]:
        t.text(0.0, y, s_, fontsize=8.5, transform=t.transAxes, wrap=True); y -= 0.045
    pdf.savefig(fig); fig.savefig(HERE / "12_レーダーとの合体.png", dpi=130); plt.close(fig)


# ------------------------------------------------------------
def page_bicolor(pdf):
    """2色 LED モジュール（No.9・No.13）のくわしいつなぎ方"""
    fig = plt.figure(figsize=(11.69, 8.27))
    fig.text(0.03, 0.955, "LED の配線　13. 2色 LED モジュール（No.9・No.13）のつなぎ方", fontsize=17, weight="bold")
    fig.text(0.03, 0.92, "2色 LED は 1 個の中に緑と赤の LED が入っていて、ピンが 3 本ある。「−」は緑と赤の共通。残りの 2 本が緑用と赤用。",
             fontsize=9.5, color="#333")
    # 左：ピンの見分け方
    ax = fig.add_axes([0.03, 0.08, 0.42, 0.80]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.text(0.0, 0.97, "① まずピンを見分ける（つなぐ前に 1 回だけ）", fontsize=12, weight="bold")
    ax.add_patch(Rectangle((0.12, 0.55), 0.36, 0.34, fc="#2e6b3a", ec="#1f4a28", lw=1.5))
    ax.add_patch(Circle((0.30, 0.76), 0.07, fc="#ffd27f", ec="#555"))
    ax.text(0.30, 0.64, "LED", ha="center", fontsize=8, color="white")
    pins = [("−", 0.18), ("真ん中", 0.30), ("S", 0.42)]
    for lab, x in pins:
        ax.plot([x, x], [0.55, 0.42], color="#bbb", lw=4)
        ax.text(x, 0.565, lab, ha="center", fontsize=9, color="white", weight="bold")
    ax.text(0.18, 0.37, "−", ha="center", fontsize=13, weight="bold")
    ax.text(0.30, 0.37, "?", ha="center", fontsize=13, weight="bold", color="#c0392b")
    ax.text(0.42, 0.37, "?", ha="center", fontsize=13, weight="bold", color="#c0392b")
    ax.text(0.55, 0.80, "基板に「−」と「S」の文字がある。\n真ん中のピンは文字がないことが多い。\n\n緑と赤がどちらのピンかは\n品によって違うので、光らせて確かめる。",
            fontsize=9.5, va="top")
    tests = ["確かめ方（運用ボードの ESP32 を USB-C につないだ状態で）",
             "1. ジャンパワイヤで、モジュールの「−」を ESP32 の GND につなぐ",
             "2. 220Ω の抵抗の片方を ESP32 の 3V3 につなぐ",
             "3. 抵抗のもう片方を「真ん中」のピンに当てる → 光った色を見る",
             "4. 同じように「S」のピンに当てる → もう一方の色で光る",
             "5. 緑で光ったピンに「緑」、赤で光ったピンに「赤」のテープを貼る",
             "   （2 個とも同じように確かめる）"]
    for i, t in enumerate(tests):
        ax.text(0.0, 0.28 - i * 0.045, t, fontsize=9.5 if i else 10, weight="bold" if i == 0 else "normal")
    # 右：つなぐ線
    bx = fig.add_axes([0.50, 0.08, 0.48, 0.80]); bx.axis("off"); bx.set_xlim(0, 1); bx.set_ylim(0, 1)
    bx.text(0.0, 0.97, "② ピンに線をはんだ付けする", fontsize=12, weight="bold")
    info = {9: ("C 滑走路 34R の端", {"−": 3, "緑": 0, "赤": 1}), 13: ("D 滑走路 23 の端", {"−": 2, "緑": 0, "赤": 1})}
    order = {}
    for k in range(5):
        start, st = chain(k)
        for i, s_ in enumerate(st, 1):
            if s_["n"] in info:
                key = "−" if "−" in s_["label"] else ("緑" if "緑" in s_["label"] else "赤")
                order[(s_["n"], key)] = (i, len(st))
    y0 = 0.90
    for n, (place, m) in info.items():
        bx.add_patch(FancyBboxPatch((0.0, y0 - 0.31), 0.98, 0.33, boxstyle="round,pad=0,rounding_size=0.02", fc="white", ec="#9aa5b1"))
        bx.text(0.06, y0 - 0.03, str(n), ha="center", va="center", fontsize=14, weight="bold", color="white",
                bbox=dict(boxstyle="circle,pad=0.3", fc="#1c2d4a"))
        bx.text(0.13, y0 - 0.03, f"No.{n}　{place}", va="center", fontsize=11, weight="bold")
        yy = y0 - 0.11
        for key in ("−", "緑", "赤"):
            k = m[key]
            i, tot = order[(n, key)]
            pin = {"−": "「−」のピン", "緑": "緑のテープのピン", "赤": "赤のテープのピン"}[key]
            bx.text(0.04, yy, pin, va="center", fontsize=10.5, color={"−": "#2c3e50", "緑": "#1e8e3e", "赤": "#c0392b"}[key], weight="bold")
            bx.annotate("", xy=(0.43, yy), xytext=(0.36, yy), arrowprops=dict(arrowstyle="->", color="#555"))
            chip(bx, 0.50, yy, k, w=0.1, h=0.05, size=11)
            bx.text(0.56, yy, f"{WNAME[k]}", va="center", fontsize=10.5)
            last = "（最後の足：線は 1 本）" if i == tot else "（来た線と次の線の 2 本）"
            bx.text(0.63, yy, f"線{k + 1} の {i} 番目 {last}", va="center", fontsize=8.5, color="#444")
            yy -= 0.07
        y0 -= 0.36
    notes = ["・モジュールの基板は底板の裏に貼り、LED を下から L1・L2・L3 の穴に通す。",
             "・ピンに直接線をはんだ付けする（ジャンパワイヤのメスを差してもよい）。",
             "・3 本のピンどうしが触れないよう、はんだの後に熱収縮チューブかテープで包む。",
             "・電源を入れたときの確認では、No.9 と No.13 は「緑 → 赤」の順に 2 回光る。",
             "  逆の色で光ったら、緑と赤の線を入れ替える。"]
    for i, t in enumerate(notes):
        bx.text(0.0, 0.0 + (len(notes) - 1 - i) * 0.038, t, fontsize=8.8)
    pdf.savefig(fig); fig.savefig(HERE / "13_2色LEDのつなぎ方.png", dpi=130); plt.close(fig)

if __name__ == "__main__":
    for f in HERE.glob("*.png"):
        f.unlink()
    with PdfPages(HERE / "配線図.pdf") as pdf:
        page_overview(pdf)                     # 1
        page_protoboard(pdf)                   # 2
        for k in range(5):                     # 3〜7
            page_wire(pdf, k)
        page_cards(pdf, PARTS[:8], "LED の配線　8. LED ごとのカード（1〜8）", "8_LEDカード1.png")
        page_cards(pdf, PARTS[8:], "LED の配線　9. LED ごとのカード（9〜14）", "9_LEDカード2.png")
        page_table(pdf)                        # 10
        page_underside(pdf)                    # 11
        page_tray(pdf)                         # 12
        page_bicolor(pdf)                      # 13
    print("saved")
