// ============================================================
//  羽田空港 運用ボード
//  ESP32-C3 SuperMini ＋ 在庫の LED 18 個（チャーリープレクシング 5 本線）
//
//  adsb.fi から羽田周辺の機体を取り、滑走路の延長線上で
//  降りてくる機体（着陸）・上がっていく機体（離陸）を見つけて、
//  使われている滑走路の端の LED を光らせる。
//
//  光の意味：緑＝着陸機が降りる端　黄＝離陸機が走り出す端　赤＝飛行機が向かう先の端
//  離陸のたびに：飛び立った滑走路の 黄（走り出す端）→ 赤（先の端）が速く点滅する
//  運用ランプ（RGB）：青＝北風運用　橙＝南風運用　白＝混在　赤の点滅＝データが取れない
//
//  ボード：ESP32C3 Dev Module ／ USB CDC On Boot: Enabled
//  電源：ケースの右の USB-C（レーダーの ESP32 とは別。線ではつながない）
//  ライブラリ：ArduinoJson 7.x
//  データ：adsb.fi（個人・非商用の利用に限る）
// ============================================================
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

// ------------------------------------------------------------
//  LED の表（線の番号：アノード → カソード）
// ------------------------------------------------------------
enum LedId {
  A16R_Y, A16R_R, A34L_G, A34L_R,
  B04_R, B22_G,
  C16L_Y, C16L_R, C34R_G, C34R_R, C34R_Y,
  D05_Y, D05_R, D23_G, D23_R,
  MODE_R, MODE_G, MODE_B,
  LED_COUNT
};
struct LedPins { uint8_t a, c; const char* name; };
static const LedPins LEDS[LED_COUNT] = {   // 名前の番号は配線図のカードの番号、線は 線1〜線5（a,c は 0〜4）
  {1, 0, "1 A16R 黄"}, {0, 1, "2 A16R 赤"}, {2, 0, "3 A34L 緑"}, {2, 1, "4 A34L 赤"},
  {3, 0, "5 B04 赤"},  {3, 1, "6 B22 緑"},
  {4, 0, "7 C16L 黄"}, {4, 1, "8 C16L 赤"}, {0, 3, "9 C34R 2色の緑"}, {1, 3, "9 C34R 2色の赤"}, {3, 2, "10 C34R 黄"},
  {4, 2, "11 D05 黄"}, {2, 3, "12 D05 赤"}, {0, 2, "13 D23 2色の緑"}, {1, 2, "13 D23 2色の赤"},
  {0, 4, "14 運用ランプ R"}, {1, 4, "14 運用ランプ G"}, {2, 4, "14 運用ランプ B"},
};

volatile uint8_t level[LED_COUNT];   // 0〜8

// ------------------------------------------------------------
//  滑走路（OpenStreetMap の中心線。基準点 35.546N 139.792E からの m）
// ------------------------------------------------------------
struct Runway {
  const char* name;
  const char* endName[2];
  float ax, ay, bx, by;
  int8_t green[2], yellow[2], red[2];   // 端ごとの LED（ない色は -1）
};
static const Runway RWY[4] = {
  {"A", {"16R", "34L"}, -2098, 1590,  -576, -1040, {-1, A34L_G}, {A16R_Y, -1},     {A16R_R, A34L_R}},
  {"B", {"04", "22"},   -2784,  334, -1352,  2374, {-1, B22_G},  {-1, -1},         {B04_R, -1}},
  {"C", {"16L", "34R"},  -492, 2204,  1188,  -698, {-1, C34R_G}, {C16L_Y, C34R_Y}, {C16L_R, C34R_R}},
  {"D", {"05", "23"},    1038, -2442, 2722,  -606, {-1, D23_G},  {D05_Y, -1},      {D05_R, D23_R}},
};
static const double REF_LAT = 35.546, REF_LON = 139.792;
static const double HND_LAT = 35.5494, HND_LON = 139.7798;

// 使用中の記録：[滑走路][走り出す端 0/1][0=着陸 1=離陸] → 最後に見えた時刻（ms、0 は見えていない）
uint32_t seenAt[4][2][2];
// 離陸の点滅：[滑走路][走り出す端] → 点滅を始めた時刻（ms、0 は点滅していない）
volatile uint32_t flashAt[4][2];
// 離陸を一度知らせた機体（同じ機体で何度も点滅しないように）
struct Recent { uint32_t hex; uint32_t t; };
Recent recent[32];
uint32_t takeoffCount = 0;
uint32_t fetchedAt = 0;
bool dataOk = false;

// 表示の切り替え（BOOT ボタン）
enum ViewMode { AUTO, DEMO_NORTH, DEMO_SOUTH, TEST };
ViewMode viewMode = AUTO;

// ------------------------------------------------------------
//  チャーリープレクシング：1 ミリ秒ごとに 1 個ずつ光らせる
// ------------------------------------------------------------
void allOff() {
  for (int i = 0; i < 5; i++) pinMode(WIRE_PIN[i], INPUT);
}

void scanTask(void*) {
  uint8_t frame = 0;
  for (;;) {
    bool any = false;
    for (int i = 0; i < LED_COUNT; i++) {
      uint8_t lv = level[i];
      if (!lv) continue;
      any = true;
      allOff();
      if ((frame & 7) < lv) {
        const LedPins& p = LEDS[i];
        pinMode(WIRE_PIN[p.a], OUTPUT); digitalWrite(WIRE_PIN[p.a], HIGH);
        pinMode(WIRE_PIN[p.c], OUTPUT); digitalWrite(WIRE_PIN[p.c], LOW);
      }
      vTaskDelay(1);
    }
    allOff();
    if (!any) vTaskDelay(10);
    frame++;
  }
}

// ------------------------------------------------------------
//  データの取得と判定
// ------------------------------------------------------------
void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);   // SuperMini はアンテナの都合で、送信を弱めた方がつながりやすい（レーダーと同じ）
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) delay(250);
  Serial.printf("Wi-Fi: %s\n", WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "つながらない");
}

// 1 機ぶんの判定。使っている滑走路が見つかれば記録する
// 離陸したばかりの機体なら点滅を始める
void newTakeoff(uint32_t hex, int r, int s, const char* flight) {
  uint32_t now = millis();
  int freeSlot = 0;
  for (int i = 0; i < 32; i++) {
    if (recent[i].hex == hex && now - recent[i].t < 20UL * 60 * 1000) return;   // もう知らせた機体
    if (recent[i].t < recent[freeSlot].t) freeSlot = i;                         // いちばん古い枠に上書き
  }
  recent[freeSlot] = {hex, now | 1};
  flashAt[r][s] = now | 1;
  takeoffCount++;
  Serial.printf("★ 離陸：%s  %s滑走路 %s から（起動してから %lu 機目）\n", flight, RWY[r].name, RWY[r].endName[s], takeoffCount);
}

void classify(uint32_t hex, const char* flight, double lat, double lon, int altFt, float track, float rate) {
  const double kx = 111320.0 * cos(REF_LAT * DEG_TO_RAD), ky = 110960.0;
  const float px = (lon - REF_LON) * kx, py = (lat - REF_LAT) * ky;
  const float tx = sinf(track * DEG_TO_RAD), ty = cosf(track * DEG_TO_RAD);
  const float cosAlign = cosf(ALIGN_DEG * DEG_TO_RAD);

  int bestR = -1, bestS = 0, bestKind = 0;
  float bestCross = 1e9, bestA = 0, bestL = 0;
  for (int r = 0; r < 4; r++) {
    const Runway& w = RWY[r];
    float dx = w.bx - w.ax, dy = w.by - w.ay;
    float L = sqrtf(dx * dx + dy * dy);
    float ux = dx / L, uy = dy / L;
    float along = (px - w.ax) * ux + (py - w.ay) * uy;
    float cross = fabsf((px - w.ax) * uy - (py - w.ay) * ux);
    float dot = tx * ux + ty * uy;
    int s;
    if (dot > cosAlign) s = 0;            // a → b に進んでいる（a の端から）
    else if (dot < -cosAlign) s = 1;      // b → a に進んでいる（b の端から）
    else continue;
    float a = (s == 0) ? along : L - along;   // 走り出す端からの距離
    int kind = -1;
    if (rate < -250 && a > -18000 && a < L * 0.4f) {
      if (cross < CENTERLINE_M + 0.03f * fmaxf(0, -a)) kind = 0;          // 着陸（進入中）
    } else if (rate > 250 && a > L * 0.3f && a < L + 15000) {
      if (cross < CENTERLINE_M + 0.03f * fmaxf(0, a - L)) kind = 1;       // 離陸（上昇中）
    }
    if (kind >= 0 && cross < bestCross) { bestCross = cross; bestR = r; bestS = s; bestKind = kind; bestA = a; bestL = L; }
  }
  if (bestR < 0) return;
  seenAt[bestR][bestS][bestKind] = millis() | 1;
  Serial.printf("  %-8s %5dft %+5.0ffpm  %s滑走路 %s %s\n", flight, altFt, rate, RWY[bestR].name,
                RWY[bestR].endName[bestS], bestKind == 0 ? "着陸" : "離陸");
  // 離陸したばかり（低く、滑走路の先から近い）なら点滅で知らせる
  if (bestKind == 1 && hex && altFt < TAKEOFF_ALT_FT && bestA < bestL + TAKEOFF_DIST_M)
    newTakeoff(hex, bestR, bestS, flight);
}

bool fetchAndClassify() {
  if (WiFi.status() != WL_CONNECTED) return false;
  char url[128];
  snprintf(url, sizeof(url), "https://opendata.adsb.fi/api/v3/lat/%.4f/lon/%.4f/dist/%d", HND_LAT, HND_LON, SEARCH_NM);
  WiFiClientSecure client;
  client.setInsecure();                 // 公開データの読み取りだけなので証明書の検証は省く
  HTTPClient http;
  http.useHTTP10(true);
  http.setTimeout(6000);
  if (!http.begin(client, url)) return false;
  int code = http.GET();
  if (code != 200) { Serial.printf("adsb.fi: HTTP %d\n", code); http.end(); return false; }

  JsonDocument filter;
  JsonObject f = filter["ac"].add<JsonObject>();
  for (const char* k : {"hex", "flight", "r", "alt_baro", "track", "baro_rate", "geom_rate", "lat", "lon"}) f[k] = true;
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) { Serial.printf("JSON: %s\n", err.c_str()); return false; }

  int n = 0;
  Serial.println("--- 羽田周辺 ---");
  for (JsonObject a : doc["ac"].as<JsonArray>()) {
    if (a["lat"].isNull() || a["track"].isNull() || !a["alt_baro"].is<int>()) continue;   // 地上（"ground"）は使わない
    int alt = a["alt_baro"].as<int>();
    if (alt > MAX_ALT_FT) continue;
    float rate = a["baro_rate"].is<float>() ? a["baro_rate"].as<float>() : (a["geom_rate"] | 0.0f);
    const char* fl = a["flight"] | (a["r"] | "?");
    const char* hx = a["hex"] | "";
    if (*hx == '~') hx++;                                   // ICAO 以外の番号には ~ が付く
    uint32_t hex = strtoul(hx, nullptr, 16);
    classify(hex, fl, a["lat"], a["lon"], alt, a["track"], rate);
    n++;
  }
  Serial.printf("低い高度の機体 %d 機\n", n);
  return true;
}

// ------------------------------------------------------------
//  表示
// ------------------------------------------------------------
uint8_t target[LED_COUNT];

void lightEvent(int r, int s, int kind, uint32_t now) {
  const Runway& w = RWY[r];
  int start = kind == 0 ? w.green[s] : w.yellow[s];
  if (start < 0) start = kind == 0 ? w.yellow[s] : w.green[s];   // その色がない端はもう一方の色で
  int end = w.red[1 - s];
  // 光の流れ：走り出す端が先に強く、少し遅れて先の端が強く光る
  float ph = (now % 2400) / 2400.0f;
  auto pulse = [&](float at) { return fmaxf(0, 1 - fabsf(ph - at) * 6); };
  if (start >= 0) target[start] = max<uint8_t>(target[start], LEVEL_ON + (uint8_t)((LEVEL_PULSE - LEVEL_ON) * pulse(0.15f) + 0.5f));
  if (end >= 0)   target[end]   = max<uint8_t>(target[end],   LEVEL_ON + (uint8_t)((LEVEL_PULSE - LEVEL_ON) * pulse(0.45f) + 0.5f));
}

void setMode(uint8_t r, uint8_t g, uint8_t b) { target[MODE_R] = r; target[MODE_G] = g; target[MODE_B] = b; }

void render() {
  uint32_t now = millis();
  memset(target, 0, sizeof(target));

  if (viewMode == TEST) {                       // LED 点検：1 個ずつ順番に
    int i = (now / 700) % LED_COUNT;
    target[i] = 8;
    static int last = -1;
    if (i != last) { Serial.printf("点検：No.%s（＋線%d −線%d）\n", LEDS[i].name, LEDS[i].a + 1, LEDS[i].c + 1); last = i; }
  } else if (viewMode == DEMO_NORTH) {          // 北風運用の見本
    lightEvent(0, 1, 0, now); lightEvent(2, 1, 0, now); lightEvent(2, 1, 1, now); lightEvent(3, 0, 1, now);
    setMode(0, 0, 8);
  } else if (viewMode == DEMO_SOUTH) {          // 南風運用の見本
    lightEvent(0, 0, 1, now); lightEvent(1, 1, 0, now); lightEvent(2, 0, 1, now); lightEvent(3, 1, 0, now);
    setMode(8, 2, 0);
  } else {                                      // 自動（ライブのデータ）
    int north = 0, south = 0;
    for (int r = 0; r < 4; r++)
      for (int s = 0; s < 2; s++)
        for (int k = 0; k < 2; k++) {
          uint32_t t = seenAt[r][s][k];
          if (!t || now - t > ACTIVE_HOLD_S * 1000UL) continue;
          lightEvent(r, s, k, now);
          bool isNorth = (r == 0 || r == 2) ? (s == 1) : (s == 0);   // 34L・34R・04・05 は北向き
          (isNorth ? north : south)++;
        }
    // 離陸の点滅（ほかの表示より優先）：黄 → 赤 の順に速く点滅
    for (int r = 0; r < 4; r++)
      for (int s = 0; s < 2; s++) {
        uint32_t t0 = flashAt[r][s];
        if (!t0) continue;
        uint32_t dt = now - t0;
        if (dt > FLASH_MS) { flashAt[r][s] = 0; continue; }
        const Runway& w = RWY[r];
        int start = w.yellow[s] >= 0 ? w.yellow[s] : w.green[s];
        int end = w.red[1 - s];
        bool on = (dt / 120) % 2 == 0;
        if (start >= 0) target[start] = (on && dt < FLASH_MS * 0.6f) ? LEVEL_PULSE : 0;
        if (end >= 0)   target[end]   = (!on && dt > FLASH_MS * 0.25f) ? LEVEL_PULSE : 0;
      }
    if (!dataOk) setMode((now / 500) % 2 ? 6 : 0, 0, 0);          // データが取れない：赤の点滅
    else if (north && !south) setMode(0, 0, 8);                   // 北風運用：青
    else if (south && !north) setMode(8, 2, 0);                   // 南風運用：橙
    else if (north && south) setMode(4, 4, 4);                    // 混在：白
    else setMode(0, 0, 0);                                        // 動きなし（深夜など）
  }
  for (int i = 0; i < LED_COUNT; i++) level[i] = target[i];
}

// 表示は別のタスクで 50 回/秒（データを取っている間も点滅が止まらない）
void renderTask(void*) {
  for (;;) { render(); vTaskDelay(20); }
}

// ------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  allOff();
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  xTaskCreate(scanTask, "scan", 2048, nullptr, 3, nullptr);

  // 起動時に全部を一度ずつ点けて配線を確かめる
  // 配線図のカードの番号 1 → 14 の順に光る（シリアルモニタにも番号が出る）
  for (int i = 0; i < LED_COUNT; i++) {
    Serial.printf("確認：No.%s（＋線%d −線%d）\n", LEDS[i].name, LEDS[i].a + 1, LEDS[i].c + 1);
    level[i] = 8; delay(250); level[i] = 0;
  }
  xTaskCreate(renderTask, "render", 4096, nullptr, 2, nullptr);
  connectWiFi();
}

void loop() {
  // BOOT ボタン：自動 → 北風の見本 → 南風の見本 → LED 点検
  static bool lastBtn = HIGH;
  bool b = digitalRead(PIN_BUTTON);
  if (lastBtn == HIGH && b == LOW) {
    viewMode = (ViewMode)((viewMode + 1) % 4);
    const char* names[] = {"自動", "北風運用の見本", "南風運用の見本", "LED 点検"};
    Serial.printf("表示：%s\n", names[viewMode]);
    delay(30);
  }
  lastBtn = b;

  if (millis() - fetchedAt > FETCH_INTERVAL_MS || fetchedAt == 0) {
    fetchedAt = millis();
    connectWiFi();
    dataOk = fetchAndClassify();
  }
  delay(20);
}
