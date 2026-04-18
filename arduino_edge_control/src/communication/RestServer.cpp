#include "RestServer.h"
#include "../utils/Logger.h"

RestServer::RestServer()
    : _server(HTTP_PORT), _valveCb(nullptr), _roofCb(nullptr),
      _sensorsCb(nullptr), _actuatorsCb(nullptr), _lastRequestMs(0) {}

void RestServer::begin(int port) {
    _server.begin();
    Logger::logf(LOG_INFO, "HTTP", "Serveur REST démarré sur port %d", port);
}

void RestServer::handleClients() {
    WiFiClient client = _server.available();
    if (!client) return;
    _lastRequestMs = millis();

    unsigned long t = millis();
    while (client.connected() && !client.available() && millis() - t < 2000);
    if (!client.available()) { client.stop(); return; }

    _handleRequest(client);
    client.stop();
}

void RestServer::_handleRequest(WiFiClient& client) {
    // Lecture de la première ligne : "METHOD /path HTTP/1.1"
    char method[8] = {0}, path[64] = {0};
    int contentLength = 0;

    String line = client.readStringUntil('\n');
    sscanf(line.c_str(), "%7s %63s", method, path);

    // Lire les headers pour Content-Length
    while (client.available()) {
        line = client.readStringUntil('\n');
        line.trim();
        if (line.startsWith("Content-Length:")) {
            contentLength = line.substring(15).toInt();
        }
        if (line.length() == 0) break;  // ligne vide = fin des headers
    }

    Logger::logf(LOG_DEBUG, "HTTP", "%s %s", method, path);

    // ── GET /api/sensors ─────────────────────────────────────────────────
    if (strcmp(method, "GET") == 0 && strcmp(path, "/api/sensors") == 0) {
        String out;
        if (_sensorsCb) _sensorsCb(out);
        _send200(client, out);

    // ── GET /api/actuators/status ─────────────────────────────────────────
    } else if (strcmp(method, "GET") == 0 && strcmp(path, "/api/actuators/status") == 0) {
        String out;
        if (_actuatorsCb) _actuatorsCb(out);
        _send200(client, out);

    // ── GET /api/health ───────────────────────────────────────────────────
    } else if (strcmp(method, "GET") == 0 && strcmp(path, "/api/health") == 0) {
        int rssi = WiFi.RSSI();
        int quality = constrain(2 * (rssi + 100), 0, 100);
        StaticJsonDocument<256> doc;
        doc["status"]           = "ok";
        doc["firmware_version"] = FIRMWARE_VERSION;
        doc["uptime_s"]         = millis() / 1000;
        doc["wifi_module"]      = "MKR WiFi 1010 (NINA-W102)";
        doc["wifi_ssid"]        = WiFi.SSID();
        doc["wifi_rssi"]        = rssi;
        doc["wifi_quality_pct"] = quality;
        String out; serializeJson(doc, out);
        _send200(client, out);

    // ── POST /api/actuators/valve/<zone> ─────────────────────────────────
    } else if (strcmp(method, "POST") == 0 && strncmp(path, "/api/actuators/valve/", 21) == 0) {
        int zoneId = atoi(path + 21);
        char body[HTTP_MAX_BODY] = {0};
        _parseBody(client, contentLength, body, sizeof(body));

        StaticJsonDocument<64> doc;
        if (deserializeJson(doc, body) == DeserializationError::Ok) {
            const char* state = doc["state"] | "";
            bool open = strcmp(state, "open") == 0;
            if (strcmp(state, "open") == 0 || strcmp(state, "close") == 0) {
                if (_valveCb) _valveCb(zoneId, open);
                _send200(client, "{\"ok\":true}");
            } else {
                _send400(client, "state doit etre 'open' ou 'close'");
            }
        } else {
            _send400(client, "JSON invalide");
        }

    // ── POST /api/actuators/roof ──────────────────────────────────────────
    } else if (strcmp(method, "POST") == 0 && strcmp(path, "/api/actuators/roof") == 0) {
        char body[HTTP_MAX_BODY] = {0};
        _parseBody(client, contentLength, body, sizeof(body));

        StaticJsonDocument<64> doc;
        if (deserializeJson(doc, body) == DeserializationError::Ok) {
            const char* state = doc["state"] | "";
            bool open = strcmp(state, "open") == 0;
            if (strcmp(state, "open") == 0 || strcmp(state, "close") == 0) {
                if (_roofCb) _roofCb(open);
                _send200(client, "{\"ok\":true}");
            } else {
                _send400(client, "state doit etre 'open' ou 'close'");
            }
        } else {
            _send400(client, "JSON invalide");
        }

    } else {
        _send404(client);
    }
}

void RestServer::_send200(WiFiClient& client, const String& body) {
    client.print("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: "); client.print(body.length()); client.print("\r\n");
    client.print("Connection: close\r\n\r\n");
    client.print(body);
}

void RestServer::_send400(WiFiClient& client, const char* msg) {
    String body = String("{\"ok\":false,\"error\":\"") + msg + "\"}";
    client.print("HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: "); client.print(body.length()); client.print("\r\n");
    client.print("Connection: close\r\n\r\n");
    client.print(body);
}

void RestServer::_send404(WiFiClient& client) {
    client.print("HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: 25\r\nConnection: close\r\n\r\n");
    client.print("{\"error\":\"not found\"}");
}

void RestServer::_parseBody(WiFiClient& client, int contentLength, char* buf, int bufSize) {
    if (contentLength <= 0) return;
    int toRead = min(contentLength, bufSize - 1);
    unsigned long t = millis();
    int idx = 0;
    while (idx < toRead && millis() - t < 2000) {
        if (client.available()) buf[idx++] = client.read();
    }
    buf[idx] = '\0';
}
