"""
ADS-B レーダーの回路図（schemdraw）
  python3 schematic.py  →  schematic.png / schematic.svg / schematic.pdf

ピン番号は firmware/adsb_radar/config.h と一致させること。
"""
from pathlib import Path
import schemdraw
import schemdraw.elements as elm

schemdraw.use("matplotlib")
schemdraw.config(font="Noto Sans CJK JP", fontsize=11, lw=1.3)

OUT = Path(__file__).resolve().parent

# 部品ごとの色（ネット名の旗の色）
C_LCD = "#2f5fa8"
C_ENC = "#1d7a45"
C_BTN = "#b8452f"
C_BUZ = "#a07400"
C_PWR = "#444444"

# ESP32-C3 SuperMini のピン（部品面を上、USB-C を上にしたときの並び）
LEFT = [("5V", None), ("GND", None), ("3V3", None), ("GPIO4", "液晶 SCL"), ("GPIO3", "液晶 RST"),
        ("GPIO2", None), ("GPIO1", "エンコーダ DT"), ("GPIO0", "ブザー S")]
RIGHT = [("GPIO5", "液晶 DC"), ("GPIO6", "液晶 SDA"), ("GPIO7", "液晶 CS"), ("GPIO8", "LIGHTボタン"),
         ("GPIO9", "VIEWボタン"), ("GPIO10", "エンコーダ SW"), ("GPIO20", "エンコーダ CLK"), ("GPIO21", "液晶 BL")]

def net_color(net):
    if net.startswith("液晶"): return C_LCD
    if net.startswith("エンコーダ"): return C_ENC
    if "ボタン" in net: return C_BTN
    if net.startswith("ブザー"): return C_BUZ
    return C_PWR

def tag(d, at, net, direction):
    """ピンから線を出して、ネット名の旗を付ける"""
    col = net_color(net)
    line = elm.Line().at(at).length(1.2).color(col)
    getattr(line, direction)()
    d += line
    t = elm.Tag(width=3.4).at(line.end).color(col).label(net, fontsize=10, color=col)
    getattr(t, direction)()
    d += t

with schemdraw.Drawing(file=None, show=False) as d:
    d.config(unit=2.5)

    # ---------------- タイトル ----------------
    d += elm.Label().at((-2.0, 2.6)).label("ADS-B レーダー 回路図", fontsize=17, halign="left")
    d += elm.Label().at((-2.0, 1.7)).label("ESP32-C3 SuperMini ＋ 2.0インチ液晶（ST7789）。電源は USB-C から（5V → 基板上で 3.3V に変換）",
                                         fontsize=10, halign="left", color="#555")

    # ---------------- ESP32-C3 ----------------
    pins = ([elm.IcPin(name=n, side="left", anchorname=f"L{i}") for i, (n, _) in enumerate(reversed(LEFT))] +
            [elm.IcPin(name=n, side="right", anchorname=f"R{i}") for i, (n, _) in enumerate(reversed(RIGHT))])
    esp = elm.Ic(size=(6.0, 9.0), pins=pins, pinspacing=1.0, edgepadH=0.5, leadlen=0.7, lw=2).right().at((4, -9))
    esp.label("ESP32-C3\nSuperMini", fontsize=13, loc="center")
    d += esp
    d += elm.Label().at((esp.absanchors["L7"][0] + 3.75, esp.absanchors["L7"][1] + 1.35)).label("▲ USB-C（右側面の穴へ）", fontsize=9, color="#555")

    L = {n: esp.absanchors[f"L{len(LEFT) - 1 - i}"] for i, (n, _) in enumerate(LEFT)}
    R = {n: esp.absanchors[f"R{len(RIGHT) - 1 - i}"] for i, (n, _) in enumerate(RIGHT)}

    # 電源ピン
    d += elm.Line().at(L["5V"]).left().length(0.8).color("#999")
    d += elm.Label().label("未接続", fontsize=9, color="#999", halign="right").at((L["5V"][0] - 0.95, L["5V"][1]))
    g = elm.Line().at(L["GND"]).left().length(1.6)
    d += g
    d += elm.Ground().at(g.end)
    v = elm.Line().at(L["3V3"]).left().length(2.8)
    d += v
    d += elm.Vdd().at(v.end).label("3.3V", fontsize=10)
    d += elm.Line().at(L["GPIO2"]).left().length(0.8).color("#999")
    d += elm.Label().label("未接続（起動設定用のピン）", fontsize=9, color="#999", halign="right").at((L["GPIO2"][0] - 0.95, L["GPIO2"][1]))

    for name, net in LEFT:
        if net:
            tag(d, L[name], net, "left")
    for name, net in RIGHT:
        if net:
            tag(d, R[name], net, "right")

    # ピン横の注記
    d += elm.Label().at((R["GPIO9"][0] + 4.9, R["GPIO9"][1])).label("基板の BOOT ボタンと共通", fontsize=8, color="#777", halign="left")
    d += elm.Label().at((R["GPIO8"][0] + 4.9, R["GPIO8"][1])).label("基板の青LEDと共通（押すと点灯）", fontsize=8, color="#777", halign="left")
    d += elm.Label().at((R["GPIO21"][0] + 4.9, R["GPIO21"][1])).label("起動時に一瞬ちらつくのは正常", fontsize=8, color="#777", halign="left")

    # ---------------- 液晶 ----------------
    X1 = 29.0
    lcd_pins = ["GND", "VCC", "SCL", "SDA", "RST", "DC", "CS", "BL"]
    lcd = elm.Ic(size=(4.2, 8.6), pins=[elm.IcPin(name=n, side="left", anchorname=f"p{i}") for i, n in enumerate(reversed(lcd_pins))],
                 pinspacing=1.0, edgepadH=0.4, leadlen=0.7, lw=1.8).right().at((X1, -8.6)).color(C_LCD)
    lcd.label("2.0インチ液晶\nGMT020-02\n（ST7789）", fontsize=11, loc="center")
    d += lcd
    LP = {n: lcd.absanchors[f"p{len(lcd_pins) - 1 - i}"] for i, n in enumerate(lcd_pins)}
    g = elm.Line().at(LP["GND"]).left().length(1.4)
    d += g
    d += elm.Ground().at(g.end)
    v = elm.Line().at(LP["VCC"]).left().length(2.6)
    d += v
    d += elm.Vdd().at(v.end).label("3.3V", fontsize=10)
    for n in ["SCL", "SDA", "RST", "DC", "CS", "BL"]:
        tag(d, LP[n], f"液晶 {n}", "left")
    d += elm.Label().at((X1 + 0.6, -9.6)).label("VCC は必ず 3.3V（5V 不可）", fontsize=9, color=C_LCD, halign="left")

    # ---------------- 下段：エンコーダ・ボタン・ブザー ----------------
    Y2 = -12.5
    # エンコーダ KY-040
    enc_pins = ["CLK", "DT", "SW", "+", "GND"]
    enc = elm.Ic(size=(4.6, 5.0), pins=[elm.IcPin(name=n, side="left", anchorname=f"p{i}") for i, n in enumerate(reversed(enc_pins))],
                 pinspacing=1.0, edgepadH=0.4, leadlen=0.7, lw=1.8).right().at((6.0, Y2 - 5.0)).color(C_ENC)
    enc.label("ロータリー\nエンコーダ\nKY-040", fontsize=11, loc="center")
    d += enc
    EP = {n: enc.absanchors[f"p{len(enc_pins) - 1 - i}"] for i, n in enumerate(enc_pins)}
    for n in ["CLK", "DT", "SW"]:
        tag(d, EP[n], f"エンコーダ {n}", "left")
    v = elm.Line().at(EP["+"]).left().length(5.6)
    d += v
    d += elm.Vdd().at(v.end).label("3.3V", fontsize=10)
    g = elm.Line().at(EP["GND"]).left().length(1.4)
    d += g
    d += elm.Ground().at(g.end)
    d += elm.Label().at((1.0, Y2 - 6.6)).label("CLK・DT は基板上の 10kΩ で 3.3V に引き上げ済み\n「+」は 3.3V に（5V にしない）",
                                          fontsize=9, color=C_ENC, halign="left")

    # ボタン（内部プルアップ使用。押すと GND に落ちる）
    BX = 17.0
    for i, (net, label) in enumerate([("VIEWボタン", "VIEW（左側面）"), ("LIGHTボタン", "LIGHT（右側面）")]):
        y = Y2 - 1.0 - i * 3.0
        tag(d, (BX, y), net, "left")
        ln = elm.Line().right().at((BX, y)).length(0.6).color(C_BTN)
        d += ln
        b = elm.Button().right().at(ln.end).label(label, loc="top", fontsize=10, ofst=0.25)
        d += b
        ln2 = elm.Line().right().at(b.end).length(0.8)
        d += ln2
        d += elm.Ground().at(ln2.end)
    d += elm.Label().at((12.4, Y2 - 6.6)).label("タクトスイッチ 12×12。4本足のうち対角の2本を使う\nプルアップ抵抗は不要（ESP32 の内蔵プルアップを使用）",
                                          fontsize=9, color=C_BTN, halign="left")

    # アクティブブザー KY-012
    buz_pins = ["S", "+", "−"]
    buz = elm.Ic(size=(4.2, 3.0), pins=[elm.IcPin(name=n, side="left", anchorname=f"p{i}") for i, n in enumerate(reversed(buz_pins))],
                 pinspacing=1.0, edgepadH=0.4, leadlen=0.7, lw=1.8).right().at((X1 + 1.0, Y2 - 3.0)).color(C_BUZ)
    buz.label("アクティブ\nブザー", fontsize=11, loc="center")
    d += buz
    BP = {n: buz.absanchors[f"p{len(buz_pins) - 1 - i}"] for i, n in enumerate(buz_pins)}
    tag(d, BP["S"], "ブザー S", "left")
    v = elm.Line().at(BP["+"]).left().length(5.6)
    d += v
    d += elm.Vdd().at(v.end).label("3.3V", fontsize=10)
    g = elm.Line().at(BP["−"]).left().length(1.4)
    d += g
    d += elm.Ground().at(g.end)
    d += elm.Label().at((X1 - 4.0, Y2 - 6.6)).label("基板によっては「+」が未使用。つないでも害はない", fontsize=9, color=C_BUZ, halign="left")

    # ---------------- 凡例 ----------------
    d += elm.Label().at((-2.0, -21.2)).label(
        "見方：同じ名前の旗どうしを1本の線でつなぎます。横線3本の記号は GND、「3.3V」と書いた記号は 3.3V で、それぞれ全部が1つにつながります。",
        fontsize=10, halign="left", color="#333")
    d += elm.Label().at((-2.0, -22.2)).label(
        "3.3V と GND は ESP32-C3 の 3V3・GND ピンから電源分配基板を通して、液晶・エンコーダ・ブザー・ボタンへ分けます（universal_board.pdf を参照）。",
        fontsize=10, halign="left", color="#333")

    d.save(str(OUT / "schematic.svg"))
    d.save(str(OUT / "schematic.png"), dpi=170)
    d.save(str(OUT / "schematic.pdf"))
print("saved")
