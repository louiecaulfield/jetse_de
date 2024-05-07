#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

RF24 radio(8, 7); // CE, CSN

#define SERIAL_DEBUG 0

#include <packet.h>
packet_t packet = {};

#define PIPES 6
conf_t config[PIPES] = {
  {.id=0, .threshold=50},
  {.id=1, .threshold=50},
  {.id=2, .threshold=50},
  {.id=3, .threshold=50},
  {.id=9, .threshold=50},
  {.id=5, .threshold=50},
};

bool config_update[PIPES];
packet_conf_t config_packet;

void setup() {
  Serial.begin(115200);
  while(!Serial)
    delay(10);

  radio.begin();
  radio.setPALevel(RF24_PA_MAX);
  radio.enableDynamicPayloads();
  radio.enableAckPayload();
  radio.setDataRate(RF24_1MBPS);

  for(uint8_t i = 0; i < PIPES; i++) {
    radio.openReadingPipe(i, address_for(config[i].id));
    config_update[i] = false;
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

int find_pipe_for_channel(uint8_t channel) {
  for(uint8_t i = 0; i < PIPES; i++) {
    if(config[i].id == channel)
      return i;
  }
  return -1;
}

bool receive_config() {
  if(Serial.available() < (int)sizeof(config_packet))
    return false;

  Serial.readBytes((uint8_t *)&config_packet, sizeof(config_packet));
  if(config_packet.magic != 0xBAE1) {
    log_debug("Invalid magic");
    while(Serial.read()) {}
    return false;
  }

  uint8_t checksum = 0;
  for(uint8_t i = 0; i < sizeof(config_packet) - 1; i++)
    checksum += ((uint8_t*)&config_packet)[i];
  if (checksum != config_packet.checksum) {
    log_debug("Invalid checksum");
    while(Serial.read()) {}
    return false;
  }

  int pipe = find_pipe_for_channel(config_packet.payload.id);
  if (pipe < 0) {
    log_debug("Invalid pipe");
    return false;
  }

  log_debug_fmt("Updating channel %d threshold to %d (pipe %d)",
                config_packet.payload.id,
                config_packet.payload.threshold,
                pipe);
  config[pipe].threshold = config_packet.payload.threshold;
  config_update[pipe] = true;
  return true;
}

void send_config(int pipe) {
  if(pipe < 0 || pipe >= PIPES)
    return;

  if(!config_update[pipe])
    return;

  if(radio.isFifo(true) == 2) { /* Fifo full */
    log_debug("Flushing TX FIFO");
    radio.flush_tx();
  }
  log_debug_fmt("Writing ACK payload on pipe %d: [Ch %d].threshold=%d",
                  pipe, config[pipe].id, config[pipe].threshold);
  config_update[pipe] = !radio.writeAckPayload(pipe, &config[pipe], sizeof(config[0]));
}

int pipe = -1;
void loop() {
  if (radio.available()) {
    radio.read(&packet, sizeof(packet));
    pipe = find_pipe_for_channel(packet.id);
    log_debug_fmt("[%lu] [%d] [ACC] %5d / %5d / %5d (%02X@%lu ms) [%d]",
      packet.time,
      packet.id,
      packet.x, packet.y, packet.z,
      packet.motion,
      packet.time_last_motion,
      sizeof(packet));

    if(pipe < 0 || pipe >= PIPES) {
      log_debug_fmt("Invalid channel id %d for pipe with address ???", packet.id);
    }
#if(!SERIAL_DEBUG)
    serial_transmit((uint8_t *)&packet, sizeof(packet));
#endif
    send_config(pipe);
  }
  receive_config();
}