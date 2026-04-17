#pragma once
#include <Arduino.h>

// Logging série conditionnel (compilé uniquement si DEBUG_SERIAL défini)
#ifdef DEBUG_SERIAL
  #define LOG(msg)        Serial.println(msg)
  #define LOGF(fmt, ...)  do { char buf[128]; snprintf(buf, sizeof(buf), fmt, __VA_ARGS__); Serial.println(buf); } while(0)
#else
  #define LOG(msg)        do {} while(0)
  #define LOGF(fmt, ...)  do {} while(0)
#endif
