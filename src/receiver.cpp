#include <Arduino.h>

#include <SPI.h>
#include <nRF24L01.h>
#include <RF24.h>

#include <packet.h>

RF24 radios[] = {
  RF24(4, 5),
  RF24(6, 7),
  RF24(8, 9),
};

packet_t packet = {};

#define N_RADIOS (sizeof(radios)/sizeof(radios[0]))

#define CHANNELS (N_RADIOS * PIPES_PER_RADIO)
conf_t config[CHANNELS];

bool config_update[CHANNELS];
packet_conf_t config_packet;

void setup() {
  Serial.begin(BAUD);
  while(!Serial)
    delay(10);

  for(uint8_t i=0; i < N_RADIOS; i++) {
    radios[i].begin();
    radios[i].setPALevel(RF24_PA_MIN);
    radios[i].enableDynamicPayloads();
    radios[i].enableAckPayload();
    radios[i].setDataRate(RF24_1MBPS);
    radios[i].setChannel(FREQ_BASE + i);

    for(uint8_t j = 0; j < PIPES_PER_RADIO; j++) {
      uint8_t pipe = i * PIPES_PER_RADIO + j;
      uint8_t channel_id = pipe + 1;
      config[pipe] = {.id=channel_id, .threshold=50, .duration=10};
      log_debug_fmt("Pipe %d with channel id %d default config set to threshold = %d - duration = %d",
                     pipe, config[pipe].id, config[pipe].threshold, config[pipe].duration);
      radios[i].openReadingPipe(j, address_for(config[pipe].id));
      config_update[pipe] = false;
    }

    radios[i].startListening();
  }
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
  for(uint8_t i = 0; i < CHANNELS; i++) {
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
    while(Serial.read() > 0) {}
    return false;
  }

  uint8_t checksum = 0;
  for(uint8_t i = 0; i < sizeof(config_packet) - 1; i++)
    checksum += ((uint8_t*)&config_packet)[i];
  if (checksum != config_packet.checksum) {
    log_debug("Invalid checksum");
    while(Serial.read() > 0) {}
    return false;
  }

  int pipe = find_pipe_for_channel(config_packet.payload.id);
  if (pipe < 0) {
    log_debug("Invalid pipe");
    return false;
  }

  log_debug_fmt("Updating channel %d threshold -> %d, duration -> %d (pipe %d)",
                config_packet.payload.id,
                config_packet.payload.threshold,
                config_packet.payload.duration,
                pipe);
  config[pipe].threshold = config_packet.payload.threshold;
  config[pipe].duration  = config_packet.payload.duration;
  config_update[pipe] = true;
  return true;
}

void send_config(uint8_t pipe) {
  if(pipe < 0 || pipe >= CHANNELS)
    return;

  if(!config_update[pipe])
    return;

  RF24 radio = radios[pipe / PIPES_PER_RADIO];

  if(radio.isFifo(true) == 2) { /* Fifo full */
    log_debug("Flushing TX FIFO");
    radio.flush_tx();
  }
  log_debug_fmt("Writing ACK payload on pipe %d: [Ch %d] threshold=%d duration=%d",
                  pipe, config[pipe].id, config[pipe].threshold, config[pipe].duration);
  config_update[pipe] = !radio.writeAckPayload(pipe, &config[pipe], sizeof(config[0]));
}

int pipe = -1;
void loop() {
  for(RF24 radio: radios) {
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

      if(pipe < 0 || pipe >= CHANNELS) {
        log_debug_fmt("Invalid channel id %d for pipe with address ???", packet.id);
      }
  #ifndef SERIAL_DEBUG
      serial_transmit((uint8_t *)&packet, sizeof(packet));
  #endif
      send_config(pipe);
    }
  }
  receive_config();
}