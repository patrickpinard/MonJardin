#pragma once
#include <Arduino.h>

enum LogLevel { LOG_DEBUG = 0, LOG_INFO, LOG_WARNING, LOG_ERROR };

class Logger {
public:
    static void begin(unsigned long baud = 115200);
    static void log(LogLevel level, const char* tag, const char* msg);
    static void logf(LogLevel level, const char* tag, const char* fmt, ...);

    // Envoie le log au RPi via HTTP POST (appelé depuis la loop si WiFi dispo)
    static void flushToRpi();

    static LogLevel minLevel;

private:
    static const int  BUFFER_SIZE = 20;
    static char       _buffer[20][160];
    static int        _head;
    static int        _count;
    static const char* levelStr(LogLevel l);
};
