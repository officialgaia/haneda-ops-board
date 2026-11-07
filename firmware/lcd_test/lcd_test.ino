// ============================================================
//  液晶の点検スケッチ（ADS-B レーダーと同じ配線）
//  1) バックライトだけを点ける（3 秒）
//  2) 液晶を初期化して 赤→緑→青→白→黒 を順に塗り、文字を出す
//  シリアルモニタ（115200）に今どこまで進んだかが出る
//  映らないときは下の SPI_MODE と SPI_FREQ を変えて試す
// ============================================================
#include <LovyanGFX.hpp>

#define PIN_TFT_SCK   4
#define PIN_TFT_MOSI  6
#define PIN_TFT_CS    7
#define PIN_TFT_DC    5
#define PIN_TFT_RST   3
#define PIN_TFT_BL    21

#define SPI_MODE  0          // 映らなければ 3 にする
#define SPI_FREQ  10000000   // 本番は 40MHz。配線が長いと速すぎて映らないので 10MHz で点検

class LGFX : public lgfx::LGFX_Device {
  lgfx::Panel_ST7789 _panel;
  lgfx::Bus_SPI _bus;
 public:
  LGFX() {
    auto b = _bus.config();
    b.spi_host = SPI2_HOST; b.spi_mode = SPI_MODE; b.freq_write = SPI_FREQ; b.freq_read = 8000000;
    b.pin_sclk = PIN_TFT_SCK; b.pin_mosi = PIN_TFT_MOSI; b.pin_miso = -1; b.pin_dc = PIN_TFT_DC;
    b.dma_channel = SPI_DMA_CH_AUTO;
    _bus.config(b); _panel.setBus(&_bus);
    auto p = _panel.config();
    p.pin_cs = PIN_TFT_CS; p.pin_rst = PIN_TFT_RST; p.pin_busy = -1;
    p.panel_width = 240; p.panel_height = 320; p.offset_x = 0; p.offset_y = 0;
    p.readable = false; p.invert = true; p.rgb_order = false; p.bus_shared = false;
    _panel.config(p);
    setPanel(&_panel);
  }
};
LGFX tft;

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\n[1] バックライトを点けます（液晶が白っぽく光れば BL の配線は OK）");
  pinMode(PIN_TFT_BL, OUTPUT);
  digitalWrite(PIN_TFT_BL, HIGH);
  delay(3000);

  Serial.println("[2] 液晶を初期化します");
  bool ok = tft.init();
  Serial.printf("    init: %s\n", ok ? "OK" : "失敗");
  digitalWrite(PIN_TFT_BL, HIGH);
}

void loop() {
  const uint16_t cols[] = {TFT_RED, TFT_GREEN, TFT_BLUE, TFT_WHITE, TFT_BLACK};
  const char* names[] = {"赤", "緑", "青", "白", "黒"};
  for (int i = 0; i < 5; i++) {
    Serial.printf("[3] 画面を %s で塗ります\n", names[i]);
    tft.fillScreen(cols[i]);
    tft.setTextColor(i == 3 ? TFT_BLACK : TFT_WHITE);
    tft.setTextSize(3);
    tft.setCursor(20, 140);
    tft.print("LCD TEST");
    delay(1500);
  }
}
