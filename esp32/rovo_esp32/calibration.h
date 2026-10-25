#pragma once

// AUSLIEFERUNGSZUSTAND: kein Servo-PWM. Erst nach mechanischer Prüfung bearbeiten.
// Keine historischen Winkel oder Pulsweiten als Kalibrierung übernehmen.
#define ROVO_ENABLE_SERVOS 0
#define ROVO_CALIBRATED 0
#define ROVO_CALIBRATION_ID "UNCONFIGURED"
// Nur mit tatsächlich angeschlossenen, getrennt kalibrierten Positionssensoren aktivieren.
#define ROVO_ENABLE_POSITION_FEEDBACK 0
#define PAN_FEEDBACK_PIN A0
#define TILT_FEEDBACK_PIN A1
#define PAN_FEEDBACK_ADC_MIN 0
#define PAN_FEEDBACK_ADC_MAX 4095
#define TILT_FEEDBACK_ADC_MIN 0
#define TILT_FEEDBACK_ADC_MAX 4095
#define PAN_MIN_DEG 0.0f
#define PAN_MAX_DEG 0.0f
#define PAN_HOME_DEG 0.0f
#define TILT_MIN_DEG 0.0f
#define TILT_MAX_DEG 0.0f
#define TILT_HOME_DEG 0.0f
#define PAN_US_MIN 0
#define PAN_US_MAX 0
#define TILT_US_MIN 0
#define TILT_US_MAX 0
#define MAX_SPEED_DEG_S 20.0f
#define MAX_ACCEL_DEG_S2 40.0f
