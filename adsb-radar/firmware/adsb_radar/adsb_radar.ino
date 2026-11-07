// ============================================================
//  ADS-B レーダー（ESP32-C3 SuperMini + 2.0インチ ST7789 液晶）
//
//  adsb.fi の公開APIから、自宅の周りを飛ぶ飛行機を数秒おきに取得し、
//  レーダー画面に描きます。データの利用は個人・非商用に限られ、
//  画面に adsb.fi の表記を出すことが条件です。
//
//  必要なライブラリ（ライブラリマネージャで入れる）
//    - LovyanGFX   （液晶の描画）
//    - ArduinoJson （v7。データの読み取り）
//  ボード設定
//    - ボード：ESP32C3 Dev Module
//    - USB CDC On Boot：Enabled（シリアルモニタを使う場合）
// ============================================================
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <LovyanGFX.hpp>
#include <time.h>
#include "config.h"

// ------------------------------------------------------------
//  液晶の設定
// ------------------------------------------------------------
class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ST7789 _panel;
  lgfx::Bus_SPI _bus;
  lgfx::Light_PWM _light;
 public:
  LGFX() {
    {
      auto cfg = _bus.config();
      cfg.spi_host = SPI2_HOST;
      cfg.spi_mode = 0;
      cfg.freq_write = 40000000;
      cfg.freq_read = 16000000;
      cfg.pin_sclk = PIN_TFT_SCK;
      cfg.pin_mosi = PIN_TFT_MOSI;
      cfg.pin_miso = -1;
      cfg.pin_dc = PIN_TFT_DC;
      cfg.dma_channel = SPI_DMA_CH_AUTO;
      _bus.config(cfg);
      _panel.setBus(&_bus);
    }
    {
      auto cfg = _panel.config();
      cfg.pin_cs = PIN_TFT_CS;
      cfg.pin_rst = PIN_TFT_RST;
      cfg.pin_busy = -1;
      cfg.panel_width = 240;
      cfg.panel_height = 320;
      cfg.offset_x = 0;
      cfg.offset_y = 0;
      cfg.readable = false;
      cfg.invert = TFT_INVERT;
      cfg.rgb_order = false;
      cfg.bus_shared = false;
      _panel.config(cfg);
    }
    {
      auto cfg = _light.config();
      cfg.pin_bl = PIN_TFT_BL;
      cfg.invert = false;
      cfg.freq = 12000;
      cfg.pwm_channel = 0;
      _light.config(cfg);
      _panel.setLight(&_light);
    }
    setPanel(&_panel);
  }
};

static LGFX tft;
static LGFX_Sprite radar(&tft);   // レーダー部分（240x236）
static LGFX_Sprite info(&tft);    // 下の詳細欄（240x62）

// 画面の区割り
static const int HEADER_H = 22;
static const int RADAR_H = 236;
static const int INFO_Y = HEADER_H + RADAR_H;   // 258
static const int INFO_H = 320 - INFO_Y;          // 62
static const int CX = 120, CY = 118, R = 110;    // レーダー中心と半径（スプライト内座標）

// 色
static uint16_t C_BG, C_GRID, C_GRID2, C_SWEEP, C_SWEEP_DIM, C_PLANE, C_SEL, C_GROUND, C_TEXT, C_TEXT_DIM, C_WARN;

// ------------------------------------------------------------
//  機体データ
// ------------------------------------------------------------
struct Aircraft {
  char hex[8];
  char flight[10];   // 画面に出す便名（KE714 のような航空会社の 2 文字コード）
  char cs[10];       // 元のコールサイン（KAL714。出発地・目的地を調べるときに使う）
  char type[6];
  char reg[10];
  int  alt;        // ft。地上は -1
  float gs;        // kt
  float track;     // 度
  float rate;      // ft/min
  float x0, y0;    // 取得時点の位置（km。東がx、北がy）
  float x, y;      // 推定した現在位置
  float dist;      // km
  uint32_t t0;     // この位置を受け取った時刻（ms）
};

static const int MAX_AC = 48;            // 近い順にこの数まで覚える
static const uint32_t HOLD_MS = 20000;   // 1 回のデータに入っていなくても、この時間は表示を続ける（ちらつき防止）
static Aircraft ac[MAX_AC];
static int acCount = 0;
static uint32_t fetchedAt = 0;
static uint32_t lastFetchTry = 0;
static String lastError = "";
static char selHex[8] = "";
static int rangeIdx = DEFAULT_RANGE_INDEX;
static const int RANGE_COUNT = sizeof(RANGES_KM) / sizeof(RANGES_KM[0]);
static bool listView = false;
static bool buzzerOn = BUZZER_DEFAULT_ON;
static int brightIdx = 0;
static const uint8_t BRIGHT[] = {255, 110, 35};
static uint32_t buzzerUntil = 0;
static float sweepDeg = 0;

// 頭上通過の検出用（直前に圏内にいた機体）
static char nearHex[16][8];
static int nearCount = 0;

// ------------------------------------------------------------
//  ロータリーエンコーダ（割り込みで読む）
// ------------------------------------------------------------
static volatile int encAcc = 0;
static volatile uint8_t encPrev = 0;
static const int8_t ENC_TABLE[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

void IRAM_ATTR encISR() {
  uint8_t s = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  encPrev = ((encPrev << 2) | s) & 0x0F;
  encAcc += ENC_TABLE[encPrev];
}

int readEncoderSteps() {
  noInterrupts();
  int a = encAcc;
  int steps = a / 4;          // 1クリック = 4変化
  encAcc = a - steps * 4;
  interrupts();
  return steps;
}

// ------------------------------------------------------------
//  ボタン（チャタリング除去・長押し判定）
// ------------------------------------------------------------
struct Button {
  uint8_t pin;
  bool stable = true, last = true;
  uint32_t changedAt = 0, pressedAt = 0;
  bool longFired = false;
  // 戻り値：0=なし 1=短押し 2=長押し
  int poll() {
    bool now = digitalRead(pin);
    uint32_t t = millis();
    if (now != last) { last = now; changedAt = t; }
    if (t - changedAt > 25 && now != stable) {
      stable = now;
      if (!stable) { pressedAt = t; longFired = false; }
      else if (!longFired) return 1;
    }
    if (!stable && !longFired && t - pressedAt > 700) { longFired = true; return 2; }
    return 0;
  }
};
static Button btnEnc{PIN_ENC_SW}, btnView{PIN_BTN_VIEW}, btnLight{PIN_BTN_LIGHT};

// ------------------------------------------------------------
//  ブザー（止めずに鳴らすため、終了時刻だけ覚える）
// ------------------------------------------------------------
void beep(uint32_t ms) {
  if (!buzzerOn) return;
  digitalWrite(PIN_BUZZER, HIGH);
  buzzerUntil = millis() + ms;
}
void updateBuzzer() {
  if (buzzerUntil && (int32_t)(millis() - buzzerUntil) >= 0) {
    digitalWrite(PIN_BUZZER, LOW);
    buzzerUntil = 0;
  }
}

// ------------------------------------------------------------
//  データ取得（adsb.fi）
// ------------------------------------------------------------
static void copyStr(char* dst, size_t n, const char* src) {
  if (!src) { dst[0] = 0; return; }
  size_t i = 0;
  for (; i < n - 1 && src[i]; i++) dst[i] = src[i];
  dst[i] = 0;
  while (i > 0 && dst[i - 1] == ' ') dst[--i] = 0;   // 便名の末尾の空白を落とす
}

// ------------------------------------------------------------
//  便名の書き方：コールサイン（KAL714）→ 便名（KE714）
//  航空会社の 3 文字コード（ICAO）を 2 文字コード（IATA）に置きかえる
// ------------------------------------------------------------
static const char* const AIRLINES[][2] = {
  // 日本
  {"JAL", "JL"}, {"ANA", "NH"}, {"SKY", "BC"}, {"ADO", "HD"}, {"SNJ", "6J"}, {"SFJ", "7G"}, {"APJ", "MM"},
  {"JJP", "GK"}, {"TZP", "ZG"}, {"JTA", "NU"}, {"RAC", "JC"}, {"IBX", "FW"}, {"FDA", "JH"}, {"ORC", "OC"},
  {"AKX", "NH"}, {"JAC", "JL"}, {"NTH", "JL"}, {"JLJ", "JL"}, {"NCA", "KZ"}, {"SJO", "IJ"}, {"TOK", "BV"},
  // 韓国・中国・台湾・香港
  {"KAL", "KE"}, {"AAR", "OZ"}, {"JNA", "LJ"}, {"TWB", "TW"}, {"JJA", "7C"}, {"ABL", "BX"}, {"ESR", "ZE"},
  {"ASV", "RS"}, {"APZ", "YP"}, {"CCA", "CA"}, {"CES", "MU"}, {"CSN", "CZ"}, {"CHH", "HU"}, {"CXA", "MF"},
  {"CSZ", "ZH"}, {"CQH", "9C"}, {"DKH", "HO"}, {"CSC", "3U"}, {"CDG", "SC"}, {"CPA", "CX"}, {"HKE", "UO"},
  {"CRK", "HX"}, {"AMU", "NX"}, {"CAL", "CI"}, {"EVA", "BR"}, {"SJX", "JX"}, {"TTW", "IT"}, {"MDA", "AE"},
  {"MGL", "OM"},
  // 東南アジア・オセアニア・中東
  {"SIA", "SQ"}, {"TGW", "TR"}, {"THA", "TG"}, {"TLM", "SL"}, {"MAS", "MH"}, {"AXM", "AK"}, {"XAX", "D7"},
  {"GIA", "GA"}, {"PAL", "PR"}, {"CEB", "5J"}, {"APG", "Z2"}, {"HVN", "VN"}, {"VJC", "VJ"}, {"AIC", "AI"},
  {"QFA", "QF"}, {"JST", "JQ"}, {"ANZ", "NZ"}, {"UAE", "EK"}, {"QTR", "QR"}, {"ETD", "EY"}, {"THY", "TK"},
  // 欧米
  {"UAL", "UA"}, {"DAL", "DL"}, {"AAL", "AA"}, {"HAL", "HA"}, {"ACA", "AC"}, {"BAW", "BA"}, {"AFR", "AF"},
  {"DLH", "LH"}, {"KLM", "KL"}, {"FIN", "AY"}, {"SWR", "LX"}, {"AUA", "OS"}, {"SAS", "SK"}, {"ITY", "AZ"},
  {"LOT", "LO"}, {"ETH", "ET"}, {"FDX", "FX"}, {"UPS", "5X"}, {"GTI", "5Y"}, {"CLX", "CV"}, {"PAC", "PO"},
};

void toFlightNumber(const char* cs, char* out, size_t n) {
  copyStr(out, n, cs);
  if (strlen(cs) < 4 || !isalpha(cs[0]) || !isalpha(cs[1]) || !isalpha(cs[2]) || !isdigit(cs[3])) return;
  for (auto& a : AIRLINES) {
    if (strncmp(cs, a[0], 3) == 0) {
      const char* num = cs + 3;
      while (num[0] == '0' && isdigit(num[1])) num++;      // 先頭の 0 は落とす（JAL0516 → JL516）
      snprintf(out, n, "%s%s", a[1], num);
      return;
    }
  }
}

// ------------------------------------------------------------
//  出発地と目的地（adsbdb.com で調べる。つまみの長押しのときだけ）
// ------------------------------------------------------------
struct Route {
  char cs[10];
  bool ok;
  char flight[10], airline[28];
  char org[5], orgCity[22], dst[5], dstCity[22];
};
static Route routes[6];          // 調べた結果を覚えておく（同じ便を何度も調べない）
static int routeNext = 0;
static int routeShown = -1;      // 表示中の routes の番号（-1 は表示していない）
static uint32_t routeUntil = 0;

static void asciiCopy(char* dst, size_t n, const char* src) {   // 液晶のフォントに無い文字は落とす
  size_t j = 0;
  for (size_t i = 0; src && src[i] && j < n - 1; i++) {
    unsigned char c = src[i];
    if (c >= 0x20 && c < 0x7f) dst[j++] = c;
  }
  dst[j] = 0;
}

int lookupRoute(const char* cs) {
  for (int i = 0; i < 6; i++) if (routes[i].cs[0] && !strcmp(routes[i].cs, cs)) return i;
  Route& r = routes[routeNext];
  int idx = routeNext;
  routeNext = (routeNext + 1) % 6;
  memset(&r, 0, sizeof(r));
  copyStr(r.cs, sizeof(r.cs), cs);

  char url[96];
  snprintf(url, sizeof(url), "https://api.adsbdb.com/v0/callsign/%s", cs);
  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.useHTTP10(true);
  http.setTimeout(6000);
  if (!http.begin(client, url)) return idx;
  int code = http.GET();
  Serial.printf("route %s: HTTP %d\n", cs, code);
  if (code != 200) { http.end(); if (code != 404) r.cs[0] = 0; return idx; }   // 404 は「わからない便」として覚える

  JsonDocument filter;
  JsonObject fr = filter["response"]["flightroute"].to<JsonObject>();
  fr["callsign_iata"] = true;
  fr["airline"]["name"] = true;
  for (const char* k : {"origin", "destination"}) { fr[k]["iata_code"] = true; fr[k]["municipality"] = true; }
  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) { r.cs[0] = 0; return idx; }
  JsonObject f = doc["response"]["flightroute"];
  if (f.isNull()) return idx;
  r.ok = true;
  asciiCopy(r.flight, sizeof(r.flight), f["callsign_iata"] | "");
  asciiCopy(r.airline, sizeof(r.airline), f["airline"]["name"] | "");
  asciiCopy(r.org, sizeof(r.org), f["origin"]["iata_code"] | "???");
  asciiCopy(r.orgCity, sizeof(r.orgCity), f["origin"]["municipality"] | "");
  asciiCopy(r.dst, sizeof(r.dst), f["destination"]["iata_code"] | "???");
  asciiCopy(r.dstCity, sizeof(r.dstCity), f["destination"]["municipality"] | "");
  return idx;
}

bool fetchAircraft() {
  if (WiFi.status() != WL_CONNECTED) {
    lastError = "Wi-Fi offline";
    static uint32_t lastRetry = 0;                 // 切れていたら 15 秒ごとにつなぎ直す
    if (millis() - lastRetry > 15000) {
      lastRetry = millis();
      Serial.println("Wi-Fi offline -> reconnect");
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
      WiFi.setTxPower(WIFI_POWER_8_5dBm);
    }
    return false;
  }

  int rangeKm = RANGES_KM[rangeIdx];              // いま表示している範囲＋少しだけ取る（機体数とデータ量を減らす）
  int distNm = (int)ceil(rangeKm * 1.15 / 1.852) + 1;
  char url[128];
  snprintf(url, sizeof(url), "https://opendata.adsb.fi/api/v3/lat/%.4f/lon/%.4f/dist/%d", HOME_LAT, HOME_LON, distNm);

  WiFiClientSecure client;
  client.setInsecure();                 // 証明書の検証を省略（公開データの読み取り専用のため）
  HTTPClient http;
  http.useHTTP10(true);                 // チャンク転送を避けてストリームのまま読む
  http.setTimeout(6000);
  if (!http.begin(client, url)) { lastError = "URL error"; return false; }
  int code = http.GET();
  if (code != 200) {
    lastError = "API " + String(code) + " (" + String(ESP.getMaxAllocHeap() / 1024) + "k)";
    Serial.printf("API %d: %s / heap free %u, max block %u\n", code, http.errorToString(code).c_str(),
                  ESP.getFreeHeap(), ESP.getMaxAllocHeap());
    http.end();
    return false;
  }

  JsonDocument filter;
  JsonObject f = filter["ac"].add<JsonObject>();
  for (const char* k : {"hex", "flight", "t", "r", "alt_baro", "gs", "track", "baro_rate", "lat", "lon", "dst", "dir"}) f[k] = true;
  f["lastPosition"]["lat"] = true; f["lastPosition"]["lon"] = true; f["lastPosition"]["seen_pos"] = true;

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, http.getStream(), DeserializationOption::Filter(filter));
  http.end();
  if (err) { lastError = String("JSON ") + err.c_str(); return false; }

  const double cosLat = cos(HOME_LAT * DEG_TO_RAD);
  const uint32_t now = millis();
  // 今回の機体はいったん別の場所に集める（通信が終わってから確保するので、HTTPS 用のメモリを減らさない）
  Aircraft* nw = (Aircraft*)malloc(sizeof(Aircraft) * MAX_AC);
  if (!nw) { lastError = "memory"; return false; }

  // 今回のデータ：全部の機体の距離を計算し、近い順に MAX_AC 機だけ残す
  // （以前は先頭から 48 機で打ち切っていたため、機体が多いと毎回違う機体が抜けて、出たり消えたりしていた）
  int n = 0;
  for (JsonObject a : doc["ac"].as<JsonArray>()) {
    double lat, lon;
    if (!a["lat"].isNull() && !a["lon"].isNull()) { lat = a["lat"]; lon = a["lon"]; }
    else if (!a["lastPosition"]["lat"].isNull() && (a["lastPosition"]["seen_pos"] | 99.0f) < 20.0f) {
      lat = a["lastPosition"]["lat"]; lon = a["lastPosition"]["lon"];      // 位置の更新が少し途切れた機体
    } else continue;
    Aircraft p;
    copyStr(p.hex, sizeof(p.hex), a["hex"] | "");
    copyStr(p.cs, sizeof(p.cs), a["flight"] | "");
    if (p.cs[0]) toFlightNumber(p.cs, p.flight, sizeof(p.flight));
    else copyStr(p.flight, sizeof(p.flight), a["r"] | p.hex);
    copyStr(p.type, sizeof(p.type), a["t"] | "----");
    copyStr(p.reg, sizeof(p.reg), a["r"] | "");
    p.alt = a["alt_baro"].is<int>() ? a["alt_baro"].as<int>() : -1;   // "ground" のときは -1
    p.gs = a["gs"] | 0.0f;
    p.track = a["track"] | 0.0f;
    p.rate = a["baro_rate"] | 0.0f;
    p.x0 = (lon - HOME_LON) * 111.32 * cosLat;
    p.y0 = (lat - HOME_LAT) * 110.57;
    p.x = p.x0; p.y = p.y0;
    p.dist = sqrtf(p.x * p.x + p.y * p.y);
    p.t0 = now;
    if (n < MAX_AC) nw[n++] = p;
    else {                                          // いちばん遠い機体より近ければ入れ替える
      int far = 0;
      for (int i = 1; i < n; i++) if (nw[i].dist > nw[far].dist) far = i;
      if (p.dist < nw[far].dist) nw[far] = p;
    }
  }
  int fresh = n;
  // 前回いて今回いない機体は、HOLD_MS の間だけ残す（予測した位置で動き続ける）
  for (int i = 0; i < acCount && n < MAX_AC; i++) {
    if (now - ac[i].t0 > HOLD_MS) continue;
    bool found = false;
    for (int j = 0; j < fresh; j++) if (!strcmp(nw[j].hex, ac[i].hex)) { found = true; break; }
    if (!found) nw[n++] = ac[i];
  }
  memcpy(ac, nw, sizeof(Aircraft) * n);
  free(nw);
  acCount = n;
  fetchedAt = now;
  lastError = "";
  Serial.printf("aircraft: %d new + %d held (heap %u)\n", fresh, n - fresh, ESP.getMaxAllocHeap());

  // 近い順に並べる（エンコーダで選ぶ順番になる）
  for (int i = 1; i < acCount; i++) {
    Aircraft t = ac[i]; int j = i - 1;
    while (j >= 0 && ac[j].dist > t.dist) { ac[j + 1] = ac[j]; j--; }
    ac[j + 1] = t;
  }

  // 頭上通過のお知らせ：圏内に新しく入った機体があれば鳴らす
  char nowNear[16][8]; int nowN = 0; bool newcomer = false;
  for (int i = 0; i < acCount && nowN < 16; i++) {
    if (ac[i].dist > OVERHEAD_ALERT_KM) continue;
    strcpy(nowNear[nowN++], ac[i].hex);
    bool seen = false;
    for (int k = 0; k < nearCount; k++) if (!strcmp(nearHex[k], ac[i].hex)) seen = true;
    if (!seen) newcomer = true;
  }
  memcpy(nearHex, nowNear, sizeof(nowNear)); nearCount = nowN;
  if (newcomer) beep(180);
  return true;
}

// 取得してからの経過時間で位置を進める（画面の動きをなめらかにする）
void extrapolate() {
  for (int i = 0; i < acCount; i++) {
    Aircraft& p = ac[i];
    float dt = (millis() - p.t0) / 1000.0f;       // 機体ごとに、位置を受け取ってからの時間で進める
    if (dt > 30) dt = 30;
    float km = p.gs * 1.852f / 3600.0f * dt;
    p.x = p.x0 + km * sinf(p.track * DEG_TO_RAD);
    p.y = p.y0 + km * cosf(p.track * DEG_TO_RAD);
    p.dist = sqrtf(p.x * p.x + p.y * p.y);
  }
}

// ------------------------------------------------------------
//  選択中の機体
// ------------------------------------------------------------
int rangeKm() { return RANGES_KM[rangeIdx]; }

int visibleIndex(int nth) {   // 範囲内の nth 番目の機体の添字
  int k = 0;
  for (int i = 0; i < acCount; i++) if (ac[i].dist <= rangeKm()) { if (k == nth) return i; k++; }
  return -1;
}
int visibleCount() {
  int k = 0;
  for (int i = 0; i < acCount; i++) if (ac[i].dist <= rangeKm()) k++;
  return k;
}
int selectedIndex() {
  for (int i = 0; i < acCount; i++) if (!strcmp(ac[i].hex, selHex) && ac[i].dist <= rangeKm()) return i;
  int i = visibleIndex(0);                       // いなくなったら一番近い機体を選び直す
  if (i >= 0) strcpy(selHex, ac[i].hex); else selHex[0] = 0;
  return i;
}
void moveSelection(int steps) {
  int n = visibleCount(); if (n == 0) return;
  int cur = 0, si = selectedIndex();
  for (int k = 0; k < n; k++) if (visibleIndex(k) == si) cur = k;
  cur = ((cur + steps) % n + n) % n;
  strcpy(selHex, ac[visibleIndex(cur)].hex);
}

// ------------------------------------------------------------
//  描画
// ------------------------------------------------------------
String flStr(const Aircraft& p) {
  if (p.alt < 0) return "GND";
  char b[8]; snprintf(b, sizeof(b), "FL%03d", (p.alt + 50) / 100); return String(b);
}
char trendChar(const Aircraft& p) { return p.rate > 300 ? '^' : (p.rate < -300 ? 'v' : ' '); }

void drawHeader() {
  static String prev = "";
  struct tm tmv; char clk[6] = "--:--";
  if (getLocalTime(&tmv, 0)) strftime(clk, sizeof(clk), "%H:%M", &tmv);
  char left[24]; snprintf(left, sizeof(left), "ADS-B  %dkm", rangeKm());
  char mid[12]; snprintf(mid, sizeof(mid), "%d ac", visibleCount());
  String key = String(left) + mid + clk + (buzzerOn ? "B" : "-") + (listView ? "L" : "R");
  if (key == prev) return;
  prev = key;
  tft.fillRect(0, 0, 240, HEADER_H, C_BG);
  tft.setFont(&fonts::Font2);
  tft.setTextColor(C_TEXT, C_BG);
  tft.setTextDatum(middle_left);   tft.drawString(left, 6, 11);
  tft.setTextDatum(middle_center); tft.drawString(mid, 138, 11);
  tft.setTextDatum(middle_right);  tft.drawString(clk, 234, 11);
  if (!buzzerOn) { tft.setTextColor(C_TEXT_DIM, C_BG); tft.setTextDatum(middle_right); tft.drawString("mute", 196, 11); }
  tft.drawFastHLine(0, HEADER_H - 1, 240, C_GRID);
}

void drawPlane(LGFX_Sprite& s, const Aircraft& p, float scale, bool sel) {
  int px = CX + (int)(p.x * scale), py = CY - (int)(p.y * scale);
  uint16_t col = sel ? C_SEL : (p.alt < 0 ? C_GROUND : C_PLANE);
  float a = p.track * DEG_TO_RAD, sa = sinf(a), ca = cosf(a);
  // 進行方向の線
  s.drawLine(px, py, px + (int)(sa * 14), py - (int)(ca * 14), sel ? C_SEL : C_SWEEP_DIM);
  // 機体（三角形を進行方向に回す）
  auto rx = [&](float x, float y) { return px + (int)(x * ca - y * sa); };
  auto ry = [&](float x, float y) { return py + (int)(x * sa + y * ca); };
  s.fillTriangle(rx(0, -6), ry(0, -6), rx(-4, 4), ry(-4, 4), rx(4, 4), ry(4, 4), col);
  // ラベル（右側に置き、端では左側に回す）
  s.setFont(&fonts::Font0);
  s.setTextColor(col);
  bool left = px > 190;
  s.setTextDatum(left ? top_right : top_left);
  int lx = left ? px - 7 : px + 7;
  s.drawString(p.flight, lx, py - 9);
  String fl = flStr(p); fl += trendChar(p);
  s.drawString(fl, lx, py + 1);
}

void drawRadar() {
  radar.fillScreen(C_BG);
  float scale = (float)R / rangeKm();
  int step = rangeKm() <= 10 ? 5 : 10;

  // 距離の円と十字
  for (int km = step; km <= rangeKm(); km += step) {
    int r = (int)(km * scale);
    radar.drawCircle(CX, CY, r, km == rangeKm() ? C_GRID : C_GRID2);
    if (km < rangeKm()) {
      radar.setFont(&fonts::Font0); radar.setTextColor(C_GRID); radar.setTextDatum(bottom_left);
      radar.drawString(String(km), CX + r + 2, CY - 1);
    }
  }
  radar.drawFastVLine(CX, CY - R, 2 * R, C_GRID2);
  radar.drawFastHLine(CX - R, CY, 2 * R, C_GRID2);
  radar.setFont(&fonts::Font0); radar.setTextColor(C_GRID); radar.setTextDatum(bottom_center);
  radar.drawString("N", CX, CY - R - 1);

  // スイープ（北から時計回り。LovyanGFXの角度は3時方向が0度）
  radar.fillArc(CX, CY, R - 1, 0, sweepDeg - 90 - 28, sweepDeg - 90, C_SWEEP_DIM);
  float sa = (sweepDeg) * DEG_TO_RAD;
  radar.drawLine(CX, CY, CX + (int)(sinf(sa) * R), CY - (int)(cosf(sa) * R), C_SWEEP);

  // 機体（選択中は最後に描いて一番上に）
  int si = selectedIndex();
  for (int i = acCount - 1; i >= 0; i--) if (i != si && ac[i].dist <= rangeKm()) drawPlane(radar, ac[i], scale, false);
  if (si >= 0) drawPlane(radar, ac[si], scale, true);

  // 自宅
  radar.fillCircle(CX, CY, 2, C_TEXT);

  // 状態とデータ提供元の表記
  radar.setFont(&fonts::Font0); radar.setTextDatum(bottom_left);
  radar.setTextColor(C_TEXT_DIM); radar.drawString("Data: adsb.fi", 3, RADAR_H - 2);
  if (lastError.length()) { radar.setTextColor(C_WARN); radar.setTextDatum(bottom_right); radar.drawString(lastError, 237, RADAR_H - 2); }
  else if (acCount == 0 && fetchedAt == 0) { radar.setTextColor(C_TEXT); radar.setTextDatum(middle_center); radar.drawString("Loading...", CX, CY + 20); }

  radar.pushSprite(0, HEADER_H);
}

void drawList() {
  radar.fillScreen(C_BG);
  radar.setFont(&fonts::Font2);
  radar.setTextDatum(middle_left);
  radar.setTextColor(C_TEXT_DIM);
  radar.drawString("FLIGHT", 6, 9); radar.drawString("TYPE", 82, 9); radar.drawString("ALT", 128, 9);
  radar.setTextDatum(middle_right); radar.drawString("km", 234, 9);
  radar.drawFastHLine(0, 19, 240, C_GRID2);
  int si = selectedIndex(), n = visibleCount();
  // 選択中の行が見えるようにスクロール
  int selPos = 0; for (int k = 0; k < n; k++) if (visibleIndex(k) == si) selPos = k;
  const int rows = 11, rowH = 19;
  int top = selPos >= rows ? selPos - rows + 1 : 0;
  for (int r = 0; r < rows && top + r < n; r++) {
    const Aircraft& p = ac[visibleIndex(top + r)];
    int y = 22 + r * rowH;
    bool sel = (visibleIndex(top + r) == si);
    if (sel) radar.fillRect(0, y, 240, rowH, C_GRID2);
    uint16_t col = sel ? C_SEL : (p.alt < 0 ? C_GROUND : C_PLANE);
    radar.setTextColor(col);
    radar.setTextDatum(middle_left);
    radar.drawString(p.flight, 6, y + rowH / 2);
    radar.drawString(p.type, 82, y + rowH / 2);
    String fl = flStr(p); fl += trendChar(p);
    radar.drawString(fl, 128, y + rowH / 2);
    radar.setTextDatum(middle_right);
    char d[8]; snprintf(d, sizeof(d), "%.1f", p.dist);
    radar.drawString(d, 234, y + rowH / 2);
  }
  if (n == 0) { radar.setTextColor(C_TEXT_DIM); radar.setTextDatum(middle_center); radar.drawString("No aircraft in range", 120, 110); }
  radar.setFont(&fonts::Font0); radar.setTextDatum(bottom_left);
  radar.setTextColor(C_TEXT_DIM); radar.drawString("Data: adsb.fi", 3, RADAR_H - 2);
  radar.pushSprite(0, HEADER_H);
}

void drawRoute() {
  const Route& r = routes[routeShown];
  radar.fillScreen(C_BG);
  radar.setTextDatum(top_center);
  radar.setFont(&fonts::Font2); radar.setTextColor(C_TEXT_DIM);
  radar.drawString("ROUTE", CX, 8);
  int si = selectedIndex();
  const char* fl = r.flight[0] ? r.flight : (si >= 0 ? ac[si].flight : r.cs);
  radar.setFont(&fonts::Font4); radar.setTextColor(C_SEL);
  radar.drawString(fl, CX, 28);
  if (!r.ok) {
    radar.setFont(&fonts::Font2); radar.setTextColor(C_TEXT);
    radar.drawString(r.cs[0] ? "Route unknown" : "Lookup failed", CX, 100);
    radar.setTextColor(C_TEXT_DIM);
    radar.drawString("(not in the database)", CX, 122);
  } else {
    radar.setFont(&fonts::Font2); radar.setTextColor(C_TEXT);
    radar.drawString(r.airline, CX, 58);
    // 出発地 → 目的地
    radar.setFont(&fonts::Font4); radar.setTextColor(C_PLANE);
    radar.setTextDatum(top_center);
    radar.drawString(r.org, 60, 100);
    radar.drawString(r.dst, 180, 100);
    radar.fillTriangle(132, 112, 108, 102, 108, 122, C_SEL);
    radar.fillRect(98, 109, 12, 6, C_SEL);
    radar.setFont(&fonts::Font2); radar.setTextColor(C_TEXT_DIM);
    radar.drawString("FROM", 60, 82); radar.drawString("TO", 180, 82);
    radar.setFont(&fonts::Font0); radar.setTextColor(C_TEXT);
    radar.drawString(r.orgCity, 60, 132); radar.drawString(r.dstCity, 180, 132);
  }
  radar.setFont(&fonts::Font0); radar.setTextColor(C_TEXT_DIM); radar.setTextDatum(bottom_center);
  radar.drawString("Press any button to return", CX, RADAR_H - 14);
  radar.setTextDatum(bottom_left); radar.drawString("Route: adsbdb.com", 3, RADAR_H - 2);
  radar.pushSprite(0, HEADER_H);
}

void showRoute() {
  int si = selectedIndex();
  if (si < 0) return;
  if (!ac[si].cs[0]) {                            // コールサインが出ていない機体
    static Route none; memset(&none, 0, sizeof(none)); copyStr(none.cs, sizeof(none.cs), ac[si].flight);
    routes[5] = none; routeShown = 5; routeUntil = millis() + 4000; return;
  }
  radar.fillScreen(C_BG);
  radar.setFont(&fonts::Font2); radar.setTextColor(C_TEXT); radar.setTextDatum(middle_center);
  radar.drawString("Looking up route...", CX, CY);
  radar.pushSprite(0, HEADER_H);
  routeShown = lookupRoute(ac[si].cs);
  routeUntil = millis() + 12000;
}

void drawInfo() {
  info.fillScreen(C_BG);
  info.drawFastHLine(0, 0, 240, C_GRID);
  int si = selectedIndex();
  if (si < 0) {
    info.setFont(&fonts::Font2); info.setTextColor(C_TEXT_DIM); info.setTextDatum(middle_center);
    info.drawString(WiFi.status() == WL_CONNECTED ? "No aircraft in range" : "Connecting Wi-Fi...", 120, 31);
    info.pushSprite(0, INFO_Y);
    return;
  }
  const Aircraft& p = ac[si];
  info.setFont(&fonts::Font4); info.setTextColor(C_SEL); info.setTextDatum(top_left);
  info.drawString(p.flight, 6, 4);
  info.setFont(&fonts::Font2); info.setTextColor(C_PLANE); info.setTextDatum(top_right);
  String t = String(p.type); if (p.reg[0]) { t += "  "; t += p.reg; }
  info.drawString(t, 234, 8);

  char l1[40], l2[40];
  if (p.alt < 0) snprintf(l1, sizeof(l1), "ON GROUND   GS %3.0fkt", p.gs);
  else snprintf(l1, sizeof(l1), "ALT %dft %c  GS %3.0fkt", p.alt, trendChar(p), p.gs);
  float brg = fmodf(atan2f(p.x, p.y) * RAD_TO_DEG + 360.0f, 360.0f);
  snprintf(l2, sizeof(l2), "HDG %03.0f   %.1fkm / %03.0f", p.track, p.dist, brg);
  info.setTextColor(C_TEXT); info.setTextDatum(top_left);
  info.drawString(l1, 6, 30);
  info.drawString(l2, 6, 46);
  info.pushSprite(0, INFO_Y);
}

// ------------------------------------------------------------
//  起動
// ------------------------------------------------------------
bool makeSprite(LGFX_Sprite& s, int w, int h, int depth = 16) {
  s.setColorDepth(depth);
  if (s.createSprite(w, h)) return true;
  s.setColorDepth(8);                 // メモリが足りないときは色数を落とす
  return s.createSprite(w, h) != nullptr;
}

void splash(const char* line1, const char* line2) {
  tft.fillScreen(C_BG);
  tft.setTextDatum(middle_center);
  tft.setFont(&fonts::Font4); tft.setTextColor(C_SEL, C_BG); tft.drawString("ADS-B RADAR", 120, 130);
  tft.setFont(&fonts::Font2); tft.setTextColor(C_TEXT, C_BG); tft.drawString(line1, 120, 166);
  tft.setTextColor(C_TEXT_DIM, C_BG); tft.drawString(line2, 120, 186);
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT); digitalWrite(PIN_BUZZER, LOW);
  pinMode(PIN_ENC_A, INPUT_PULLUP); pinMode(PIN_ENC_B, INPUT_PULLUP);
  pinMode(PIN_ENC_SW, INPUT_PULLUP); pinMode(PIN_BTN_VIEW, INPUT_PULLUP); pinMode(PIN_BTN_LIGHT, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encISR, CHANGE);

  tft.init();
  tft.setRotation(0);
  tft.setBrightness(BRIGHT[brightIdx]);
  C_BG = tft.color565(6, 18, 13);
  C_GRID = tft.color565(47, 110, 83);
  C_GRID2 = tft.color565(22, 56, 42);
  C_SWEEP = tft.color565(61, 220, 151);
  C_SWEEP_DIM = tft.color565(14, 48, 34);
  C_PLANE = tft.color565(126, 226, 184);
  C_SEL = tft.color565(245, 185, 66);
  C_GROUND = tft.color565(110, 125, 118);
  C_TEXT = tft.color565(200, 235, 218);
  C_TEXT_DIM = tft.color565(90, 130, 112);
  C_WARN = tft.color565(240, 120, 100);

  // レーダー部分は 8bit 色にしてメモリを空ける（https の通信に 40〜50KB 必要なため）
  if (!makeSprite(radar, 240, RADAR_H, 8) || !makeSprite(info, 240, INFO_H)) {
    splash("Out of memory", "sprite allocation failed");
    while (true) delay(1000);
  }

  // 前回の再起動の理由（電源の電圧低下で再起動をくり返していないかを見る）
  esp_reset_reason_t rr = esp_reset_reason();
  Serial.printf("reset reason: %d\n", (int)rr);
  if (rr == ESP_RST_BROWNOUT) { splash("Power dropped (brownout)", "Check USB cable / charger"); delay(2500); }

  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);   // ESP32-C3 SuperMini はアンテナの都合で、出力を下げないとつながらないことが多い
  uint32_t t0 = millis();
  int lastSec = -1;
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 20000) {
    int sec = (millis() - t0) / 1000;
    if (sec != lastSec) {                 // 経過秒数を出す（止まっていないことが分かる）
      lastSec = sec;
      char l2[48]; snprintf(l2, sizeof(l2), "%s  %ds / 20s  (status %d)", WIFI_SSID, sec, (int)WiFi.status());
      splash("Connecting Wi-Fi...", l2);
      Serial.println(l2);
    }
    delay(100);
  }
  if (WiFi.status() != WL_CONNECTED) {
    // 見えている Wi-Fi の名前を出す（設定したWi-Fiが見えているかの確認）
    splash("Wi-Fi failed. Scanning...", "");
    int n = WiFi.scanNetworks();
    tft.fillScreen(C_BG);
    tft.setTextDatum(top_left); tft.setFont(&fonts::Font2);
    tft.setTextColor(C_WARN, C_BG); tft.drawString("Wi-Fi failed. Networks found:", 8, 20);
    tft.setTextColor(C_TEXT, C_BG);
    bool seen = false;
    for (int i = 0; i < n && i < 10; i++) {
      char l[48]; snprintf(l, sizeof(l), "%s  %ddBm  %s", WiFi.SSID(i).c_str(), WiFi.RSSI(i), WiFi.channel(i) > 14 ? "5GHz" : "");
      tft.drawString(l, 8, 50 + i * 20);
      Serial.println(l);
      if (WiFi.SSID(i) == WIFI_SSID) seen = true;
    }
    tft.setTextColor(seen ? C_TEXT : C_WARN, C_BG);
    tft.drawString(seen ? "\"" WIFI_SSID "\" found: check password" : "\"" WIFI_SSID "\" NOT found", 8, 270);
    tft.setTextColor(C_TEXT_DIM, C_BG);
    tft.drawString("Retrying in background...", 8, 292);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    WiFi.setTxPower(WIFI_POWER_8_5dBm);
    delay(8000);
  }
  splash(WiFi.status() == WL_CONNECTED ? "Wi-Fi connected" : "Wi-Fi failed (retrying)", "Data: adsb.fi");
  configTzTime("JST-9", "ntp.nict.jp", "pool.ntp.org");
  delay(600);
  tft.fillScreen(C_BG);
}

// ------------------------------------------------------------
//  メインループ
// ------------------------------------------------------------
void loop() {
  // 入力
  int steps = readEncoderSteps();
  int be = btnEnc.poll(), bv = btnView.poll();
  int lb = btnLight.poll();
  if (routeShown >= 0) {                          // 出発地・目的地の表示中：何か押したら戻る
    if (steps || be || bv || lb || (int32_t)(millis() - routeUntil) > 0) routeShown = -1;
    steps = 0; be = bv = lb = 0;
  }
  if (be == 2) showRoute();                        // つまみの長押し：出発地と目的地
  if (steps) moveSelection(steps);
  if (be == 1) {
    rangeIdx = (rangeIdx + 1) % RANGE_COUNT;
    if (millis() - lastFetchTry > 1500) lastFetchTry = millis() - FETCH_INTERVAL_MS;   // 範囲を広げたらすぐ取り直す
  }
  if (bv == 1) listView = !listView;
  if (lb == 1) { brightIdx = (brightIdx + 1) % 3; tft.setBrightness(BRIGHT[brightIdx]); }
  if (lb == 2) { buzzerOn = !buzzerOn; if (buzzerOn) beep(60); }
  updateBuzzer();

  // データ取得
  if (millis() - lastFetchTry >= FETCH_INTERVAL_MS || lastFetchTry == 0) {
    lastFetchTry = millis();
    fetchAircraft();
  }

  // 描画（約25fps）
  static uint32_t lastFrame = 0;
  if (millis() - lastFrame >= 40) {
    float dt = (millis() - lastFrame) / 1000.0f;
    lastFrame = millis();
    sweepDeg = fmodf(sweepDeg + 90.0f * dt, 360.0f);   // 4秒で1周
    extrapolate();
    drawHeader();
    if (routeShown >= 0) drawRoute();
    else if (listView) drawList(); else drawRadar();
    drawInfo();
  }
}
