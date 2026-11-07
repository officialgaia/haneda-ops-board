"""3D ビューア用：3D プリント部品のメッシュを board.json に追記する"""
import json, base64
from pathlib import Path
import numpy as np
import sys
import case3d as C
import board as B
sys.path.insert(0, "/home/claude/adsb-radar/case")
import case as R          # ADS-B レーダーのケース

ROOT = Path(__file__).resolve().parent.parent
def mesh(w, tol):
    vs, fs = w.val().tessellate(tol, 0.3)
    v = np.array([(p.x, p.y, p.z) for p in vs]); f = np.array(fs, dtype=np.int64)
    q = np.round(v * 20).astype(np.int32)
    return {"v": base64.b64encode(q.astype(np.int32).tobytes()).decode(), "i": base64.b64encode(f.astype(np.uint32).tobytes()).decode()}
d = json.loads((ROOT / "build" / "board.json").read_text())
d["printed"] = [
    dict(name="トレー", group="case", color="#3b4a57", **mesh(C.make_case(), 0.08)),
    dict(name="運用ボードのケース", group="case", color="#3b4a57", **mesh(C.make_led_case(), 0.08)),
    # レーダーの本体：前面（液晶）を上にして、海の板の上（z = 2T）に置く
    dict(name="ADS-B レーダー", group="radar", color="#2b3640",
         **mesh(R.make_shell().rotate((0, 0, 0), (0, 1, 0), 180)
                .translate((B.RADAR_X0 + R.W / 2, B.RADAR_Y0 + R.H / 2, 2 * B.T + R.D)), 0.08)),
    dict(name="管制塔", group="tower", color="#e8ecef", **mesh(C.make_tower(), 0.03)),
] + [dict(name="脚", group="feet", color="#3b4a57", **mesh(C.make_foot(x, y), 0.1)) for x, y in C.FEET]
d["case"] = {"tray": [C.X0 - C.WALL, C.Y0 - C.WALL, C.X1 + C.WALL, C.Y1 + C.WALL], "feet": C.FEET, "foot_d": C.FOOT_D,
             "parts": {"ESP32-C3（レーダー）": [C.C3_X0, C.ESP["レーダー"] - C.C3_W / 2, C.C3_X1, C.ESP["レーダー"] + C.C3_W / 2],
                       "ブザー": [C.BUZ[0] - C.BUZ_PCB[0] / 2, C.BUZ[1] - C.BUZ_PCB[1] / 2, C.BUZ[0] + C.BUZ_PCB[0] / 2, C.BUZ[1] + C.BUZ_PCB[1] / 2],
                       "電源分配": [C.DIST[0], C.DIST[1] - C.DIST[3] / 2, C.DIST[0] + C.DIST[2], C.DIST[1] + C.DIST[3] / 2],
                       },
             "led_case": list(C.LED_CASE_RECT),
             "led_case_notch": [C.L_X0 - C.L_WALL, C.L_CY],
             "radar_hole": list(B.RADAR_HOLE.bounds), "btn_hole": B.BTN_HOLE,
             "zb": C.ZB, "esp": [[C.C3_X0, ey - C.C3_W / 2, C.C3_Z0, C.C3_X1, ey + C.C3_W / 2] for ey in C.ESP.values()]
             + [[C.L_C3_X0, C.L_CY - C.L_C3_W / 2, C.L_C3_Z0, C.L_C3_X1, C.L_CY + C.L_C3_W / 2]]}
# 液晶の表示部（ビューアで光らせる）：ケースの窓の位置
lx = B.RADAR_X0 + R.LCD_X + R.LCD_PCB_W / 2
ly = B.RADAR_Y0 + R.H - (R.LCD_Y + R.LCD_AA_TOP + R.LCD_AA_H / 2)
d["radar_lcd"] = [lx, ly, 2 * B.T + R.D - R.FRONT - 0.3, R.LCD_AA_W, R.LCD_AA_H]
(ROOT / "build" / "board.json").write_text(json.dumps(d, ensure_ascii=False))
print(len(json.dumps(d)) // 1024, "KB")
