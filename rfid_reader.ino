/**
 * Smart Gym CP02 — Firmware Arduino/ESP32
 * Lê o UID do cartão RFID (RC522) e envia via Serial.
 *
 * Biblioteca necessária: MFRC522
 * Instale pela Arduino IDE: Sketch → Include Library → Manage Libraries → "MFRC522"
 *
 * Conexões ESP32 + RC522:
 *   RC522 SDA  → GPIO 5  (SS_PIN)
 *   RC522 SCK  → GPIO 18
 *   RC522 MOSI → GPIO 23
 *   RC522 MISO → GPIO 19
 *   RC522 RST  → GPIO 22 (RST_PIN)
 *   RC522 3.3V → 3.3V
 *   RC522 GND  → GND
 */

#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN  5    // GPIO 5  (ESP32) — Arduino Uno: pino 10
#define RST_PIN 22   // GPIO 22 (ESP32) — Arduino Uno: pino 9

MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("SMART_GYM_READY");
}

void loop() {
  // Aguarda um novo cartão
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial())   return;

  // Monta string do UID em hexadecimal maiúsculo (ex: "A1B2C3D4")
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();

  Serial.println(uid);  // Envia para o Python via Serial

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();

  delay(1500);  // Debounce — evita leituras duplicadas
}
