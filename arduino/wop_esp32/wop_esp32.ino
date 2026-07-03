/*
 * WOP - Water Our Plants | ESP32 Wi-Fi Version
 *
 * Replaces the Arduino Uno + BLE setup with a single ESP32 connected to Wi-Fi.
 * Pushes data directly to the Raspberry Pi backend and pulls pending commands.
 *
 * DEPENDENCIES (Install via Sketch -> Include Library -> Manage Libraries):
 *   - ArduinoJson by Benoit Blanchon (Version 7.x or 6.x)
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <ArduinoJson.h>

// ==========================================
// CONFIGURATION - CHANGE THESE!
// ==========================================
const char* WIFI_SSID = "YOUR_WIFI_NETWORK_NAME";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// The IP address of your Raspberry Pi (e.g., "192.168.1.100")
const char* BACKEND_IP = "YOUR_PI_IP_ADDRESS";
const int BACKEND_PORT = 8080;

// The Plant ID that this ESP32 is monitoring
const int PLANT_ID = 1; 

// ==========================================
// PINS (ESP32 WROOM-32)
// ==========================================
#define SOIL_MOISTURE_PIN 34  // ADC1
#define PUMP_PIN 25           // Digital Out
// Water Level Sensor uses default I2C pins: GPIO 21 (SDA), GPIO 22 (SCL)

// Water Level Sensor I2C Addresses
#define ATTINY1_HIGH_ADDR 0x78
#define ATTINY2_LOW_ADDR  0x77

// Timing
const unsigned long SEND_INTERVAL = 2000; // Post data every 2 seconds
unsigned long lastSendTime = 0;

bool pumpState = false;

// Construct the full API URL
String getApiUrl() {
  return "http://" + String(BACKEND_IP) + ":" + String(BACKEND_PORT) + "/api/plants/" + String(PLANT_ID) + "/readings";
}

void setup() {
  Serial.begin(115200);
  Wire.begin(); // Start I2C for water level sensor
  
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
  
  // Need to wait briefly for serial monitor to catch up
  delay(1000);
  
  Serial.println("\n\n================================");
  Serial.println("🌱 WOP - ESP32 Wi-Fi Starting...");
  Serial.println("================================");
  
  // Connect to Wi-Fi
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ Wi-Fi Connected!");
  Serial.print("IP Address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Backend URL: ");
  Serial.println(getApiUrl());
  Serial.println("================================\n");
}

void loop() {
  // Reconnect Wi-Fi if dropped
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Reconnecting...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("\n✅ Wi-Fi Reconnected!");
  }

  // Time to send data?
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = millis();
    sendTelemetryAndFetchCommands();
  }
}

void sendTelemetryAndFetchCommands() {
  if (WiFi.status() != WL_CONNECTED) return;
  
  int moisture = readSoilMoisture();
  int waterDepth = readWaterDepth();
  int uptimeSec = millis() / 1000;
  
  Serial.printf("📊 Data: Moisture=%d, Depth=%d, Pump=%s, Uptime=%ds\n", 
                moisture, waterDepth, pumpState ? "ON" : "OFF", uptimeSec);
  
  // 1. Build JSON Payload
  StaticJsonDocument<200> doc;
  doc["soil_moisture"] = moisture;
  doc["water_depth"] = waterDepth;
  doc["pump_active"] = pumpState;
  doc["uptime_seconds"] = uptimeSec;
  
  String requestBody;
  serializeJson(doc, requestBody);
  
  // 2. Send HTTP POST Request
  HTTPClient http;
  http.begin(getApiUrl());
  http.addHeader("Content-Type", "application/json");
  
  int httpResponseCode = http.POST(requestBody);
  
  if (httpResponseCode > 0) {
    String responseBody = http.getString();
    // Only log if not a standard 200 OK (to keep terminal clean), or if commands exist
    if (httpResponseCode != 200 || responseBody.indexOf("PUMP") > 0 || responseBody.indexOf("PING") > 0) {
      Serial.printf("🌐 HTTP %d: %s\n", httpResponseCode, responseBody.c_str());
    }
    
    // 3. Parse Response for Commands
    StaticJsonDocument<512> responseDoc;
    DeserializationError error = deserializeJson(responseDoc, responseBody);
    
    if (!error && responseDoc.containsKey("commands")) {
      JsonArray commands = responseDoc["commands"].as<JsonArray>();
      for (JsonVariant v : commands) {
        String cmd = v.as<String>();
        executeCommand(cmd);
      }
    }
  } else {
    Serial.printf("❌ HTTP POST failed. Error code: %d\n", httpResponseCode);
  }
  
  http.end();
}

void executeCommand(String cmd) {
  Serial.print("⚡ Executing Command: ");
  Serial.println(cmd);
  
  if (cmd == "PUMP_ON") {
    pumpState = true;
    digitalWrite(PUMP_PIN, HIGH);
  } 
  else if (cmd == "PUMP_OFF") {
    pumpState = false;
    digitalWrite(PUMP_PIN, LOW);
  }
  else if (cmd == "PING") {
    Serial.println("   (Ping acknowledged)");
  }
}

// ==========================================
// SENSOR READING FUNCTIONS
// ==========================================

int readSoilMoisture() {
  // ESP32 ADC is 12-bit (0-4095) unlike Arduino's 10-bit (0-1023).
  // We map it down to 0-1023 so the backend doesn't need to change!
  int raw = analogRead(SOIL_MOISTURE_PIN);
  return map(raw, 0, 4095, 0, 1023);
}

int readWaterDepth() {
  // Grove Water Level Sensor 10cm (I2C)
  int touchedPads = 0;
  byte val;

  // Read the 12 high-level sections (address 0x78)
  Wire.beginTransmission(ATTINY1_HIGH_ADDR);
  Wire.write(0x01); 
  Wire.endTransmission();
  Wire.requestFrom(ATTINY1_HIGH_ADDR, 12);
  while (Wire.available()) {
    val = Wire.read();
    if (val > 100) { touchedPads++; }
  }

  // Read the 8 low-level sections (address 0x77)
  Wire.beginTransmission(ATTINY2_LOW_ADDR);
  Wire.write(0x01);
  Wire.endTransmission();
  Wire.requestFrom(ATTINY2_LOW_ADDR, 8);
  while (Wire.available()) {
    val = Wire.read();
    if (val > 100) { touchedPads++; }
  }

  return touchedPads * 5; 
}
