// ROVO Nano ESP32, Protokoll 1. Keine Bewegung beim Booten.
// GPIO-Nummern für PWM gehen direkt an ESP-IDF; D-Pins sind Arduino-Boardlabels.
#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <driver/ledc.h>
#include <math.h>
#include "calibration.h"

Adafruit_ST7789 screen(D10, D6, D5);
GFXcanvas16 canvas(260, 100);
constexpr int PAN_GPIO = 18;
constexpr int TILT_GPIO = 17;
constexpr uint32_t WATCHDOG_MS = 800;
char lineBuffer[128];
size_t lineLength = 0;
bool overflowed = false;
bool pwmActive = false;
float pan = PAN_HOME_DEG, tilt = TILT_HOME_DEG;
float panTarget = PAN_HOME_DEG, tiltTarget = TILT_HOME_DEG;
float panVelocity = 0, tiltVelocity = 0;
float runtimeSpeed = MAX_SPEED_DEG_S, runtimeAccel = MAX_ACCEL_DEG_S2;
uint32_t activeId = 0, lastRx = 0, lastServo = 0, lastDraw = 0, faceUntil = 0;
uint32_t lastMove = 0;
String face = "NEUTRAL";
uint8_t brightness = 100;
bool backlightPwmActive = false;
uint16_t dimColor(uint16_t color) {
  return ((((color >> 11) & 31) * brightness / 100) << 11) |
         ((((color >> 5) & 63) * brightness / 100) << 5) |
         ((color & 31) * brightness / 100);
}

bool initBacklightPwm() {
  ledc_timer_config_t timer = {};
  timer.speed_mode = LEDC_LOW_SPEED_MODE;
  timer.timer_num = LEDC_TIMER_1;
  timer.duty_resolution = LEDC_TIMER_8_BIT;
  timer.freq_hz = 5000;
  timer.clk_cfg = LEDC_AUTO_CLK;
  if (ledc_timer_config(&timer) != ESP_OK) return false;
  ledc_channel_config_t channel = {};
  channel.gpio_num = digitalPinToGPIONumber(D4);
  channel.speed_mode = LEDC_LOW_SPEED_MODE;
  channel.channel = LEDC_CHANNEL_2;
  channel.timer_sel = LEDC_TIMER_1;
  channel.duty = 255;
  if (ledc_channel_config(&channel) != ESP_OK) return false;
  backlightPwmActive = true;
  return true;
}

bool setBacklight(uint8_t percent) {
  if (!backlightPwmActive && !initBacklightPwm()) return false;
  uint32_t value = uint32_t(percent) * 255 / 100;
  if (ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2, value) != ESP_OK) return false;
  return ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_2) == ESP_OK;
}

#if ROVO_ENABLE_SERVOS
static_assert(ROVO_CALIBRATED == 1, "Servos brauchen bestaetigte Kalibrierung");
static_assert(PAN_MIN_DEG < PAN_MAX_DEG && PAN_HOME_DEG >= PAN_MIN_DEG && PAN_HOME_DEG <= PAN_MAX_DEG, "Pan-Limits ungueltig");
static_assert(TILT_MIN_DEG < TILT_MAX_DEG && TILT_HOME_DEG >= TILT_MIN_DEG && TILT_HOME_DEG <= TILT_MAX_DEG, "Tilt-Limits ungueltig");
static_assert(PAN_US_MIN >= 400 && PAN_US_MAX <= 2600 && PAN_US_MIN < PAN_US_MAX, "Pan-Pulsweiten pruefen");
static_assert(TILT_US_MIN >= 400 && TILT_US_MAX <= 2600 && TILT_US_MIN < TILT_US_MAX, "Tilt-Pulsweiten pruefen");
static_assert(MAX_SPEED_DEG_S > 0 && MAX_SPEED_DEG_S <= 60 && MAX_ACCEL_DEG_S2 > 0 && MAX_ACCEL_DEG_S2 <= 120, "Bewegungsprofil ungueltig");
#endif

uint32_t duty(float angle, int minUs, int maxUs) {
  return uint32_t((minUs + angle / 180.0f * (maxUs - minUs)) / 20000.0f * 16383.0f);
}

bool initPwm() {
#if ROVO_ENABLE_SERVOS && ROVO_CALIBRATED
  ledc_timer_config_t timer = {};
  timer.speed_mode = LEDC_LOW_SPEED_MODE;
  timer.timer_num = LEDC_TIMER_0;
  timer.duty_resolution = LEDC_TIMER_14_BIT;
  timer.freq_hz = 50;
  timer.clk_cfg = LEDC_AUTO_CLK;
  if (ledc_timer_config(&timer) != ESP_OK) return false;
  for (int axis = 0; axis < 2; axis++) {
    ledc_channel_config_t ch = {};
    ch.gpio_num = axis == 0 ? PAN_GPIO : TILT_GPIO;
    ch.speed_mode = LEDC_LOW_SPEED_MODE;
    ch.channel = axis == 0 ? LEDC_CHANNEL_0 : LEDC_CHANNEL_1;
    ch.timer_sel = LEDC_TIMER_0;
    ch.duty = axis == 0 ? duty(pan, PAN_US_MIN, PAN_US_MAX) : duty(tilt, TILT_US_MIN, TILT_US_MAX);
    if (ledc_channel_config(&ch) != ESP_OK) {
      ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
      ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, 0);
      return false;
    }
  }
  pwmActive = true;
  return true;
#else
  return false;
#endif
}

void ack(uint32_t id) { Serial.printf("ACK %lu\n", (unsigned long)id); }
void error(uint32_t id, const char *reason) { Serial.printf("ERR %lu %s\n", (unsigned long)id, reason); }
void stopMotion() {
  panTarget = pan; tiltTarget = tilt;
  panVelocity = tiltVelocity = 0;
  if (activeId) error(activeId, "CANCELLED");
  activeId = 0;
}

bool parseFloat(const char *text, float &result) {
  char *end;
  result = strtof(text, &end);
  return end != text && *end == '\0' && isfinite(result);
}

bool validFace(const char *value) {
  const char *names[] = {"NEUTRAL", "LISTENING", "THINKING", "TALKING", "HAPPY", "CURIOUS", "SLEEPY", "SURPRISED", "ERROR", "SAD", "ANGRY", "CONFUSED", "LAUGHING", "WINK", "BLINK", "LOVE"};
  for (auto name : names) if (!strcmp(value, name)) return true;
  return false;
}

float feedbackDegrees(int pin, int adcMin, int adcMax, float degreeMin, float degreeMax) {
  int raw = analogRead(pin);
  float ratio = float(raw - adcMin) / float(adcMax - adcMin);
  ratio = fmaxf(0.0f, fminf(1.0f, ratio));
  return degreeMin + ratio * (degreeMax - degreeMin);
}

void processLine(char *line) {
  if (!strcmp(line, "HELLO 1")) {
    stopMotion();
    Serial.println("HELLO 1 ROVO_ESP");
    lastRx = millis();
    return;
  }
  char *tokens[7], *save;
  size_t count = 0;
  for (char *t = strtok_r(line, " ", &save); t; t = strtok_r(nullptr, " ", &save)) {
    if (count >= 7) { error(0, "TOO_MANY_ARGS"); return; }
    tokens[count++] = t;
  }
  if (count < 3 || strcmp(tokens[0], "CMD")) { error(0, "SYNTAX"); return; }
  for (char *p = tokens[1]; *p; p++) if (*p < '0' || *p > '9') { error(0, "ID"); return; }
  if (strlen(tokens[1]) > 9) { error(0, "ID"); return; }
  uint32_t id = strtoul(tokens[1], nullptr, 10);
  if (!id) { error(0, "ID"); return; }
  const char *cmd = tokens[2];
  if (!strcmp(cmd, "STOP") && count == 3) { stopMotion(); ack(id); }
  else if (!strcmp(cmd, "PING") && count == 3) { ack(id); }
  else if (!strcmp(cmd, "INFO") && count == 3) {
    Serial.printf("INFO %lu CALIB %s FEEDBACK %d\n", (unsigned long)id,
                  ROVO_CALIBRATED ? ROVO_CALIBRATION_ID : "NONE",
                  ROVO_ENABLE_POSITION_FEEDBACK ? 1 : 0);
    ack(id);
  }
  else if (!strcmp(cmd, "POSITION") && count == 3) {
#if ROVO_ENABLE_POSITION_FEEDBACK && ROVO_CALIBRATED
    float measuredPan = feedbackDegrees(PAN_FEEDBACK_PIN, PAN_FEEDBACK_ADC_MIN, PAN_FEEDBACK_ADC_MAX, PAN_MIN_DEG, PAN_MAX_DEG);
    float measuredTilt = feedbackDegrees(TILT_FEEDBACK_PIN, TILT_FEEDBACK_ADC_MIN, TILT_FEEDBACK_ADC_MAX, TILT_MIN_DEG, TILT_MAX_DEG);
    Serial.printf("POS %lu %.2f %.2f\n", (unsigned long)id, measuredPan, measuredTilt);
    ack(id);
#else
    error(id, "NO_FEEDBACK"); return;
#endif
  }
  else if (!strcmp(cmd, "BRIGHTNESS") && count == 4) {
    float value;
    if (!parseFloat(tokens[3], value) || value < 0 || value > 100 || floorf(value) != value) { error(id,"BRIGHTNESS"); return; }
    brightness = uint8_t(value);
    if (!setBacklight(brightness)) { error(id,"BACKLIGHT_PWM"); return; }
    ack(id);
  }
  else if (!strcmp(cmd, "PROFILE") && count == 5) {
    float speed, accel;
    if (!parseFloat(tokens[3], speed) || !parseFloat(tokens[4], accel) ||
        speed < 2 || speed > MAX_SPEED_DEG_S || accel < 4 || accel > MAX_ACCEL_DEG_S2) {
      error(id, "PROFILE_LIMIT"); return;
    }
    runtimeSpeed = speed; runtimeAccel = accel; ack(id);
  }
  else if (!strcmp(cmd, "FACE") && count == 4 && validFace(tokens[3])) {
    face = tokens[3]; faceUntil = millis() + 8000; ack(id);
  }
  else if (!strcmp(cmd, "MOVE") && count == 5) {
#if ROVO_ENABLE_SERVOS && ROVO_CALIBRATED
    float p, t;
    if (lastMove && millis() - lastMove < 50) { error(id, "RATE_LIMIT"); return; }
    if (!parseFloat(tokens[3], p) || !parseFloat(tokens[4], t)) { error(id, "NUMBER"); return; }
    if (p < PAN_MIN_DEG || p > PAN_MAX_DEG || t < TILT_MIN_DEG || t > TILT_MAX_DEG) { error(id, "OUT_OF_RANGE"); return; }
    if (!pwmActive && (p != PAN_HOME_DEG || t != TILT_HOME_DEG)) { error(id, "HOME_REQUIRED"); return; }
    if (!pwmActive && !initPwm()) { error(id, "PWM"); return; }
    if (activeId) error(activeId, "REPLACED");
    panTarget = p; tiltTarget = t; activeId = id; ack(id);
    lastMove = millis();
#else
    error(id, "UNCALIBRATED"); return;
#endif
  } else { error(id, "UNSUPPORTED"); return; }
  lastRx = millis();
}

void readSerialNonBlocking() {
  for (int budget = 0; budget < 128 && Serial.available(); budget++) {
    char ch = Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      if (overflowed) error(0, "LINE_TOO_LONG");
      else if (lineLength) { lineBuffer[lineLength] = '\0'; processLine(lineBuffer); }
      lineLength = 0; overflowed = false;
    } else if (ch < 32 || ch > 126) { overflowed = true; }
    else if (lineLength < sizeof(lineBuffer) - 1 && !overflowed) lineBuffer[lineLength++] = ch;
    else overflowed = true;
  }
}

void interpolate(float &position, float target, float &velocity, float dt) {
  float distance = target - position;
  float wanted = copysignf(fminf(runtimeSpeed, sqrtf(2 * runtimeAccel * fabsf(distance))), distance);
  float dv = fmaxf(-runtimeAccel * dt, fminf(runtimeAccel * dt, wanted - velocity));
  velocity += dv;
  float step = velocity * dt;
  if (fabsf(distance) < .03f || (step * distance > 0 && fabsf(step) >= fabsf(distance))) {
    position = target; velocity = 0;
  } else position += step;
}

void updateServoTargets(uint32_t now) {
  if (now - lastRx > WATCHDOG_MS && activeId) stopMotion();
  if (now - lastServo < 20) return;
  float dt = fminf((now - lastServo) / 1000.0f, .04f);
  lastServo = now;
#if ROVO_ENABLE_SERVOS && ROVO_CALIBRATED
  if (!pwmActive || !activeId) return;
  interpolate(pan, panTarget, panVelocity, dt);
  interpolate(tilt, tiltTarget, tiltVelocity, dt);
  pan = fmaxf(PAN_MIN_DEG, fminf(PAN_MAX_DEG, pan));
  tilt = fmaxf(TILT_MIN_DEG, fminf(TILT_MAX_DEG, tilt));
  ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty(pan, PAN_US_MIN, PAN_US_MAX));
  ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
  ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1, duty(tilt, TILT_US_MIN, TILT_US_MAX));
  ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_1);
  if (pan == panTarget && tilt == tiltTarget) {
    Serial.printf("DONE %lu\n", (unsigned long)activeId); activeId = 0;
  }
#endif
}

void updateFaceAnimation(uint32_t now) {
  if (now - lastDraw < 50) return;
  lastDraw = now;
  if (faceUntil && int32_t(now - faceUntil) >= 0) { face = "NEUTRAL"; faceUntil = 0; }
  bool blink = (now % 4700 < 120) || face == "BLINK";
  int eyeH = blink ? 5 : face == "SLEEPY" ? 18 : face == "SURPRISED" ? 68 : 46;
  int y = 50 - eyeH / 2;
  uint16_t color = face == "ERROR" || face == "ANGRY" ? ST77XX_RED : face == "LOVE" ? ST77XX_MAGENTA : ST77XX_CYAN;
  color = dimColor(color);
  canvas.fillScreen(ST77XX_BLACK);
  for (int eye = 0; eye < 2; eye++) {
    int x = eye == 0 ? 25 : 155;
    int h = face == "WINK" && eye == 1 ? 5 : eyeH;
    canvas.fillRoundRect(x, y, 80, h, h < 10 ? 2 : 16, color);
    if (face == "HAPPY" || face == "LAUGHING") canvas.fillRoundRect(x - 2, y + eyeH / 2, 84, eyeH / 2 + 2, 12, ST77XX_BLACK);
    if (face == "ANGRY") canvas.fillTriangle(x, y, x + 80, y, eye == 0 ? x + 80 : x, y + 22, ST77XX_BLACK);
    if (face == "SAD") canvas.fillTriangle(x, y, x + 80, y, eye == 0 ? x : x + 80, y + 20, ST77XX_BLACK);
    if ((face == "CURIOUS" || face == "CONFUSED") && eye == 1) canvas.fillRect(x, y, 80, 15, ST77XX_BLACK);
    if (face == "THINKING") canvas.fillCircle(x + 40 + int(8 * sinf(now / 500.0f)), y + h / 2, 10, ST77XX_BLACK);
    if (face == "LISTENING") canvas.drawRoundRect(x - 4, y - 4, 88, h + 8, 18, dimColor(ST77XX_WHITE));
  }
  if (face == "TALKING") canvas.fillRoundRect(110, 80, 40, 4 + int(8 * fabsf(sinf(now / 120.0f))), 4, color);
  screen.drawRGBBitmap(30, 35, canvas.getBuffer(), 260, 100);
}

void setup() {
  Serial.begin(115200);
  pinMode(D4, OUTPUT);
  if (!setBacklight(100)) digitalWrite(D4, HIGH);
  SPI.begin(); // Nano-Boardprofil: SCK D13, MOSI D11; Hardware-SPI.
  screen.init(170, 320); screen.setRotation(1); screen.fillScreen(ST77XX_BLACK);
  lastRx = lastServo = millis();
  // Kein Servo-Attach, kein HOME, kein Warten auf USB.
}

void loop() {
  uint32_t now = millis();
  readSerialNonBlocking();
  updateServoTargets(now);
  updateFaceAnimation(now);
}
