#include "Logger.h"
#include "../config.h"
#include <WiFiNINA.h>
#include <ArduinoJson.h>

LogLevel Logger::minLevel = LOG_DEBUG;
char     Logger::_buffer[20][160];
int      Logger::_head  = 0;
int      Logger::_count = 0;

void Logger::begin(unsigned long baud) {
    Serial.begin(baud);
    while (!Serial && millis() < 3000);
}

const char* Logger::levelStr(LogLevel l) {
    switch (l) {
        case LOG_DEBUG:   return "DEBUG";
        case LOG_INFO:    return "INFO";
        case LOG_WARNING: return "WARNING";
        case LOG_ERROR:   return "ERROR";
        default:          return "INFO";
    }
}

void Logger::log(LogLevel level, const char* tag, const char* msg) {
    if (level < minLevel) return;

    char line[160];
    snprintf(line, sizeof(line), "[%s][%s] %s", levelStr(level), tag, msg);
    Serial.println(line);

    // Mise en buffer circulaire pour envoi ultérieur au RPi
    if (_count < BUFFER_SIZE) _count++;
    strncpy(_buffer[_head], line, 159);
    _buffer[_head][159] = '\0';
    _head = (_head + 1) % BUFFER_SIZE;
}

void Logger::logf(LogLevel level, const char* tag, const char* fmt, ...) {
    char msg[128];
    va_list args;
    va_start(args, fmt);
    vsnprintf(msg, sizeof(msg), fmt, args);
    va_end(args);
    log(level, tag, msg);
}

void Logger::flushToRpi() {
    if (_count == 0) return;
    if (WiFi.status() != WL_CONNECTED) return;

    WiFiClient client;
    if (!client.connect(RPI_HOST, RPI_PORT)) return;

    // Calcule l'index de départ (buffer circulaire)
    int start = (_head - _count + BUFFER_SIZE) % BUFFER_SIZE;

    StaticJsonDocument<1024> doc;
    JsonArray arr = doc.createNestedArray("logs");
    for (int i = 0; i < _count; i++) {
        int idx = (start + i) % BUFFER_SIZE;
        arr.add(_buffer[idx]);
    }
    String body;
    serializeJson(doc, body);

    client.println("POST " RPI_LOG_PATH " HTTP/1.1");
    client.print("Host: "); client.println(RPI_HOST);
    client.println("Content-Type: application/json");
    client.print("Content-Length: "); client.println(body.length());
    client.println("Connection: close");
    client.println();
    client.print(body);

    // Attente réponse (non bloquante, timeout 2s)
    unsigned long t = millis();
    while (client.available() == 0 && millis() - t < 2000);
    client.stop();

    _count = 0;  // vider le buffer après envoi
}
