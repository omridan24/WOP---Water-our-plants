/*
 * HM-13 Blind Configurator (D2 Socket)
 * 
 * Blindly transmits baud-rate change commands at various speeds,
 * then checks if the module successfully changed to 9600 baud.
 */

#include <SoftwareSerial.h>

#define BLE_RX_PIN 2
#define BLE_TX_PIN 3
#define LED_PIN 13

SoftwareSerial ble(BLE_RX_PIN, BLE_TX_PIN);

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
  
  // Fast blink to indicate start
  for(int i=0; i<5; i++) {
    digitalWrite(LED_PIN, HIGH); delay(100);
    digitalWrite(LED_PIN, LOW); delay(100);
  }
  
  delay(2000);
  
  Serial.println("=================================");
  Serial.println("HM-13 Blind Configurator");
  Serial.println("=================================");
  Serial.println("Yelling baud change commands...");
  
  long rates[] = {115200, 38400, 57600, 19200, 9600};
  int numRates = 5;
  
  for (int i = 0; i < numRates; i++) {
    ble.begin(rates[i]);
    delay(200);
    
    // Command to change HM-13 to 9600 baud
    // Try with \r\n (standard HM-13)
    ble.print("AT+BAUD2\r\n");
    delay(200);
    
    // Try without \r\n (just in case it's a weird clone)
    ble.print("AT+BAUD2");
    delay(200);
    
    // Try the HM-10/11 version of the command just in case (AT+BAUD0)
    ble.print("AT+BAUD0\r\n");
    delay(200);
    ble.print("AT+BAUD0");
    delay(200);
    
    // Reset to apply
    ble.print("AT+RESET\r\n");
    delay(200);
    ble.print("AT+RESET");
    delay(200);
    
    ble.end();
  }
  
  Serial.println("Commands sent. Waiting 3 seconds for module to reboot...");
  delay(3000);
  
  // ── Now verify if it worked at 9600 baud ──
  Serial.println("Verifying at 9600 baud...");
  ble.begin(9600);
  delay(200);
  
  while (ble.available()) ble.read();
  
  // Test with \r\n
  ble.print("AT\r\n");
  String response = "";
  unsigned long start = millis();
  while (millis() - start < 1000) {
    if (ble.available()) response += (char)ble.read();
  }
  
  // Test without \r\n if first failed
  if (response.indexOf("OK") < 0) {
    ble.print("AT");
    start = millis();
    while (millis() - start < 1000) {
      if (ble.available()) response += (char)ble.read();
    }
  }
  
  if (response.indexOf("OK") >= 0) {
    Serial.println("");
    Serial.println("✅ SUCCESS! Module is now talking at 9600 baud.");
    
    // Configure transparent mode (Mode 0) and Notifications (Noti 1)
    ble.print("AT+MODE0\r\n"); delay(200); ble.print("AT+MODE0"); delay(200);
    ble.print("AT+NOTI1\r\n"); delay(200); ble.print("AT+NOTI1"); delay(200);
    
    Serial.println("Configuration complete. You can now re-upload wop_basic.ino!");
    
    // Solid LED = SUCCESS
    digitalWrite(LED_PIN, HIGH);
  } else {
    Serial.println("");
    Serial.println("❌ FAILED. No response at 9600 baud.");
    Serial.print("Raw garbage received (if any): [");
    Serial.print(response);
    Serial.println("]");
    
    // Slow blink = FAILED
    while(true) {
      digitalWrite(LED_PIN, HIGH); delay(1000);
      digitalWrite(LED_PIN, LOW); delay(1000);
    }
  }
}

void loop() {
  // Do nothing
}
