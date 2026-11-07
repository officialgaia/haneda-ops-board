// ============================================================
//  羽田空港 運用ボード  設定ファイル
// ============================================================
#pragma once

// ---- Wi-Fi（2.4GHz）----
#define WIFI_SSID     "YOUR_SSID"
#define WIFI_PASSWORD "YOUR_PASSWORD"

// ---- データを取りに行く間隔（adsb.fi の上限は 1 秒に 1 回。レーダー（5 秒ごと）と合わせても余裕あり）----
#define FETCH_INTERVAL_MS 5000

// ---- 羽田の周り何海里（nm）の機体を見るか ----
#define SEARCH_NM 12

// ---- 判定のしきい値 ----
#define MAX_ALT_FT        4000   // これより高い機体は判定に使わない
#define ACTIVE_HOLD_S     300    // 最後に見えてから何秒間「使用中」として光らせ続けるか
#define ALIGN_DEG         20     // 滑走路の向きとの角度の差がこれ以内なら「その滑走路を使っている」
#define CENTERLINE_M      450    // 滑走路の延長線からの横ずれがこれ以内（遠いほど少し広げる）

// ---- 離陸の点滅 ----
#define TAKEOFF_ALT_FT  2500     // これより低い上昇中の機体を「いま離陸した」とみなす
#define TAKEOFF_DIST_M  9000     // 滑走路の先からこの距離まで
#define FLASH_MS        4000     // 点滅を続ける時間

// ---- LED の明るさ（0〜8）----
#define LEVEL_ON    5
#define LEVEL_PULSE 8

// ---- LED の線（チャーリープレクシング。47Ω を通して 5 本の線へ）----
//  配線図の 線1〜線5（茶・紫・青・灰・白）と ESP32-C3 のピン（GPIO3〜7）
static const uint8_t WIRE_PIN[5] = {3, 4, 5, 6, 7};

// ---- 本体の BOOT ボタン（GPIO9）：押すたびに 自動 → 北風の見本 → 南風の見本 → LED 点検 ----
#define PIN_BUTTON 9
