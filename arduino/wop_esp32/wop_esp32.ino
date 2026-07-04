/*
 * WOP - Water Our Plants | ESP32 WiFi Bridge
 *
 * This ESP32 acts as a WiFi adapter for the Arduino Uno.
 * It does NOT read sensors or control the pump directly.
 * It simply bridges the Arduino's serial data to the Raspberry Pi over WiFi.
 *
 * Data flow:
 *   Arduino → [Serial UART @ 9600] → ESP32 → [WiFi HTTP POST] → Raspberry Pi
 *   Raspberry Pi → [HTTP Response] → ESP32 → [Serial UART] → Arduino
 *
 * WIRING (4 jumper wires):
 *   Arduino Shield pin 2  → ESP32 GPIO 17 (TX2)  [ESP32 sends TO Arduino]
 *   Arduino Shield pin 3  → ESP32 GPIO 16 (RX2)  [ESP32 receives FROM Arduino]
 *   Arduino Shield GND    → ESP32 GND             [Shared ground]
 *   Arduino Shield 5V     → ESP32 5V pin          [Power - DISCONNECT when USB flashing!]
 *
 * POWER WARNING:
 *   When uploading code via USB, DISCONNECT the 5V wire from the Arduino first!
 *   Having two 5V sources (USB + Arduino) at the same time can damage your computer's USB port.
 *   After uploading, unplug USB and reconnect the 5V wire.
 *
 * DEPENDENCIES:
 *   - ArduinoJson by Benoit Blanchon (v6.x or 7.x)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"  // WiFi credentials — gitignored, see config.h.example

// ==========================================
// UART2 — Communication with Arduino
// ==========================================
#define ARDUINO_RX_PIN 16  // ESP32 receives data FROM Arduino on this pin
#define ARDUINO_TX_PIN 17  // ESP32 sends data TO Arduino on this pin
#define ARDUINO_BAUD   9600

// ==========================================
// State
// ==========================================
String serialBuffer = "";
unsigned long lastWifiCheck = 0;
const unsigned long WIFI_CHECK_INTERVAL = 30000; // 30 seconds
String macAddress = "";

void setup() {
  // USB Serial — for debugging when connected to computer
  Serial.begin(115200);

  // UART2 — for talking to the Arduino
  Serial2.begin(ARDUINO_BAUD, SERIAL_8N1, ARDUINO_RX_PIN, ARDUINO_TX_PIN);

  delay(1000);

  Serial.println("\n\n================================");
  Serial.println("🌱 WOP - ESP32 WiFi Bridge");
  Serial.println("================================");
  Serial.println("Role: Serial ↔ WiFi bridge");
  Serial.println("Arduino UART: GPIO16 (RX) / GPIO17 (TX)");
  macAddress = WiFi.macAddress();
  Serial.printf("Device ID (MAC): %s\n", macAddress.c_str());
  Serial.printf("Backend: http://%s:%d\n", BACKEND_IP, BACKEND_PORT);
  Serial.println("================================\n");

  connectWiFi();
}

void loop() {
  // Periodically check WiFi is still connected
  if (millis() - lastWifiCheck > WIFI_CHECK_INTERVAL) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("⚠️ WiFi lost. Reconnecting...");
      connectWiFi();
    }
  }

  // Read incoming bytes from the Arduino (arrives on UART2)
  while (Serial2.available()) {
    char c = Serial2.read();
    if (c == '\n' || c == '\r') {
      serialBuffer.trim();
      if (serialBuffer.length() > 0) {
        handleArduinoMessage(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += c;
      // Safety: prevent buffer overflow from garbage data
      if (serialBuffer.length() > 128) {
        serialBuffer = "";
      }
    }
  }
}

// ==========================================
// WiFi
// ==========================================

void connectWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 40) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n❌ WiFi failed. Will retry in 30 seconds...");
  }
}

// ==========================================
// Arduino Message Handler
// ==========================================

void handleArduinoMessage(String msg) {
  // Log everything we receive from the Arduino
  Serial.print("📥 From Arduino: ");
  Serial.println(msg);

  if (msg.startsWith("WOP:DATA:")) {
    // Sensor data — parse and forward to backend
    // Format: WOP:DATA:soilMoisture,waterDepth,pumpState,uptimeSeconds
    String data = msg.substring(9);  // Remove "WOP:DATA:" prefix

    int c1 = data.indexOf(',');
    int c2 = data.indexOf(',', c1 + 1);
    int c3 = data.indexOf(',', c2 + 1);

    if (c1 < 0 || c2 < 0 || c3 < 0) {
      Serial.println("   ❌ Bad data format — expected 4 comma-separated values");
      return;
    }

    int soilMoisture   = data.substring(0, c1).toInt();
    int waterDepth     = data.substring(c1 + 1, c2).toInt();
    int pumpActive     = data.substring(c2 + 1, c3).toInt();
    unsigned long uptime = strtoul(data.substring(c3 + 1).c_str(), NULL, 10);

    Serial.printf("   📊 Soil=%d, Depth=%dmm, Pump=%s, Uptime=%lus\n",
                  soilMoisture, waterDepth, pumpActive ? "ON" : "OFF", uptime);

    postToBackend(soilMoisture, waterDepth, pumpActive, uptime);
  }
  else if (msg.startsWith("WOP:HELLO")) {
    Serial.println("   👋 Arduino says hello — bridge is working!");
  }
  else if (msg.startsWith("WOP:ACK:")) {
    Serial.printf("   ✅ Arduino acknowledged command: %s\n", msg.substring(8).c_str());
  }
  else if (msg.startsWith("WOP:PONG")) {
    Serial.println("   🏓 Arduino responded to PING");
  }
  else if (msg.startsWith("WOP:ERR:")) {
    Serial.printf("   ⚠️ Arduino error: %s\n", msg.substring(8).c_str());
  }
  else {
    Serial.printf("   ❓ Unknown message: %s\n", msg.c_str());
  }
}

// ==========================================
// Backend Communication
// ==========================================

void postToBackend(int soil, int depth, int pump, unsigned long uptime) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("   ❌ No WiFi — skipping POST");
    return;
  }

  // Build the URL: POST /api/devices/{mac_address}/readings
  String url = String("http://") + BACKEND_IP + ":" + String(BACKEND_PORT)
               + "/api/devices/" + macAddress + "/readings";

  // Build JSON payload
  StaticJsonDocument<200> doc;
  doc["soil_moisture"]   = soil;
  doc["water_depth"]     = depth;
  doc["pump_active"]     = (pump == 1);
  doc["uptime_seconds"]  = uptime;

  String body;
  serializeJson(doc, body);

  // Send HTTP POST
  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000);  // 5 second timeout

  int responseCode = http.POST(body);

  if (responseCode > 0) {
    String response = http.getString();

    // Parse response for any pending commands from the backend
    StaticJsonDocument<512> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, response);

    if (!error && responseDoc.containsKey("commands")) {
      JsonArray commands = responseDoc["commands"].as<JsonArray>();
      for (JsonVariant v : commands) {
        String cmd = v.as<String>();
        Serial.printf("   📤 Forwarding command to Arduino: %s\n", cmd.c_str());
        Serial2.println(cmd);  // Send command to Arduino over UART
      }
    }

    // Only log non-200 responses to keep the output clean
    if (responseCode != 200) {
      Serial.printf("   🌐 HTTP %d: %s\n", responseCode, response.c_str());
    }
  } else {
    Serial.printf("   ❌ HTTP POST failed (code %d)\n", responseCode);
  }

  http.end();
}
