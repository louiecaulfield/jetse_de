#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(8, 7); // CE, CSN
const byte address[6] = "00009";

#include <packet.h>
packet_t packet = {};

void setup() {
  Serial.begin(115200);
  while(!Serial)
    delay(10);
  Serial.println("RF24 receiver");

  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  // radio.setDataRate(RF24_250KBPS);
  // radio.setRetries(3,5);
  radio.openReadingPipe(1, address);
  radio.printDetails();
}

char rf24_msg[100] = "";

void loop() {
  radio.startListening();
  if (radio.available()) {
    radio.read(&packet, sizeof(packet));
    sprintf(rf24_msg, "Accelero %05.2f / %05.2f / %05.2f (%d) - KNOCK %d @ %lu ms",
                      packet.x, packet.y, packet.z,
                      packet.motion,
                      packet.knock,
                      packet.last_knock_time);
    Serial.println(rf24_msg);
  }
}