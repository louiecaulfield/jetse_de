#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(8, 7); // CE, CSN

#include <packet.h>
packet_t packet = {};

void setup() {
  Serial.begin(115200);
  while(!Serial)
    delay(10);

  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  radio.setDataRate(RF24_2MBPS);
  radio.openReadingPipe(1, address_for(9));
  radio.startListening();
}

uint8_t checksum;
void loop() {
  if (radio.available()) {
    radio.read(&packet, sizeof(packet));
    /* 0xBAE1 = Baetelaan magic */
    Serial.write((uint8_t)0xBA);
    Serial.write((uint8_t)0xE1);

    /* Send the packet data */
    Serial.write((uint8_t *)&packet, sizeof(packet));

    /* Simple checksum */
    checksum = 0;
    for(int i=0; i < sizeof(packet); i++) {
      checksum += ((uint8_t *)&packet)[i];
    }
    Serial.write(checksum);
  }
}