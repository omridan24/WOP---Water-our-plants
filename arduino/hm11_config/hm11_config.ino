/*
 * HM-11 AT Command Configuration Tool
 * 
 * Upload this sketch, open Serial Monitor at 9600 baud (with "No line ending"),
 * and type AT commands to configure the HM-11 module.
 * 
 * STEP-BY-STEP:
 *   1. Upload this sketch to Arduino
 *   2. Open Serial Monitor (9600 baud, "No line ending")
 *   3. Type each command below and press Enter. Wait for response.
 * 
 * COMMANDS TO SEND (in this order):
 *   AT          → Should respond "OK" (confirms communication works)
 *   AT+MODE?    → Shows current mode (should be 0 for transparent)
 *   AT+MODE0    → Set to transparent UART passthrough mode
 *   AT+ROLE?    → Shows role (should be 0 = peripheral/slave)
 *   AT+ROLE0    → Set to peripheral (if not already)
 *   AT+BAUD?    → Shows baud rate (should be 0 = 9600)
 *   AT+NOTI1    → Enable connection state notifications
 *   AT+RESET    → Reboot the module to apply changes
 * 
 * After configuration, re-upload the wop_basic.ino sketch.
 * 
 * NOTE: AT commands only work when NO BLE device is connected!
 *       Make sure your Pi is NOT running the WOP backend or debug scripts.
 */

#include <SoftwareSerial.h>

#define BLE_RX_PIN 2
#define BLE_TX_PIN 3

SoftwareSerial ble(BLE_RX_PIN, BLE_TX_PIN);

void setup() {
  Serial.begin(9600);
  ble.begin(9600);
  
  Serial.println("================================");
  Serial.println("HM-11 AT Command Tool");
  Serial.println("================================");
  Serial.println("Type AT commands in the box above.");
  Serial.println("Set line ending to 'No line ending'");
  Serial.println("(HM-11 AT commands have NO newline!)");
  Serial.println("");
  Serial.println("Try typing: AT");
  Serial.println("Expected response: OK");
  Serial.println("================================");
  Serial.println("");
}

void loop() {
  // Forward Serial Monitor → HM-11
  if (Serial.available()) {
    String cmd = Serial.readString();
    cmd.trim();
    Serial.print(">> Sending to HM-11: [");
    Serial.print(cmd);
    Serial.println("]");
    
    // HM-11 AT commands must NOT have \r\n
    ble.print(cmd);
  }
  
  // Forward HM-11 → Serial Monitor
  if (ble.available()) {
    String response = "";
    unsigned long start = millis();
    // Collect response for up to 500ms
    while (millis() - start < 500) {
      if (ble.available()) {
        char c = ble.read();
        response += c;
        start = millis(); // Reset timeout on each char
      }
    }
    Serial.print("<< HM-11 says: [");
    Serial.print(response);
    Serial.println("]");
  }
}
