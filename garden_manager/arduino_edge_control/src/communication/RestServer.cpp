#include "RestServer.h"
#include "../config.h"

RestServer::RestServer(uint16_t port) : _server(port), _startMs(0) {}

void RestServer::begin() {
    _server.begin();
    _startMs = millis();
    Serial.print("Serveur REST démarré sur port ");
    Serial.println(API_PORT);
}

void RestServer::handleClients(const SensorSnapshot& sensors, ActuatorSnapshot& actuators) {
    WiFiClient client = _server.available();
    if (!client) return;

    // Timeout lecture requête : 200ms
    unsigned long t0 = millis();
    while (!client.available() && millis() - t0 < 200) delay(1);

    if (client.available()) {
        _handleRequest(client, sensors, actuators);
    }
    client.stop();
}

void RestServer::_handleRequest(WiFiClient& client, const SensorSnapshot& sensors,
                                 ActuatorSnapshot& actuators) {
    // Lire la première ligne : "METHOD /path HTTP/1.1"
    String requestLine = client.readStringUntil('\n');
    requestLine.trim();

    // Lire les headers pour obtenir Content-Length
    int contentLength = 0;
    while (client.available()) {
        String line = client.readStringUntil('\n');
        line.trim();
        if (line.length() == 0) break;  // Fin des headers
        if (line.startsWith("Content-Length:")) {
            contentLength = line.substring(16).toInt();
        }
    }

    // Lire le corps si présent
    String body = "";
    if (contentLength > 0) {
        for (int i = 0; i < contentLength && client.available(); i++) {
            body += (char)client.read();
        }
    }

    // Parser méthode et chemin
    int sp1 = requestLine.indexOf(' ');
    int sp2 = requestLine.indexOf(' ', sp1 + 1);
    if (sp1 < 0 || sp2 < 0) { _sendError(client, 400, "Requête malformée"); return; }

    String method = requestLine.substring(0, sp1);
    String path   = requestLine.substring(sp1 + 1, sp2);

    // Router
    if (method == "GET" && path == "/api/sensors") {
        _handleSensors(client, sensors, -1);
    } else if (method == "GET" && path.startsWith("/api/sensors/")) {
        int zoneId = path.substring(13).toInt();
        _handleSensors(client, sensors, zoneId);
    } else if (method == "GET" && path == "/api/actuators/status") {
        _handleActuatorStatus(client, actuators);
    } else if (method == "POST" && path.startsWith("/api/actuators/valve/")) {
        int zoneId = path.substring(21).toInt();
        _handleSetValve(client, actuators, zoneId, body);
    } else if (method == "POST" && path == "/api/actuators/roof") {
        _handleSetRoof(client, actuators, body);
    } else if (method == "GET" && path == "/api/health") {
        _handleHealth(client);
    } else {
        _sendError(client, 404, "Endpoint non trouvé");
    }
}

void RestServer::_handleSensors(WiFiClient& client, const SensorSnapshot& s, int zoneFilter) {
    StaticJsonDocument<512> doc;
    doc["timestamp"] = millis();
    doc["temperature_c"] = s.temperature;

    if (zoneFilter > 0 && zoneFilter <= NUM_ZONES) {
        // Zone unique
        JsonObject zone = doc.createNestedObject("zone");
        int idx = zoneFilter - 1;
        zone["zone_id"] = zoneFilter;
        zone["soil_moisture_pct"] = s.moisture[idx];
        zone["raw_adc"] = (int)s.rawAdc[idx];
    } else {
        // Toutes les zones
        JsonArray zones = doc.createNestedArray("zones");
        for (int i = 0; i < NUM_ZONES; i++) {
            JsonObject zone = zones.createNestedObject();
            zone["zone_id"] = i + 1;
            zone["soil_moisture_pct"] = s.moisture[i];
            zone["raw_adc"] = (int)s.rawAdc[i];
        }
    }

    String out;
    serializeJson(doc, out);
    _sendJson(client, 200, out);
}

void RestServer::_handleActuatorStatus(WiFiClient& client, const ActuatorSnapshot& a) {
    StaticJsonDocument<256> doc;
    JsonArray valves = doc.createNestedArray("valves");
    for (int i = 0; i < NUM_ZONES; i++) {
        JsonObject v = valves.createNestedObject();
        v["zone_id"] = i + 1;
        v["state"] = a.valveOpen[i] ? "open" : "close";
    }
    doc["roof_state"] = a.roofState;
    String out;
    serializeJson(doc, out);
    _sendJson(client, 200, out);
}

void RestServer::_handleSetValve(WiFiClient& client, ActuatorSnapshot& a,
                                  int zoneId, const String& body) {
    if (zoneId < 1 || zoneId > NUM_ZONES) {
        _sendError(client, 400, "Zone invalide"); return;
    }
    StaticJsonDocument<64> req;
    if (deserializeJson(req, body) != DeserializationError::Ok) {
        _sendError(client, 400, "JSON invalide"); return;
    }
    String state = req["state"].as<String>();
    if (state != "open" && state != "close") {
        _sendError(client, 400, "state invalide"); return;
    }
    // La commande réelle est exécutée via le flag dans actuators (géré dans main.cpp)
    a.valveOpen[zoneId - 1] = (state == "open");
    StaticJsonDocument<64> resp;
    resp["ok"] = true;
    resp["zone_id"] = zoneId;
    resp["state"] = state;
    String out;
    serializeJson(resp, out);
    _sendJson(client, 200, out);
}

void RestServer::_handleSetRoof(WiFiClient& client, ActuatorSnapshot& a, const String& body) {
    StaticJsonDocument<64> req;
    if (deserializeJson(req, body) != DeserializationError::Ok) {
        _sendError(client, 400, "JSON invalide"); return;
    }
    String state = req["state"].as<String>();
    if (state != "open" && state != "close") {
        _sendError(client, 400, "state invalide"); return;
    }
    a.roofState = (state == "open") ? "open" : "close";
    StaticJsonDocument<64> resp;
    resp["ok"] = true;
    resp["roof_state"] = state;
    String out;
    serializeJson(resp, out);
    _sendJson(client, 200, out);
}

void RestServer::_handleHealth(WiFiClient& client) {
    StaticJsonDocument<128> doc;
    doc["status"] = "ok";
    doc["uptime_s"] = (millis() - _startMs) / 1000;
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["firmware_version"] = FIRMWARE_VERSION;
    doc["simulated"] = false;
    String out;
    serializeJson(doc, out);
    _sendJson(client, 200, out);
}

void RestServer::_sendJson(WiFiClient& client, int status, const String& body) {
    client.print("HTTP/1.1 ");
    client.print(status);
    client.println(status == 200 ? " OK" : " Error");
    client.println("Content-Type: application/json");
    client.println("Access-Control-Allow-Origin: *");
    client.print("Content-Length: ");
    client.println(body.length());
    client.println("Connection: close");
    client.println();
    client.print(body);
}

void RestServer::_sendError(WiFiClient& client, int status, const char* msg) {
    String body = "{\"error\":\"";
    body += msg;
    body += "\"}";
    _sendJson(client, status, body);
}
