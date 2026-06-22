/*
 * WOP - Water Our Plants
 * Basic Arduino Sketch - Serial Communication
 * * Phase 2: Real Sensors Integrated (Moisture & Water Level)
 */

#include <Wire.h>

// ===== PIN DEFINITIONS =====
#define SOIL_MOISTURE_PIN A0
// #define PUMP_RELAY_PIN    7

// ===== WATER LEVEL SENSOR I2C ADDRESSES =====
#define ATTINY1_HIGH_ADDR 0x78
#define ATTINY2_LOW_ADDR  0x77

// ===== SETTINGS =====
const unsigned long SEND_INTERVAL = 2000; // Send data every 2 seconds
const long BAUD_RATE = 9600;

unsigned long lastSendTime = 0;
bool pumpState = false;

void setup() {
  Serial.begin(BAUD_RATE);
  Wire.begin(); // Start I2C communication for the water level sensor
  
  // Uncomment when you add the pump relay
  // pinMode(PUMP_RELAY_PIN, OUTPUT);
  // digitalWrite(PUMP_RELAY_PIN, LOW);
  
  // Wait for serial connection
  while (!Serial) { ; }
  
  // Send handshake identifier so the desktop app can confirm it's a WOP device
  Serial.println("WOP:HELLO");
  delay(100);
}

void loop() {
  // Check for incoming commands from desktop app
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    handleCommand(command);
  }

  // Send sensor data at regular intervals
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = millis();
    sendData();
  }
}

void sendData() {
  // Format: WOP:DATA:soilMoisture,waterDepth,pumpState,uptimeSeconds
  
  int soilMoisture = readSoilMoisture();
  int waterDepth = readWaterDepth();
  unsigned long uptimeSec = millis() / 1000;
  
  Serial.print("WOP:DATA:");
  Serial.print(soilMoisture);
  Serial.print(",");
  Serial.print(waterDepth);
  Serial.print(",");
  Serial.print(pumpState ? "1" : "0");
  Serial.print(",");
  Serial.println(uptimeSec);
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

void handleCommand(String cmd) {
  if (cmd == "PING") {
    Serial.println("WOP:PONG");
  }
  else if (cmd == "PUMP_ON") {
    pumpState = true;
    // digitalWrite(PUMP_RELAY_PIN, HIGH);
    Serial.println("WOP:ACK:PUMP_ON");
  }
  else if (cmd == "PUMP_OFF") {
    pumpState = false;
    // digitalWrite(PUMP_RELAY_PIN, LOW);
    Serial.println("WOP:ACK:PUMP_OFF");
  }
  else if (cmd == "STATUS") {
    sendData();
  }
  else {
    Serial.print("WOP:ERR:UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}