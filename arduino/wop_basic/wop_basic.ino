/*
 * WOP - Water Our Plants
 * Arduino Sketch - USB Serial + BLE Wireless
 * Phase 3: Grove BLE (HM-11) wireless link added
 *
 * USB Serial  = debug monitor (always available via cable)
 * SoftwareSerial = Grove BLE module on D2/D3 (wireless to desktop app)
 */

#include <Wire.h>
#include <SoftwareSerial.h>

// ===== PIN DEFINITIONS =====
#define SOIL_MOISTURE_PIN A0
#define PUMP_PIN 9

// ===== BLE MODULE PINS (Grove UART socket) =====
#define BLE_RX_PIN 2   // Arduino D2 ← BLE TX
#define BLE_TX_PIN 3   // Arduino D3 → BLE RX

// ===== WATER LEVEL SENSOR I2C ADDRESSES =====
#define ATTINY1_HIGH_ADDR 0x78
#define ATTINY2_LOW_ADDR  0x77

// ===== SETTINGS =====
const unsigned long SEND_INTERVAL = 2000; // Send data every 2 seconds
const long BAUD_RATE = 9600;

// ===== BLE SERIAL =====
SoftwareSerial ble(BLE_RX_PIN, BLE_TX_PIN); // RX, TX

unsigned long lastSendTime = 0;
bool pumpState = false;

// Buffer for BLE incoming data (commands may arrive in small BLE packets)
String bleCommandBuffer = "";

void setup() {
  Serial.begin(BAUD_RATE);
  ble.begin(BAUD_RATE);
  Wire.begin(); // Start I2C communication for the water level sensor
  
  pinMode(PUMP_PIN, OUTPUT);
  digitalWrite(PUMP_PIN, LOW);
  
  // Wait for USB serial connection (only blocks when USB is connected)
  // Timeout after 2 seconds so the Arduino works without USB too
  unsigned long serialWaitStart = millis();
  while (!Serial && (millis() - serialWaitStart < 2000)) { ; }
  
  // Send handshake on BOTH channels
  Serial.println("WOP:HELLO");
  ble.println("WOP:HELLO");
  delay(100);
}

void loop() {
  // --- Check USB Serial for commands ---
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    handleCommand(command, false);
  }

  // --- Check BLE for commands ---
  // BLE data may arrive in small chunks (max ~20 bytes per BLE packet),
  // so we buffer until we get a newline.
  while (ble.available()) {
    char c = ble.read();
    if (c == '\n' || c == '\r') {
      bleCommandBuffer.trim();
      if (bleCommandBuffer.length() > 0) {
        handleCommand(bleCommandBuffer, true);
        bleCommandBuffer = "";
      }
    } else {
      bleCommandBuffer += c;
      // Safety: prevent buffer overflow from garbage data
      if (bleCommandBuffer.length() > 64) {
        bleCommandBuffer = "";
      }
    }
  }

  // Send sensor data at regular intervals
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = millis();
    sendData();
  }
}

// Helper: print a line to both USB Serial and BLE
void sendLine(const String &line) {
  Serial.println(line);
  ble.println(line);
}

void sendData() {
  // Format: WOP:DATA:soilMoisture,waterDepth,pumpState,uptimeSeconds
  
  int soilMoisture = readSoilMoisture();
  int waterDepth = readWaterDepth();
  unsigned long uptimeSec = millis() / 1000;
  
  String msg = "WOP:DATA:";
  msg += soilMoisture;
  msg += ",";
  msg += waterDepth;
  msg += ",";
  msg += (pumpState ? "1" : "0");
  msg += ",";
  msg += uptimeSec;
  
  sendLine(msg);
}

int readSoilMoisture() {
  // Grove Moisture Sensor connected to A0
  // Returns raw analog value (0-1023)
  // ~0-300 = Dry | ~300-700 = Moist | ~700+ = In water
  return analogRead(SOIL_MOISTURE_PIN);
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

  // The sensor has 20 capacitive pads total, each representing roughly 5mm of water.
  // Multiplying the touched pads by 5 gives us the water depth in millimeters (0 to 100 mm).
  return touchedPads * 5; 
}

void handleCommand(String cmd, bool fromBLE) {
  // Log which channel the command came from (debug)
  Serial.print("[CMD ");
  Serial.print(fromBLE ? "BLE" : "USB");
  Serial.print("] '");
  Serial.print(cmd);
  Serial.println("'");

  String response = "";
  
  if (cmd.indexOf("PING") >= 0) {
    response = "WOP:PONG";
  }
  else if (cmd.indexOf("PUMP_ON") >= 0) {
    pumpState = true;
    digitalWrite(PUMP_PIN, HIGH);
    response = "WOP:ACK:PUMP_ON";
  }
  else if (cmd.indexOf("PUMP_OFF") >= 0) {
    pumpState = false;
    digitalWrite(PUMP_PIN, LOW);
    response = "WOP:ACK:PUMP_OFF";
  }
  else if (cmd.indexOf("STATUS") >= 0) {
    sendData();
    return; // sendData already sends on both channels
  }
  else {
    response = "WOP:ERR:UNKNOWN_CMD:" + cmd;
  }

  // Send response back on the channel it came from
  if (fromBLE) {
    ble.println(response);
  } else {
    Serial.println(response);
  }
}