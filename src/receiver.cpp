#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(8, 7); // CE, CSN

#include <packet.h>
packet_t packet = {};
#define PIPES 6
packet_conf_t config[PIPES] = {
  {.id=0, .threshold=50},
  {.id=1, .threshold=50},
  {.id=2, .threshold=50},
  {.id=3, .threshold=50},
  {.id=9, .threshold=50},
  {.id=5, .threshold=50},
};
bool config_update[PIPES];

#define SERIAL_DEBUG 1

void setup() {
  Serial.begin(115200);
  while(!Serial)
    delay(10);

  radio.begin();
  radio.setPALevel(RF24_PA_LOW);
  radio.enableDynamicPayloads();
  radio.enableAckPayload();
  radio.setDataRate(RF24_2MBPS);

  for(uint8_t i = 0; i < PIPES; i++) {
    radio.openReadingPipe(i, address_for(config[i].id));
    config_update[i] = true;
  }

  radio.startListening();
}

void serial_transmit(uint8_t * buf, int len) {
    uint8_t checksum;
    /* 0xBAE1 = Baetelaan magic */
    Serial.write((uint8_t)0xBA);
    Serial.write((uint8_t)0xE1);

    /* Send the packet data */
    Serial.write(buf, len);

    /* Simple checksum */
    checksum = 0;
    for(int i=0; i < len; i++) {
      checksum += buf[i];
    }
    Serial.write(checksum);
}

#if SERIAL_DEBUG
char debug_msg[100] = "";
#endif

int find_pipe_for_channel(uint8_t channel) {
  for(uint8_t i = 0; i < PIPES; i++) {
    if(config[i].id == channel)
      return i;
  }
  return -1;
}

void send_config(int pipe) {
  if(pipe < 0 || pipe >= PIPES)
    return;

  if(radio.isFifo(true) == 2) { /* Fifo full */
#if SERIAL_DEBUG
    Serial.println("Flushing TX FIFO");
#endif
    radio.flush_tx();
  }
  config_update[pipe] = !radio.writeAckPayload(pipe, &config[pipe], sizeof(config[0]));
}

int pipe = -1;
void loop() {
  if (radio.available()) {
    radio.read(&packet, sizeof(packet));
    pipe = find_pipe_for_channel(packet.id);
#if SERIAL_DEBUG
    sprintf(debug_msg, "[%lu] [%d] [ACC] %05.2f / %05.2f / %05.2f (%d@%lu) - [KNOCK] %d @ %lu ms [%d]",
                      packet.time,
                      packet.id,
                      packet.x, packet.y, packet.z,
                      packet.motion,
                      packet.time_last_motion,
                      packet.knock,
                      packet.time_last_knock,
                      sizeof(packet));
    Serial.println(debug_msg);
    if(pipe < 0 || pipe >= PIPES) {
      sprintf(debug_msg, "Invalid channel id %d for pipe with address ???", packet.id);
      Serial.println(debug_msg);
    } else {
      config[pipe].threshold += 1;
      sprintf(debug_msg, "CONF = [%d] -> [%d]", config[pipe].id, config[pipe].threshold);
      Serial.println(debug_msg);
    }
#else
    serial_transmit((uint8_t *)&packet, sizeof(packet));
    if(Serial.available() >= sizeof(config)) {
      Serial.readBytes((uint8_t *)&config, sizeof(config));
      radio.writeAckPayload(1, &config, sizeof(config));
    }
#endif
    send_config(pipe);
  }
}