#include "RestServer.h"
#include "../utils/Logger.h"

RestServer::RestServer()
    : _server(HTTP_PORT), _valveCb(nullptr), _roofCb(nullptr),
      _sensorsCb(nullptr), _actuatorsCb(nullptr), _lastRequestMs(0) {}

void RestServer::begin(int port) {
    _server.begin();
    Logger::logf(LOG_INFO, "HTTP", "Serveur REST démarré sur port %d", port);
}

// ── Lecture sécurisée d'une ligne HTTP ────────────────────────────────────
// C1 : limite stricte à maxLen octets (protège la SRAM contre les lignes infinies)
// C2 : delay(1) dans la boucle d'attente (plus de busy-wait CPU à 100%)
// M2 : timeout réinitialisé à chaque octet reçu (évite la troncature sur liaison lente)
static int _readLineSafe(WiFiClient& client, char* buf, int maxLen, int timeoutMs = 2000) {
    int  idx = 0;
    unsigned long t = millis();
    while (client.connected() && millis() - t < timeoutMs) {
        if (client.available()) {
            char c = client.read();
            t = millis();           // M2 : reset timeout par octet reçu
            if (c == '\n') break;
            if (c != '\r' && idx < maxLen - 1) {
                buf[idx++] = c;
            }
        } else {
            delay(1);               // C2 : évite le busy-wait
        }
    }
    buf[idx] = '\0';
    return idx;
}

void RestServer::handleClients() {
    WiFiClient client = _server.available();
    if (!client) return;
    _lastRequestMs = millis();

    // C2 : attente initiale avec delay(1) — plus de busy-wait
    unsigned long t = millis();
    while (client.connected() && !client.available() && millis() - t < 2000) delay(1);
    if (!client.available()) { client.stop(); return; }

    _handleRequest(client);
    client.stop();
}

void RestServer::_handleRequest(WiFiClient& client) {
    // C1 : buffers statiques de taille bornée — plus de String dynamique
    char lineBuf[256] = {0};
    char method[8]    = {0};
    char path[64]     = {0};
    int  contentLength = 0;

    // Lecture première ligne : "METHOD /path HTTP/1.1"
    _readLineSafe(client, lineBuf, sizeof(lineBuf));
    sscanf(lineBuf, "%7s %63s", method, path);

    // M3 : lecture des headers avec timeout par ligne (_readLineSafe)
    while (client.connected()) {
        _readLineSafe(client, lineBuf, sizeof(lineBuf));
        if (lineBuf[0] == '\0') break;   // ligne vide = fin des headers
        if (strncmp(lineBuf, "Content-Length:", 15) == 0) {
            contentLength = atoi(lineBuf + 15);
        }
    }

    Logger::logf(LOG_DEBUG, "HTTP", "%s %s", method, path);

    // ── GET /api/sensors ─────────────────────────────────────────────────
    if (strcmp(method, "GET") == 0 && strcmp(path, "/api/sensors") == 0) {
        String out;
        if (_sensorsCb) _sensorsCb(out);
        _send200(client, out.c_str());

    // ── GET /api/actuators/status ─────────────────────────────────────────
    } else if (strcmp(method, "GET") == 0 && strcmp(path, "/api/actuators/status") == 0) {
        String out;
        if (_actuatorsCb) _actuatorsCb(out);
        _send200(client, out.c_str());

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
        char out[256]; serializeJson(doc, out, sizeof(out));
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

void RestServer::_send200(WiFiClient& client, const char* body) {
    client.print("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: "); client.print(strlen(body)); client.print("\r\n");
    client.print("Connection: close\r\n\r\n");
    client.print(body);
}

// M1 : snprintf sur buffer statique — plus de String()+String() qui fragmente le heap
void RestServer::_send400(WiFiClient& client, const char* msg) {
    char body[160];
    snprintf(body, sizeof(body), "{\"ok\":false,\"error\":\"%s\"}", msg);
    client.print("HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: "); client.print(strlen(body)); client.print("\r\n");
    client.print("Connection: close\r\n\r\n");
    client.print(body);
}

void RestServer::_send404(WiFiClient& client) {
    client.print("HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\n");
    client.print("Content-Length: 20\r\nConnection: close\r\n\r\n");
    client.print("{\"error\":\"not found\"}");
}

// M2 : timeout réinitialisé par octet reçu — évite la troncature sur liaison lente
void RestServer::_parseBody(WiFiClient& client, int contentLength, char* buf, int bufSize) {
    if (contentLength <= 0) return;
    int toRead = min(contentLength, bufSize - 1);
    unsigned long t = millis();
    int idx = 0;
    while (idx < toRead && millis() - t < 5000) {
        if (client.available()) {
            buf[idx++] = client.read();
            t = millis();   // reset timeout par octet
        } else {
            delay(1);
        }
    }
    buf[idx] = '\0';
}
