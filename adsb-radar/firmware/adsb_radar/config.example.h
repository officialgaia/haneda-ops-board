// ============================================================
//  ADS-B レーダー  設定ファイル
//  ここだけ自分の環境に書き換えてから書き込んでください
// ============================================================
#pragma once

// ---- Wi-Fi（2.4GHz帯のSSIDを指定。ESP32-C3は5GHzにつながりません）----
#define WIFI_SSID     "YOUR_SSID"
#define WIFI_PASSWORD "YOUR_PASSWORD"

// ---- レーダーの中心（自分の家の緯度・経度）----
// Googleマップで家を右クリックすると表示される数字をそのまま入れます
#define HOME_LAT  35.6179
#define HOME_LON  139.5543

// ---- 表示範囲（km）。エンコーダを押すたびにこの順で切り替わります ----
static const int RANGES_KM[] = {10, 20, 30, 50};
#define DEFAULT_RANGE_INDEX 2   // 0始まり。2 = 30km

// ---- 何秒ごとにデータを取りに行くか（adsb.fi の上限は1秒に1回）----
#define FETCH_INTERVAL_MS 5000

// ---- 頭上通過のお知らせ（この距離以内に新しい機体が入ったらブザーを鳴らす）----
#define OVERHEAD_ALERT_KM 3.0
#define BUZZER_DEFAULT_ON true

// ---- 液晶の色が反転して見えるときは false にする ----
#define TFT_INVERT true

// ---- ピン割り当て（ESP32-C3 SuperMini）----
#define PIN_TFT_SCK   4
#define PIN_TFT_MOSI  6   // 液晶の「SDA」
#define PIN_TFT_CS    7
#define PIN_TFT_DC    5
#define PIN_TFT_RST   3
#define PIN_TFT_BL    21  // 起動時に通信ログが出るピン。バックライトなら一瞬ちらつくだけで無害
#define PIN_ENC_A     20  // エンコーダの CLK
#define PIN_ENC_B     1   // エンコーダの DT
#define PIN_ENC_SW    10  // エンコーダの SW（押し込み）
#define PIN_BTN_VIEW  9   // ボタンA：表示切替（基板の BOOT ボタンと同じピン）
#define PIN_BTN_LIGHT 8   // ボタンB：明るさ／長押しでブザーON/OFF
#define PIN_BUZZER    0   // アクティブブザーモジュールの S
