/*
 * WOP - Water Our Plants
 * Basic Arduino Sketch - Serial Communication
 * 
 * Phase 1: USB Serial - sends basic stats
 * Phase 2: Add real sensors (soil moisture, water depth)
 * Phase 3: Bluetooth (HC-05/HM-10) communication
 * Phase 4: Water pump control
 */

// ===== PIN DEFINITIONS (uncomment when you wire sensors) =====
// #define SOIL_MOISTURE_PIN A0
// #define WATER_DEPTH_PIN   A1
// #define PUMP_RELAY_PIN    7

// ===== SETTINGS =====
const unsigned long SEND_INTERVAL = 2000; // Send data every 2 seconds
const long BAUD_RATE = 9600;

unsigned long lastSendTime = 0;
bool pumpState = false;

void setup() {
  Serial.begin(BAUD_RATE);
  
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
  // TODO: Replace with real sensor reading
  // return analogRead(SOIL_MOISTURE_PIN);
  
  // Simulated value (0-1023) - fluctuates around 500
  return 450 + random(0, 100);
}

int readWaterDepth() {
  // TODO: Replace with real sensor reading
  // return analogRead(WATER_DEPTH_PIN);
  
  // Simulated value (0-1023) - fluctuates around 700
  return 650 + random(0, 100);
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
